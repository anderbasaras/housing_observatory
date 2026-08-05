"""
QUE HACE ESTE FICHERO
Guarda en MongoDB dos cosas que PostgreSQL no puede guardar bien:

1. listings_raw: el anuncio ORIGINAL, tal cual venia del CSV, sin
   limpiar. Es la copia de seguridad: si manana descubrimos que una
   regla estaba mal, se puede rehacer todo desde aqui.

2. parsing_log: el "cuaderno de trabajo" de la transformacion. Por
   cada anuncio anota que texto entro, que regla se aplico y que
   salio. Sirve para demostrar que el parseo funciona, en lugar de
   pedir que nos crean.

POR QUE MONGODB Y NO POSTGRESQL
Estos datos no tienen forma fija: cada anuncio puede tener mas o
menos campos, y el log crece con reglas nuevas. Meterlo en tablas
rigidas seria forzar la herramienta.
"""

import os
from datetime import datetime, timezone

import pandas as pd
from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING

from data_ingestion.transform import (
    transform, parse_title, match_municipality, norm
)

CSV_PATH = 'data/raw/rent_spain_scraping_dataset.csv'
DB_NAME = 'housing_observatory'

def get_db():
    load_dotenv()
    uri = os.getenv('MONGODB_URI')
    if not uri:
        raise RuntimeError('Falta MONGODB_URI en el fichero .env')
    return MongoClient(uri)[DB_NAME]

def clean(v):
    """Convierte los NaN de pandas en None, que es lo que entiende Mongo."""
    if pd.isna(v):
        return None
    if hasattr(v, 'item'):      # tipos numpy -> tipos Python
        return v.item()
    return v

def load_raw(db, df):
    """Guarda el anuncio original con metadatos de la carga."""
    col = db['listings_raw']
    col.create_index([('fingerprint', ASCENDING)], unique=True)

    now = datetime.now(timezone.utc)
    docs = []
    for _, r in df.iterrows():
        docs.append({
            'fingerprint': r['fingerprint'],
            'source': {
                'dataset': 'rental-listins-in-idealista-spain',
                'author': 'Laura Barreda Agusti',
                'platform': 'Kaggle',
                'capture_date': '2022-07-01',
            },
            'raw_fields': {
                'provincia': clean(r.get('provincia')),
                'comunidad_autonoma': clean(r.get('comunidad autonoma')),
                'titulo': clean(r.get('titulo')),
                'precio': clean(r.get('precio')),
                'habitaciones': clean(r.get('habitaciones')),
                'metros': clean(r.get('metros')),
            },
            'ingestion': {
                'loaded_at': now,
                'pipeline_version': '1.0',
            },
        })

    inserted = 0
    for d in docs:
        res = col.update_one({'fingerprint': d['fingerprint']},
                             {'$setOnInsert': d}, upsert=True)
        if res.upserted_id:
            inserted += 1
    return inserted, col.count_documents({})

def load_parsing_log(db, df):
    """Registra que hizo cada regla sobre cada anuncio."""
    col = db['parsing_log']
    col.create_index([('fingerprint', ASCENDING)], unique=True)

    now = datetime.now(timezone.utc)
    inserted = 0

    for _, r in df.iterrows():
        title = r['titulo']
        segments = [norm(x) for x in str(title).split(',') if norm(x)]
        parsed = parse_title(title)

        rules = [
            {'rule': 'split_title_segments',
             'input': title,
             'output': segments,
             'success': len(segments) > 0},
            {'rule': 'extract_municipality',
             'input': parsed['municipality_raw'],
             'output': r['municipality'],
             'success': r['municipality'] is not None},
            {'rule': 'extract_neighbourhood',
             'input': segments[-2] if len(segments) >= 3 else None,
             'output': clean(r['neighbourhood']),
             'success': pd.notna(r['neighbourhood'])},
            {'rule': 'extract_typology',
             'input': segments[0] if segments else None,
             'output': clean(r['typology']),
             'success': pd.notna(r['typology'])},
            {'rule': 'extract_street_type',
             'input': segments[0] if segments else None,
             'output': clean(r['street_type']),
             'success': pd.notna(r['street_type'])},
            {'rule': 'parse_area',
             'input': clean(r.get('metros')),
             'output': clean(r['area_sqm']),
             'success': pd.notna(r['area_sqm'])},
        ]

        # Si la fila tenia las columnas corridas, se anota lo rescatado
        if r['column_shift_flag']:
            rules.append({
                'rule': 'recover_shifted_columns',
                'input': clean(r.get('metros')),
                'output': {'floor_level': clean(r['floor_level']),
                           'is_exterior': clean(r['is_exterior']),
                           'has_lift': clean(r['has_lift'])},
                'success': pd.notna(r['floor_level']),
            })

        doc = {
            'fingerprint': r['fingerprint'],
            'raw_title': title,
            'n_segments': len(segments),
            'column_shift_flag': bool(r['column_shift_flag']),
            'rules_applied': rules,
            'rules_ok': sum(1 for x in rules if x['success']),
            'rules_total': len(rules),
            'logged_at': now,
        }

        res = col.update_one({'fingerprint': doc['fingerprint']},
                             {'$setOnInsert': doc}, upsert=True)
        if res.upserted_id:
            inserted += 1

    return inserted, col.count_documents({})

def main():
    print('1. Transformando el CSV...')
    df = transform(CSV_PATH)

    print('\n2. Conectando a MongoDB...')
    db = get_db()

    print('3. Guardando anuncios originales...')
    n_raw, total_raw = load_raw(db, df)
    print(f'   nuevos: {n_raw} | total en coleccion: {total_raw}')

    print('4. Guardando registro de transformacion...')
    n_log, total_log = load_parsing_log(db, df)
    print(f'   nuevos: {n_log} | total en coleccion: {total_log}')

    # Resumen de rendimiento de cada regla
    print('\n5. Rendimiento de las reglas de parseo:')
    pipeline = [
        {'$unwind': '$rules_applied'},
        {'$group': {
            '_id': '$rules_applied.rule',
            'total': {'$sum': 1},
            'ok': {'$sum': {'$cond': ['$rules_applied.success', 1, 0]}},
        }},
        {'$sort': {'_id': 1}},
    ]
    for row in db['parsing_log'].aggregate(pipeline):
        pct = row['ok'] / row['total'] * 100
        print(f"   {row['_id']:28s} {row['ok']:4d}/{row['total']:4d}  ({pct:5.1f} %)")

if __name__ == '__main__':
    main()