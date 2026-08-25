"""
QUE HACE ESTE FICHERO
Mete en la base de datos la forma de los 46 barrios de Bilbao.

DE DONDE SALEN
Del visor geografico municipal GeoBilbao, que publica la capa oficial
de barrios con sus poligonos. Ya vienen en coordenadas de latitud y
longitud, asi que no hace falta traducir el sistema.
"""

import os

import geopandas as gpd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

GEOJSON = "data/raw/geo/barrios_bilbao.geojson"


def get_engine():
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("Falta DATABASE_URL en el fichero .env")
    return create_engine(url)


def main():
    print("1. Leyendo los barrios...")
    g = gpd.read_file(GEOJSON)
    print(f"   barrios: {len(g)} | sistema: {g.crs}")

    engine = get_engine()
    with engine.begin() as conn:
        print()
        print("2. Actualizando geometrias...")
        updated, created = 0, 0

        for _, r in g.iterrows():
            name = str(r["Nombre"]).strip()
            code = str(r["CodigoBarrio"]).strip()

            if name.upper() == "DISEMINADO":
                name = f"Diseminado {code}"

            res = conn.execute(text("""
                UPDATE core.dim_zone
                SET boundary = ST_Multi(ST_GeomFromText(:wkt, 4326)),
                    centroid = ST_PointOnSurface(ST_GeomFromText(:wkt, 4326))
                WHERE municipality = 'Bilbao'
                  AND UPPER(neighbourhood) = UPPER(:n)
            """), {"wkt": r["geometry"].wkt, "n": name})

            if res.rowcount:
                updated += res.rowcount
            else:
                conn.execute(text("""
                    INSERT INTO core.dim_zone
                        (municipality, neighbourhood, municipality_ine,
                         in_functional_area, boundary, centroid)
                    VALUES ('Bilbao', :n, '48020', TRUE,
                            ST_Multi(ST_GeomFromText(:wkt, 4326)),
                            ST_PointOnSurface(ST_GeomFromText(:wkt, 4326)))
                    ON CONFLICT (municipality, neighbourhood) DO NOTHING
                """), {"wkt": r["geometry"].wkt, "n": name})
                created += 1

        print(f"   actualizados: {updated} | creados: {created}")

    with engine.connect() as conn:
        n = conn.execute(text("""
            SELECT COUNT(*) FROM core.dim_zone
            WHERE municipality = 'Bilbao' AND neighbourhood IS NOT NULL
              AND boundary IS NOT NULL
        """)).scalar()
        print()
        print(f"BARRIOS CON GEOMETRIA: {n}")

if __name__ == "__main__":
    main()