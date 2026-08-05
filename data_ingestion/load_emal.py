"""
QUE HACE ESTE FICHERO
Lee los Excel oficiales del Gobierno Vasco con los precios de alquiler
REALMENTE PAGADOS (segun las fianzas depositadas) y los mete en la base.

POR QUE ES IMPORTANTE
Nuestros anuncios dicen lo que los propietarios PIDEN.
Este fichero dice lo que los inquilinos PAGAN.
Comparar ambos es la aportacion principal del TFM.

CODIGOS ESPECIALES DEL FICHERO
  "-"  = no hay oferta suficiente
  "."  = dato protegido por secreto estadistico
Ambos se guardan como nulo.
"""

import os

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Codigos INE leidos del propio fichero oficial
AF_INE = {
    '48002': 'Abanto y Ciervana', '48011': 'Arrigorriaga',
    '48013': 'Barakaldo', '48015': 'Basauri', '48016': 'Berango',
    '48020': 'Bilbao', '48029': 'Etxebarri', '48036': 'Galdakao',
    '48043': 'Gorliz', '48044': 'Getxo', '48054': 'Leioa',
    '48071': 'Muskiz', '48078': 'Portugalete', '48080': 'Valle de Trapaga',
    '48082': 'Santurtzi', '48083': 'Ortuella', '48084': 'Sestao',
    '48085': 'Sopela', '48089': 'Urduliz', '48901': 'Derio',
    '48902': 'Erandio',
}

# Galdakao aparece dos veces: (1) sin Usansolo, (2) con Usansolo.
# Los anuncios son de 2022, anteriores a la segregacion -> serie (2)
GALDAKAO_VARIANT = '(2)'

FILE_BARRIOS = 'data/raw/EMAL_-Barrios-Municipios_-2016-2025_es.xlsx'
SOURCE = 'EMAL'

def to_num(v):
    if pd.isna(v):
        return None
    s = str(v).strip()
    if s in ('-', '.', ''):
        return None
    try:
        return float(s)
    except ValueError:
        return None

def find_year_columns(df):
    for i in range(min(6, len(df))):
        cols = {}
        for j, v in df.iloc[i].items():
            if pd.notna(v):
                try:
                    y = int(float(v))
                    if 2016 <= y <= 2030:
                        cols[y] = j
                except (ValueError, TypeError):
                    pass
        if len(cols) >= 5:
            return cols
    return {}

def read_municipalities(sheet, metric):
    df = pd.read_excel(FILE_BARRIOS, sheet_name=sheet, header=None)
    years = find_year_columns(df)
    rows = []
    for _, r in df.iterrows():
        code = str(r[0]).strip() if pd.notna(r[0]) else ''
        name = str(r[1]).strip() if pd.notna(r[1]) else ''
        if not (code.isdigit() and len(code) == 5 and name):
            continue
        if code not in AF_INE:
            continue
        if code == '48036' and GALDAKAO_VARIANT not in name:
            continue
        for year, col in years.items():
            v = to_num(r[col])
            if v is not None:
                rows.append({'municipality': AF_INE[code], 'ine': code,
                             'neighbourhood': '', 'year': year,
                             'metric': metric, 'value': v})
    return rows

def read_bilbao_neighbourhoods(sheet, metric):
    df = pd.read_excel(FILE_BARRIOS, sheet_name=sheet, header=None)
    years = find_year_columns(df)
    rows = []
    for _, r in df.iterrows():
        if pd.isna(r[1]):
            continue
        try:
            int(float(r[1]))
        except (ValueError, TypeError):
            continue
        name = str(r[2]).strip() if pd.notna(r[2]) else ''
        if not name:
            continue
        for year, col in years.items():
            v = to_num(r[col])
            if v is not None:
                rows.append({'municipality': 'Bilbao', 'ine': '48020',
                             'neighbourhood': name, 'year': year,
                             'metric': metric, 'value': v})
    return rows

def get_engine():
    load_dotenv()
    url = os.getenv('DATABASE_URL')
    if not url:
        raise RuntimeError('Falta DATABASE_URL en el fichero .env')
    return create_engine(url)

def ensure_zone(conn, municipality, neighbourhood):
    conn.execute(text("""
        INSERT INTO core.dim_zone (municipality, neighbourhood, in_functional_area)
        VALUES (:m, :n, TRUE)
        ON CONFLICT (municipality, neighbourhood) DO NOTHING
    """), {'m': municipality, 'n': neighbourhood})

    return conn.execute(text("""
        SELECT zone_id FROM core.dim_zone
        WHERE municipality = :m
          AND neighbourhood IS NOT DISTINCT FROM :n
    """), {'m': municipality, 'n': neighbourhood}).scalar()

def main():
    print('1. Leyendo los ficheros de la EMAL...')
    records = (
        read_municipalities('T2.3', 'rent_per_sqm')
        + read_municipalities('T2.2', 'mean_rent')
        + read_bilbao_neighbourhoods('T6.3', 'rent_per_sqm')
        + read_bilbao_neighbourhoods('T6.2', 'mean_rent')
    )
    df = pd.DataFrame(records)
    print(f'   registros leidos: {len(df)}')

    # Agrupar sin generar combinaciones inexistentes.
    # groupby().first() solo devuelve las claves que existen de verdad.
    g = df.groupby(['municipality', 'ine', 'neighbourhood', 'year', 'metric'],
                   as_index=False)['value'].first()
    wide = g.pivot(index=['municipality', 'ine', 'neighbourhood', 'year'],
                   columns='metric', values='value').reset_index()
    wide.columns.name = None

    for c in ('mean_rent', 'rent_per_sqm'):
        if c not in wide.columns:
            wide[c] = None

    # Descartar filas sin ningun dato
    wide = wide.dropna(subset=['mean_rent', 'rent_per_sqm'], how='all')

    print(f'   filas a cargar: {len(wide)}')
    print(f'   zonas distintas: '
          f'{wide[["municipality", "neighbourhood"]].drop_duplicates().shape[0]}')

    print('\n2. Conectando a la base de datos...')
    engine = get_engine()

    with engine.begin() as conn:
        print('3. Resolviendo zonas...')
        zone_cache = {}
        for _, r in wide[['municipality', 'neighbourhood']].drop_duplicates().iterrows():
            neigh = r['neighbourhood'] if r['neighbourhood'] else None
            zone_cache[(r['municipality'], r['neighbourhood'])] = \
                ensure_zone(conn, r['municipality'], neigh)
        print(f'   zonas resueltas: {len(zone_cache)}')

        print('4. Asignando codigos INE...')
        for ine_code, muni in AF_INE.items():
            conn.execute(text("""
                UPDATE core.dim_zone SET municipality_ine = :i
                WHERE municipality = :m AND municipality_ine IS NULL
            """), {'i': ine_code, 'm': muni})

        print('5. Cargando precios oficiales...')
        rows = [{
            'z': zone_cache[(r['municipality'], r['neighbourhood'])],
            'y': int(r['year']),
            'mr': None if pd.isna(r['mean_rent']) else float(r['mean_rent']),
            'rps': None if pd.isna(r['rent_per_sqm']) else float(r['rent_per_sqm']),
            'src': SOURCE,
        } for _, r in wide.iterrows()]

        conn.execute(text("""
            INSERT INTO core.fact_official_rent
                (zone_id, year, quarter, mean_rent, rent_per_sqm, source)
            VALUES (:z, :y, NULL, :mr, :rps, :src)
            ON CONFLICT (zone_id, year, quarter, source) DO NOTHING
        """), rows)
        print(f'   filas enviadas: {len(rows)}')

    with engine.connect() as conn:
        total = conn.execute(text(
            'SELECT COUNT(*) FROM core.fact_official_rent')).scalar()
        print(f'\nTOTAL EN BASE DE DATOS: {total} registros oficiales')

if __name__ == '__main__':
    main()