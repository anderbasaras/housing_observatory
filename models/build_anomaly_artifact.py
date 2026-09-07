"""Construye el artefacto de deteccion de anomalias.

Reproduce las cuatro senales del notebook 04_anomalias sobre el
dataset completo y guarda en un unico .pkl todo lo que el endpoint
/score_anomaly necesita para puntuar un anuncio nuevo:

  - Isolation Forest ya entrenado
  - Mediana de precio/m2 por zona (con TODOS los anuncios)
  - Constantes estadisticas: media y desviacion de price_relative_zone,
    desviacion tipica de los residuos del modelo, min/max del score
    del Isolation Forest
  - Pesos, umbrales de las reglas y parametro de normalizacion

Se ejecuta UNA sola vez:
    python models/build_anomaly_artifact.py
"""

from pathlib import Path
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import IsolationForest

RANDOM_STATE = 42
RAIZ = Path(__file__).resolve().parent.parent
DATASET = RAIZ / "data" / "processed" / "model_dataset.parquet"
DIR_ART = RAIZ / "models" / "artifacts"
MODELO = DIR_ART / "price_model.pkl"
SALIDA = DIR_ART / "anomaly_meta.pkl"

NUMERICAS = ["area_sqm", "n_rooms", "sqm_per_room"]
CATEGORICAS = ["typology_grouped", "zona_modelo", "river_bank"]
VARS_ISO = ["monthly_price", "area_sqm", "n_rooms", "price_per_sqm", "sqm_per_room"]

# Umbrales de las reglas de consistencia (identicos al notebook)
REGLAS = {
    "precio_m2_min": 5, "precio_m2_max": 28,
    "superficie_min": 25, "superficie_max": 300,
    "habitaciones_max": 8,
    "densidad_min": 12,
}
PESOS = {"reglas": 0.35, "modelo": 0.30, "zona": 0.20, "iso": 0.15}
TOPE = 4.0

print("Cargando dataset y modelo...")
df = pd.read_parquet(DATASET)
modelo = joblib.load(MODELO)
print(f"  {len(df)} anuncios")

# --- SENAL 2: constantes de zona ---
# Mediana de precio/m2 por zona con TODOS los anuncios: un anuncio nuevo
# no forma parte del historico, asi que no se aplica leave-one-out.
zone_median = df.groupby("zona_modelo")["price_per_sqm"].median()
mediana_global = float(df["price_per_sqm"].median())  # respaldo si llega zona sin datos
# Media y desviacion de price_relative_zone: se toman de la columna del
# dataset para reproducir EXACTAMENTE los valores del notebook.
prz_mean = float(df["price_relative_zone"].mean())
prz_std = float(df["price_relative_zone"].std())
print("\nSENAL ZONA")
print(f"  Media de price_relative_zone: {prz_mean:.3f}")
print(f"  Desviacion tipica:            {prz_std:.3f}")

# --- SENAL 3: desviacion tipica de los residuos del modelo ---
con_datos = df[df["area_sqm"].notna()].copy()
pred_log = modelo.predict(con_datos[NUMERICAS + CATEGORICAS])
residuo = np.log(con_datos["monthly_price"]) - pred_log
r_std = float(residuo.std())
print("\nSENAL MODELO")
print(f"  Desviacion tipica del residuo: {r_std:.3f}")

# --- SENAL 4: Isolation Forest ---
datos_iso = df[VARS_ISO].dropna()
iso = IsolationForest(
    contamination=0.05, n_estimators=200, random_state=RANDOM_STATE,
)
iso.fit(datos_iso)
score_iso = -iso.score_samples(datos_iso)
iso_min = float(score_iso.min())
iso_max = float(score_iso.max())
print("\nSENAL ISOLATION FOREST")
print(f"  Anuncios evaluados: {len(datos_iso)}")
print(f"  score_iso min/max:  {iso_min:.3f} / {iso_max:.3f}")

# --- Guardar artefacto ---
meta = {
    "iso": iso,
    "vars_iso": VARS_ISO,
    "zone_median": zone_median.to_dict(),
    "mediana_global": mediana_global,
    "prz_mean": prz_mean,
    "prz_std": prz_std,
    "r_std": r_std,
    "iso_min": iso_min,
    "iso_max": iso_max,
    "reglas": REGLAS,
    "pesos": PESOS,
    "tope": TOPE,
    "numericas": NUMERICAS,
    "categoricas": CATEGORICAS,
}
joblib.dump(meta, SALIDA)
print(f"\nArtefacto guardado en: {SALIDA}")

# --- AUTOCOMPROBACION: puntuar todos los anuncios ---
# Reproduce la puntuacion compuesta usando el artefacto recien creado.
# Compara la distribucion resultante con la que imprimio el notebook.
def normaliza(serie, tope=TOPE):
    return (serie.abs().clip(0, tope) / tope).fillna(0)

r_pm2 = ((df["price_per_sqm"] < REGLAS["precio_m2_min"]) |
         (df["price_per_sqm"] > REGLAS["precio_m2_max"])).fillna(False)
r_sup = ((df["area_sqm"] < REGLAS["superficie_min"]) |
         (df["area_sqm"] > REGLAS["superficie_max"])).fillna(False)
r_hab = (df["n_rooms"] > REGLAS["habitaciones_max"]).fillna(False)
r_den = (df["sqm_per_room"] < REGLAS["densidad_min"]).fillna(False)
n_reglas = (r_pm2.astype(int) + r_sup.astype(int)
            + r_hab.astype(int) + r_den.astype(int))
p_reglas = (n_reglas / 4).clip(0, 1)

med = df["zona_modelo"].map(zone_median).fillna(mediana_global)
z_zona = ((df["price_per_sqm"] / med) - prz_mean) / prz_std
p_zona = normaliza(z_zona)

z_modelo = pd.Series(np.nan, index=df.index)
z_modelo.loc[con_datos.index] = residuo / r_std
p_modelo = normaliza(z_modelo)

s_iso = pd.Series(np.nan, index=df.index)
s_iso.loc[datos_iso.index] = score_iso
p_iso = ((s_iso - iso_min) / (iso_max - iso_min)).clip(0, 1).fillna(0)

anomaly_score = (PESOS["reglas"] * p_reglas + PESOS["modelo"] * p_modelo +
                 PESOS["zona"] * p_zona + PESOS["iso"] * p_iso).round(4)

print("\nDISTRIBUCION DE anomaly_score (comparar con el notebook)")
print(anomaly_score.describe().round(3).to_string())
print("\nLOS 10 MAS ANOMALOS")
tmp = df.assign(anomaly_score=anomaly_score, n_reglas=n_reglas)
cols = ["zona_modelo", "monthly_price", "area_sqm", "n_rooms",
        "price_per_sqm", "anomaly_score"]
print(tmp.nlargest(10, "anomaly_score")[cols].round(2).to_string(index=False))
