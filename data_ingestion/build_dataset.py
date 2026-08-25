"""
QUE HACE ESTE FICHERO
Construye el conjunto de datos final que usaran los modelos.

Hace dos cosas:
1. Calcula variables nuevas a partir de las que ya hay
2. Lo guarda todo junto en un fichero listo para modelar

LAS VARIABLES NUEVAS

price_relative_zone
  El precio del piso dividido entre lo normal en su barrio.
  Un 1,20 significa "un 20 por ciento mas caro de lo habitual aqui".
  Es mas util que el precio a secas: 1.200 euros es mucho en Otxarkoaga
  y poco en Abando.

  IMPORTANTE: la referencia se calcula SIN contar el propio anuncio.
  Si no, cada piso influiria en su propia vara de medir, y en barrios
  con pocos anuncios eso distorsiona bastante.

sqm_per_room
  Metros por habitacion. Distingue un piso de 80 metros con dos
  habitaciones de otro de 80 con cuatro.

typology_grouped
  Casa, chalet, finca y duplex tienen entre 1 y 18 registros cada uno.
  Con tan pocos casos el modelo no puede aprender nada de ellos, asi
  que se juntan en una categoria "otros".

EL FICHERO DE SALIDA
Se guarda en formato Parquet, que es como un Excel pero comprimido y
mucho mas rapido de leer. Es el formato que espera la siguiente fase.
"""

import os

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

SALIDA = "data/processed/analytical_dataset.parquet"

# Tipologias con menos de 20 registros: se agrupan
TIPOLOGIAS_PRINCIPALES = {"flat", "penthouse", "studio"}


def get_engine():
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("Falta DATABASE_URL en el fichero .env")
    return create_engine(url)


def mediana_sin_uno(serie):
    """Mediana del grupo excluyendo cada observacion de si misma.

    Para cada fila devuelve la mediana de las OTRAS filas del grupo.
    Evita que un anuncio forme parte de su propia referencia.
    """
    valores = serie.to_numpy(dtype=float)
    n = len(valores)
    if n <= 1:
        return pd.Series([np.nan] * n, index=serie.index)
    resultado = [
        np.nanmedian(np.delete(valores, i)) for i in range(n)
    ]
    return pd.Series(resultado, index=serie.index)


def main():
    print("1. Leyendo datos de la base...")
    engine = get_engine()

    df = pd.read_sql("""
        SELECT
            v.listing_id, v.fingerprint,
            v.monthly_price, v.area_sqm, v.price_per_sqm, v.n_rooms,
            v.typology, v.rooms_band, v.area_band,
            v.municipality,
            v.neighbourhood_raw,
            v.neighbourhood_official,
            v.mapping_confidence,
            v.street_type,
            z.river_bank,
            z.dist_centro,
            f.is_excluded, f.is_outlier, v.column_shift_flag,
            o.rent_per_sqm AS emal_rent_per_sqm,
            o.mean_rent     AS emal_mean_rent
        FROM core.v_listing_mapped v
        JOIN core.fact_listing f ON f.listing_id = v.listing_id
        JOIN core.dim_zone z     ON f.zone_id = z.zone_id
        LEFT JOIN core.dim_zone zo
               ON zo.municipality = v.municipality
              AND zo.neighbourhood IS NOT DISTINCT FROM v.neighbourhood_official
        LEFT JOIN core.fact_official_rent o
               ON o.zone_id = zo.zone_id AND o.year = 2022
    """, engine)

    print(f"   registros: {len(df)}")

    # Los excluidos por error geografico no entran en el conjunto final
    df = df[~df["is_excluded"]].copy()
    print(f"   tras excluir errores geograficos: {len(df)}")

    print()
    print("2. Calculando variables derivadas...")

    # Referencia de zona: barrio si lo hay, municipio si no
    df["zona_ref"] = df["neighbourhood_official"].fillna(df["municipality"])

    # Mediana de la zona excluyendo el propio anuncio
    df["zone_median_sqm"] = (
        df.groupby("zona_ref")["price_per_sqm"]
          .transform(mediana_sin_uno)
          .round(2)
    )
    df["price_relative_zone"] = (
        df["price_per_sqm"] / df["zone_median_sqm"]
    ).round(3)
    print(f"   price_relative_zone: {df['price_relative_zone'].notna().sum()} valores")

    # Metros por habitacion
    df["sqm_per_room"] = np.where(
        df["n_rooms"] > 0, (df["area_sqm"] / df["n_rooms"]).round(1), np.nan
    )
    print(f"   sqm_per_room: {df['sqm_per_room'].notna().sum()} valores")

    # Agrupacion de tipologias minoritarias
    df["typology_grouped"] = np.where(
        df["typology"].isin(TIPOLOGIAS_PRINCIPALES), df["typology"], "other"
    )
    print("   typology_grouped:")
    for t, n in df["typology_grouped"].value_counts().items():
        print(f"      {t:12s} {n:4d}")

    # Brecha frente al dato oficial, cuando existe
    df["gap_vs_official"] = np.where(
        df["emal_rent_per_sqm"].notna(),
        ((df["price_per_sqm"] - df["emal_rent_per_sqm"])
         / df["emal_rent_per_sqm"] * 100).round(1),
        np.nan,
    )
    print(f"   gap_vs_official: {df['gap_vs_official'].notna().sum()} valores")

    print()
    print("3. Guardando el conjunto analitico...")
    os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
    df.to_parquet(SALIDA, index=False)

    tam = os.path.getsize(SALIDA) / 1024
    print(f"   {SALIDA}")
    print(f"   {len(df)} filas | {len(df.columns)} columnas | {tam:.0f} KB")

    print()
    print("4. Resumen del conjunto:")
    print(f"   municipios: {df['municipality'].nunique()}")
    print(f"   zonas de referencia: {df['zona_ref'].nunique()}")
    print(f"   con dato oficial de contraste: {df['emal_rent_per_sqm'].notna().sum()}")
    print(f"   marcados como atipicos: {df['is_outlier'].sum()}")
    print(f"   sin superficie: {df['area_sqm'].isna().sum()}")


if __name__ == "__main__":
    main()
