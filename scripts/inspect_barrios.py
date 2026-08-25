import geopandas as gpd
g = gpd.read_file("data/raw/geo/barrios_bilbao.geojson")
print("barrios:", len(g))
print("crs:", g.crs)
print("columnas:", [c for c in g.columns if c != "geometry"])
print()
for _, r in g.iterrows():
    print("  ", r.get("CodigoBarrio"), "|", r.get("Nombre"))
