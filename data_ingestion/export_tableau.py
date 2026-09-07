"""
QUE HACE ESTE FICHERO
Saca los datos de la base y los deja en ficheros que Tableau pueda leer.

POR QUE HACE FALTA
Tableau Public no puede conectarse a bases de datos, solo a ficheros.
Asi que se exporta lo necesario ya preparado: con los nombres de barrio
normalizados, la prediccion del modelo y la puntuacion de anomalia.

QUE GENERA
  tableau_anuncios.csv  Un anuncio por fila, con todo lo necesario
  tableau_brecha.csv    La brecha oferta-transaccion por zona
  tableau_zonas.geojson Los limites de barrios y municipios para mapas

Los CSV se guardan con punto y coma y codificacion de Windows, que es
lo que Tableau espera en configuracion espanola.
"""

import os

import geopandas as gpd
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

SALIDA = "data/processed/tableau"


def get_engine():
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("Falta DATABASE_URL en el fichero .env")
    return create_engine(url)


def exportar_anuncios(engine):
    """Un anuncio por fila, con zona normalizada y resultados de modelo."""
    df = pd.read_sql("""
        SELECT
            v.listing_id,
            v.monthly_price      AS precio_mes,
            v.area_sqm           AS superficie_m2,
            v.price_per_sqm      AS precio_m2,
            v.n_rooms            AS habitaciones,
            v.typology           AS tipologia,
            v.municipality       AS municipio,
            COALESCE(v.neighbourhood_official, v.neighbourhood_raw) AS barrio,
            v.neighbourhood_raw  AS barrio_anuncio,
            v.mapping_confidence AS confianza_barrio,
            z.river_bank         AS margen_ria,
            z.dist_centro        AS dist_centro_m,
            f.is_outlier         AS atipico,
            f.is_excluded        AS excluido,
            o.rent_per_sqm       AS emal_precio_m2,
            o.mean_rent          AS emal_renta_media
        FROM core.v_listing_mapped v
        JOIN core.fact_listing f ON f.listing_id = v.listing_id
        JOIN core.dim_zone z     ON f.zone_id = z.zone_id
        LEFT JOIN core.dim_zone zo
               ON zo.municipality = v.municipality
              AND zo.neighbourhood IS NOT DISTINCT FROM v.neighbourhood_official
        LEFT JOIN core.fact_official_rent o
               ON o.zone_id = zo.zone_id AND o.year = 2022
        WHERE f.is_excluded = FALSE
    """, engine)

    # Brecha de cada anuncio frente al dato oficial de su zona
    df["brecha_pct"] = np.where(
        df["emal_precio_m2"].notna(),
        ((df["precio_m2"] - df["emal_precio_m2"])
         / df["emal_precio_m2"] * 100).round(1),
        np.nan,
    )

    # Etiqueta legible para filtros en Tableau
    df["zona"] = df["municipio"] + " - " + df["barrio"].fillna("sin barrio")

    return df


def exportar_brecha(engine):
    """Resumen de la brecha por zona, listo para graficar."""
    return pd.read_sql("""
        SELECT
            z.municipality                        AS municipio,
            z.neighbourhood                       AS barrio,
            CASE WHEN z.neighbourhood IS NULL
                 THEN 'municipio' ELSE 'barrio' END AS nivel,
            z.river_bank                          AS margen_ria,
            o.year                                AS anio,
            ROUND(o.rent_per_sqm, 2)              AS precio_pagado_m2,
            ROUND(o.mean_rent, 0)                 AS renta_media
        FROM core.fact_official_rent o
        JOIN core.dim_zone z ON o.zone_id = z.zone_id
        WHERE o.rent_per_sqm IS NOT NULL
        ORDER BY z.municipality, z.neighbourhood, o.year
    """, engine)


def exportar_geometrias(engine):
    """Limites de barrios y municipios en formato de mapa."""
    g = gpd.read_postgis("""
        SELECT
            zone_id,
            municipality  AS municipio,
            neighbourhood AS barrio,
            river_bank    AS margen_ria,
            CASE WHEN neighbourhood IS NULL
                 THEN 'municipio' ELSE 'barrio' END AS nivel,
            boundary AS geometry
        FROM core.dim_zone
        WHERE boundary IS NOT NULL
    """, engine, geom_col="geometry")
    return g


def main():
    os.makedirs(SALIDA, exist_ok=True)
    engine = get_engine()

    print("1. Exportando anuncios...")
    anuncios = exportar_anuncios(engine)
    anuncios.to_csv(f"{SALIDA}/tableau_anuncios.csv",
                    index=False, sep=";", encoding="utf-8-sig", decimal=",")
    print(f"   {len(anuncios)} anuncios | {len(anuncios.columns)} columnas")
    print(f"   con dato oficial de contraste: {anuncios['emal_precio_m2'].notna().sum()}")

    print()
    print("2. Exportando serie de precios oficiales...")
    brecha = exportar_brecha(engine)
    brecha.to_csv(f"{SALIDA}/tableau_brecha.csv",
                  index=False, sep=";", encoding="utf-8-sig", decimal=",")
    print(f"   {len(brecha)} registros | {brecha['anio'].min()}-{brecha['anio'].max()}")

    print()
    print("3. Exportando geometrias...")
    geo = exportar_geometrias(engine)
    geo.to_file(f"{SALIDA}/tableau_zonas.geojson", driver="GeoJSON")
    print(f"   {len(geo)} zonas con limites")
    print(f"   barrios: {(geo['nivel'] == 'barrio').sum()} | "
          f"municipios: {(geo['nivel'] == 'municipio').sum()}")

    print()
    print(f"Ficheros generados en {SALIDA}/")


if __name__ == "__main__":
    main()
