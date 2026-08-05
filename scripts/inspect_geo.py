"""
QUE HACE ESTE FICHERO
Abre los mapas descargados y enseña que informacion contienen:
que columnas tienen, cuantas zonas hay y en que sistema de
coordenadas estan.

No modifica nada. Solo mira.
"""

import geopandas as gpd

for name, path in [
    ('MUNICIPIOS', 'data/raw/geo/municipios/MUNICIPIOS_5000_ETRS89.shp'),
    ('AREAS FUNCIONALES',
     'data/raw/geo/areas_funcionales/AREAS_FUNCIONALES_5000_ETRS89.shp'),
]:
    g = gpd.read_file(path)
    print('=' * 60)
    print(name)
    print('  filas:', len(g))
    print('  sistema de coordenadas:', g.crs)
    print('  columnas:', [c for c in g.columns if c != 'geometry'])
    print('\n  primeras filas:')
    print(g.drop(columns='geometry').head(4).to_string())
    print()