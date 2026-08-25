"""
QUE HACE ESTE FICHERO
Calcula, para cada barrio y municipio, lo lejos que esta del metro, del
tren, de un hospital y del centro de Bilbao.

PARA QUE SIRVE
La cercania al transporte es una de las cosas que mas influye en el
precio de un alquiler. Sin esta informacion el modelo solo sabe el
tamano del piso y el nombre del barrio.

DE DONDE SALEN LOS DATOS
De OpenStreetMap, un mapa colaborativo mundial de consulta libre.

COMO SE CONSULTA
Se pide un unico rectangulo que cubre toda el Area Funcional, en lugar
de preguntar municipio por municipio. Asi se evita depender de que el
nombre de cada municipio se reconozca y se reduce el numero de
peticiones, que es donde fallaba antes.

COMO SE MIDE
Desde el punto central de cada zona hasta el equipamiento mas cercano,
en linea recta. Es una aproximacion: no tiene en cuenta las cuestas de
Bilbao ni el recorrido real a pie.
"""

import os

import geopandas as gpd
import osmnx as ox
from dotenv import load_dotenv
from shapely.geometry import Point, box
from sqlalchemy import create_engine, text

# El servidor de OSM responde lento con areas grandes.
# Se amplia el tiempo de espera y se activan los reintentos.
ox.settings.requests_timeout = 300
ox.settings.overpass_rate_limit = True
ox.settings.use_cache = True

# Rectangulo que cubre el Area Funcional de Bilbao Metropolitano
NORTE, SUR = 43.45, 43.15
ESTE, OESTE = -2.80, -3.15

# Plaza Moyua: centro funcional de Bilbao
CENTRO = Point(-2.9350, 43.2630)

# Sistema metrico para medir en metros (el de grados no sirve)
CRS_METRICO = "EPSG:25830"


def get_engine():
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("Falta DATABASE_URL en el fichero .env")
    return create_engine(url)


def traer_de_osm(etiquetas, filtro=None):
    """Consulta OSM sobre el rectangulo que cubre el area metropolitana."""
    poligono = box(OESTE, SUR, ESTE, NORTE)
    try:
        g = ox.features_from_polygon(poligono, tags=etiquetas)
    except Exception as e:
        print(f"      ERROR: {type(e).__name__}")
        return None
    if filtro:
        col, valor = filtro
        if col in g.columns:
            g = g[g[col] == valor]
    return g[["geometry"]] if len(g) else None


def a_puntos(g):
    """Convierte poligonos en puntos para poder medir distancias.

    Se reproyecta ANTES de calcular el centro: hacerlo sobre
    coordenadas en grados da resultados desplazados.
    """
    g = g.to_crs(CRS_METRICO).copy()
    g["geometry"] = g.geometry.centroid
    return g


def main():
    print("1. Descargando equipamientos de OpenStreetMap...")

    capas = {}
    for nombre, etiquetas, filtro in [
        ("metro",    {"railway": "station"}, ("station", "subway")),
        ("tren",     {"railway": "station"}, None),
        ("hospital", {"amenity": "hospital"}, None),
        ("colegio",  {"amenity": "school"}, None),
    ]:
        print(f"   {nombre}...")
        g = traer_de_osm(etiquetas, filtro)
        if g is not None and len(g):
            capas[nombre] = a_puntos(g)
            print(f"      {len(g)} elementos")
        else:
            print("      sin resultados")

    print()
    print("2. Leyendo zonas de la base de datos...")
    engine = get_engine()

    zonas = gpd.read_postgis(
        """SELECT zone_id, municipality, neighbourhood, centroid AS geometry
           FROM core.dim_zone WHERE centroid IS NOT NULL""",
        engine, geom_col="geometry")
    print(f"   zonas con centroide: {len(zonas)}")

    zonas_m = zonas.to_crs(CRS_METRICO)
    centro_m = gpd.GeoSeries([CENTRO], crs="EPSG:4326").to_crs(CRS_METRICO).iloc[0]

    print()
    print("3. Calculando distancias...")
    zonas["dist_centro"] = zonas_m.geometry.distance(centro_m).round(0)
    print(f"   dist_centro: mediana {zonas['dist_centro'].median():.0f} m")

    for nombre, capa in capas.items():
        zonas[f"dist_{nombre}"] = [
            round(capa.geometry.distance(p).min(), 0) for p in zonas_m.geometry
        ]
        print(f"   dist_{nombre}: mediana {zonas[f'dist_{nombre}'].median():.0f} m")

    print()
    print("4. Guardando en la base de datos...")
    with engine.begin() as conn:
        conn.execute(text("""
            ALTER TABLE core.dim_zone
                ADD COLUMN IF NOT EXISTS dist_centro   INTEGER,
                ADD COLUMN IF NOT EXISTS dist_metro    INTEGER,
                ADD COLUMN IF NOT EXISTS dist_tren     INTEGER,
                ADD COLUMN IF NOT EXISTS dist_hospital INTEGER,
                ADD COLUMN IF NOT EXISTS dist_colegio  INTEGER
        """))

        filas = []
        for _, r in zonas.iterrows():
            filas.append({
                "z": int(r["zone_id"]),
                "c": int(r["dist_centro"]),
                "m": int(r["dist_metro"]) if "dist_metro" in zonas.columns else None,
                "t": int(r["dist_tren"]) if "dist_tren" in zonas.columns else None,
                "h": int(r["dist_hospital"]) if "dist_hospital" in zonas.columns else None,
                "e": int(r["dist_colegio"]) if "dist_colegio" in zonas.columns else None,
            })

        conn.execute(text("""
            UPDATE core.dim_zone
            SET dist_centro = :c, dist_metro = :m, dist_tren = :t,
                dist_hospital = :h, dist_colegio = :e
            WHERE zone_id = :z
        """), filas)

    print(f"   actualizadas: {len(filas)} zonas")


if __name__ == "__main__":
    main()