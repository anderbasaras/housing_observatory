"""
QUE HACE ESTE FICHERO
Coge los datos ya limpios y los mete en la base de datos.

POR QUE EN TRES PASOS
La tabla de anuncios no guarda "Indautxu, Bilbao" como texto: guarda
un numero que apunta a otra tabla. Asi el nombre se escribe una sola
vez aunque haya 500 anuncios en ese barrio.

Por eso primero se rellenan las tablas de barrios, fechas y tipos
(las "dimensiones"), luego se leen para saber que numero le toco a
cada una, y solo entonces se insertan los anuncios.

SE PUEDE EJECUTAR VARIAS VECES
Si lo lanzas dos veces no duplica nada: la base rechaza los repetidos.
"""

import os
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from data_ingestion.transform import transform

CSV_PATH = 'data/raw/rent_spain_scraping_dataset.csv'
CAPTURE_DATE = '2022-07-01'   # ver apartado 6.1 del documento de alcance

def get_engine():
    load_dotenv()
    url = os.getenv('DATABASE_URL')
    if not url:
        raise RuntimeError('Falta DATABASE_URL en el fichero .env')
    return create_engine(url)

def load_dim_time(conn):
    """Una sola fila: la fecha de captura del CSV."""
    conn.execute(text("""
        INSERT INTO core.dim_time (capture_date, year, quarter, month, is_snapshot)
        VALUES (:d, 2022, 3, 7, TRUE)
        ON CONFLICT (capture_date) DO NOTHING
    """), {'d': CAPTURE_DATE})

    return conn.execute(text(
        "SELECT time_id FROM core.dim_time WHERE capture_date = :d"
    ), {'d': CAPTURE_DATE}).scalar()

def load_dim_zone(conn, df):
    """Una fila por combinacion municipio + barrio."""
    zones = df[['municipality', 'neighbourhood']].drop_duplicates()

    for _, r in zones.iterrows():
        conn.execute(text("""
            INSERT INTO core.dim_zone (municipality, neighbourhood, in_functional_area)
            VALUES (:m, :n, TRUE)
            ON CONFLICT (municipality, neighbourhood) DO NOTHING
        """), {'m': r['municipality'],
               'n': None if pd.isna(r['neighbourhood']) else r['neighbourhood']})

    rows = conn.execute(text(
        "SELECT zone_id, municipality, neighbourhood FROM core.dim_zone"
    )).fetchall()
    return {(m, n): z for z, m, n in rows}

def load_dim_property_type(conn, df):
    """Una fila por combinacion tipologia + tramo habitaciones + tramo superficie."""
    types = df[['typology', 'rooms_band', 'area_band']].drop_duplicates()

    for _, r in types.iterrows():
        conn.execute(text("""
            INSERT INTO core.dim_property_type
                   (typology, rooms_band, area_band, operation)
            VALUES (:t, :r, :a, 'rent')
            ON CONFLICT (typology, rooms_band, area_band, operation) DO NOTHING
        """), {'t': r['typology'],
               'r': None if pd.isna(r['rooms_band']) else r['rooms_band'],
               'a': None if pd.isna(r['area_band']) else r['area_band']})

    rows = conn.execute(text("""
        SELECT property_type_id, typology, rooms_band, area_band
        FROM core.dim_property_type WHERE operation = 'rent'
    """)).fetchall()
    return {(t, r, a): p for p, t, r, a in rows}

def load_dim_data_quality(conn, df):
    """Una fila por combinacion de banderas de calidad."""
    cols = ['column_shift_flag', 'neighbourhood_src', 'area_imputed', 'rooms_imputed']
    combos = df[cols].drop_duplicates()

    for _, r in combos.iterrows():
        conn.execute(text("""
            INSERT INTO core.dim_data_quality
                   (column_shift_flag, neighbourhood_src, area_imputed, rooms_imputed)
            VALUES (:c, :s, :a, :r)
            ON CONFLICT (column_shift_flag, neighbourhood_src, area_imputed, rooms_imputed)
            DO NOTHING
        """), {'c': bool(r['column_shift_flag']), 's': r['neighbourhood_src'],
               'a': bool(r['area_imputed']), 'r': bool(r['rooms_imputed'])})

    rows = conn.execute(text("""
        SELECT quality_id, column_shift_flag, neighbourhood_src,
               area_imputed, rooms_imputed
        FROM core.dim_data_quality
    """)).fetchall()
    return {(c, s, a, r): q for q, c, s, a, r in rows}

def none_if_nan(v):
    """Convierte los NaN de pandas en None, que es lo que entiende SQL."""
    return None if pd.isna(v) else v

def load_facts(conn, df, time_id, zones, types, qualities):
    inserted = 0
    for _, r in df.iterrows():
        zone_key = (r['municipality'],
                    None if pd.isna(r['neighbourhood']) else r['neighbourhood'])
        type_key = (r['typology'],
                    None if pd.isna(r['rooms_band']) else r['rooms_band'],
                    None if pd.isna(r['area_band']) else r['area_band'])
        qual_key = (bool(r['column_shift_flag']), r['neighbourhood_src'],
                    bool(r['area_imputed']), bool(r['rooms_imputed']))

        res = conn.execute(text("""
            INSERT INTO core.fact_listing
                (fingerprint, time_id, zone_id, property_type_id, quality_id,
                 monthly_price, area_sqm, n_rooms,
                 street_type, street_number, raw_title,
                 floor_level, is_exterior, has_lift)
            VALUES
                (:fp, :ti, :zi, :pi, :qi,
                 :price, :area, :rooms,
                 :stype, :snum, :title,
                 :floor, :ext, :lift)
            ON CONFLICT (fingerprint) DO NOTHING
        """), {
            'fp': r['fingerprint'],
            'ti': time_id,
            'zi': zones[zone_key],
            'pi': types[type_key],
            'qi': qualities[qual_key],
            'price': float(r['monthly_price']),
            'area': none_if_nan(r['area_sqm']),
            'rooms': none_if_nan(r['n_rooms']),
            'stype': none_if_nan(r['street_type']),
            'snum': none_if_nan(r['street_number']),
            'title': r['titulo'],
            'floor': none_if_nan(r['floor_level']),
            'ext': none_if_nan(r['is_exterior']),
            'lift': none_if_nan(r['has_lift']),
        })
        inserted += res.rowcount
    return inserted

def main():
    print('1. Transformando el CSV...')
    df = transform(CSV_PATH)

    print('\n2. Conectando a la base de datos...')
    engine = get_engine()

    with engine.begin() as conn:
        print('3. Cargando dimensiones...')
        time_id = load_dim_time(conn)
        zones = load_dim_zone(conn, df)
        types = load_dim_property_type(conn, df)
        qualities = load_dim_data_quality(conn, df)
        print(f'   zonas: {len(zones)} | tipos: {len(types)} | calidad: {len(qualities)}')

        print('4. Cargando anuncios...')
        n = load_facts(conn, df, time_id, zones, types, qualities)
        print(f'   insertados: {n}')

    with engine.connect() as conn:
        total = conn.execute(text('SELECT COUNT(*) FROM core.fact_listing')).scalar()
        print(f'\nTOTAL EN BASE DE DATOS: {total} anuncios')

if __name__ == '__main__':
    main()