"""
QUE HACE ESTE FICHERO
Saca del mapa oficial la lista de municipios que pertenecen al Area
Funcional de Bilbao Metropolitano.

POR QUE IMPORTA
Hasta ahora la lista estaba escrita a mano. Ahora sale directamente
de la cartografia oficial del Gobierno Vasco, que es citable.
"""

import geopandas as gpd

g = gpd.read_file("data/raw/geo/municipios/MUNICIPIOS_5000_ETRS89.shp")

print("Areas funcionales disponibles:")
for a in sorted(g["A_FUNC_CAS"].dropna().unique()):
    print("   -", a)

af = g[g["A_FUNC_CAS"].str.contains("BILBAO", case=False, na=False)]
print()
print("MUNICIPIOS DEL AREA FUNCIONAL:", len(af))
print()
for _, r in af.sort_values("NOMBRE_TOP").iterrows():
    print(f"   {r['EUSTAT']}  {r['NOMBRE_TOP']}")
