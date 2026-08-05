"""
QUE HACE ESTE FICHERO
Mete en la base de datos la FORMA de cada municipio: su contorno en
el mapa y su punto central.

PARA QUE SIRVE
Sin esto no se pueden pintar mapas. Con esto podras hacer un mapa de
colores donde cada municipio se tine segun su precio.

EL PASO CRITICO: LA REPROYECCION
El mapa oficial vasco usa un sistema de coordenadas propio de Espana
(EPSG 25830, metros desde un punto de referencia). Las librerias de
mapas de internet usan otro (EPSG 4326, latitud y longitud de toda la
vida). Hay que traducir de uno a otro.

Si se olvida este paso los mapas salen vacios y los municipios
aparecen en mitad del oceano.
"""

import os
import geopandas as gpd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

SHAPEFILE = 'data/raw/geo/municipios/MUNICIPIOS_5000_ETRS89.shp'
AREA_FUNCIONAL = 'BILBAO METROPOLITANO'
TARGET_CRS = 'EPSG:4326'

# Usansolo se segrego de Galdakao despues del periodo de analisis.
# Se asigna a Galdakao para mantener la coherencia temporal.
MERGE_INTO = {'48916': '48036'}

def get_engine():
    load_dotenv()
    url = os.getenv('DATABASE_URL')
    if not url:
        raise RuntimeError('Falta DATABASE_URL en el fichero .env')
    return create_engine(url)

def load_shapes():
    g = gpd.read_file(SHAPEFILE)
    print(f'   municipios en el fichero: {len(g)}')
    print(f'   sistema original: {g.crs}')

    af = g[g['A_FUNC_CAS'].str.contains(AREA_FUNCIONAL, case=False, na=False)].copy()
    print(f'   en el Area Funcional: {len(af)}')

    # Unir Usansolo con Galdakao antes de reproyectar
    af['ine'] = af['EUSTAT'].replace(MERGE_INTO)
    af = af.dissolve(by='ine', aggfunc='first').reset_index()
    print(f'   tras unir Usansolo con Galdakao: {len(af)}')

    af = af.to_crs(TARGET_CRS)
    print(f'   reproyectado a: {af.crs}')
    return af

def main():
    print('1. Leyendo la cartografia...')
    shapes = load_shapes()

    print('\n2. Conectando a la base de datos...')
    engine = get_engine()

    with engine.begin() as conn:
        print('3. Actualizando geometrias...')
        updated = 0
        not_found = []

        for _, r in shapes.iterrows():
            res = conn.execute(text("""
                UPDATE core.dim_zone
                SET boundary = ST_Multi(ST_GeomFromText(:wkt, 4326)),
                    centroid = ST_PointOnSurface(ST_GeomFromText(:wkt, 4326)),
                    municipality_ine = :ine
                WHERE neighbourhood IS NULL
                  AND (municipality_ine = :ine
                       OR (municipality_ine IS NULL
                           AND UPPER(municipality) LIKE UPPER(:pattern)))
            """), {
                'wkt': r['geometry'].wkt,
                'ine': r['ine'],
                'pattern': r['NOMBRE_TOP'].split('-')[0].split('/')[0].strip() + '%',
            })
            if res.rowcount:
                updated += res.rowcount
            else:
                not_found.append(f"{r['ine']} {r['NOMBRE_TOP']}")

        print(f'   zonas actualizadas: {updated}')
        if not_found:
            print(f'   sin correspondencia ({len(not_found)}):')
            for n in not_found:
                print(f'      {n}')

    with engine.connect() as conn:
        n = conn.execute(text(
            'SELECT COUNT(*) FROM core.dim_zone WHERE boundary IS NOT NULL'
        )).scalar()
        print(f'\nZONAS CON GEOMETRIA: {n}')


if __name__ == '__main__':
    main()