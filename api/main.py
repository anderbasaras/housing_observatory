"""API del Observatorio de Vivienda - prediccion de precio de alquiler.

Sirve el modelo de precio entrenado a traves de HTTP. Levantar con:
    uvicorn api.main:app --reload

Documentacion interactiva automatica en:
    http://127.0.0.1:8000/docs
"""

import logging

import numpy as np
import pandas as pd
from fastapi import FastAPI

from api.model_loader import modelo, COLUMNAS, ZONAS_VALIDAS
from api.schemas import PeticionPrecio, RespuestaPrecio

# Logging basico: registra cada prediccion. Es la semilla de la
# monitorizacion (fase 5): sirve para vigilar drift mas adelante.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("observatorio")

app = FastAPI(
    title="Observatorio Inteligente de Vivienda - API de precio",
    description="Estima el precio de alquiler en Bilbao Metropolitano.",
    version="1.0.0",
)


@app.get("/")
def raiz():
    """Comprobacion rapida de que la API esta viva."""
    return {"estado": "ok", "mensaje": "API del Observatorio de Vivienda"}


@app.get("/zonas")
def listar_zonas():
    """Devuelve las zonas validas, para saber que valores admite el modelo."""
    return {"n_zonas": len(ZONAS_VALIDAS), "zonas": sorted(ZONAS_VALIDAS)}


@app.post("/predict_price", response_model=RespuestaPrecio)
def predict_price(peticion: PeticionPrecio):
    """Estima el precio mensual de un alquiler.

    Pasos:
    1. Calcular sqm_per_room (igual que en el ETL).
    2. Montar un DataFrame de una fila con las 6 columnas, en orden.
    3. Predecir. OJO: el modelo devuelve LOG(precio), asi que hay
       que deshacer con exp() para obtener euros.
    """
    # 1. Variable derivada. n_rooms >= 1 garantizado por el esquema,
    #    asi que no hay division por cero.
    sqm_per_room = round(peticion.area_sqm / peticion.n_rooms, 1)

    # 2. Una fila con las columnas EXACTAS que espera el pipeline.
    fila = pd.DataFrame([{
        "area_sqm": peticion.area_sqm,
        "n_rooms": peticion.n_rooms,
        "sqm_per_room": sqm_per_room,
        "typology_grouped": peticion.typology_grouped,
        "zona_modelo": peticion.zona_modelo,
        "river_bank": peticion.river_bank,
    }])[COLUMNAS]  # reordena por seguridad

    # 3. Prediccion en escala logaritmica -> se deshace con exp().
    pred_log = modelo.predict(fila)[0]
    precio_eur = float(np.exp(pred_log))

    log.info(
        "prediccion zona=%s area=%.0f rooms=%d -> %.0f EUR",
        peticion.zona_modelo, peticion.area_sqm, peticion.n_rooms, precio_eur,
    )

    return RespuestaPrecio(
        precio_estimado_eur=round(precio_eur, 2),
        sqm_per_room=sqm_per_room,
    )


from api.model_loader import anomaly_meta
from api.schemas import PeticionAnomalia, RespuestaAnomalia, DesgloseSenales


def _clip01(x):
    """Recorta un valor al rango [0, 1]."""
    return max(0.0, min(1.0, float(x)))


@app.post("/score_anomaly", response_model=RespuestaAnomalia)
def score_anomaly(peticion: PeticionAnomalia):
    """Audita si el precio de un anuncio es anomalo.

    Combina las cuatro senales del sistema (reglas, desviacion de
    zona, desviacion del modelo, Isolation Forest) en una puntuacion
    de 0 a 1. Las constantes se leen del artefacto anomaly_meta, por
    lo que el resultado es identico al del notebook.
    """
    m = anomaly_meta
    reglas = m["reglas"]
    pesos = m["pesos"]
    tope = m["tope"]

    # Variables derivadas, igual que en el ETL.
    price_per_sqm = peticion.monthly_price / peticion.area_sqm
    sqm_per_room = round(peticion.area_sqm / peticion.n_rooms, 1)

    # --- SENAL 1: reglas de consistencia ---
    r_pm2 = price_per_sqm < reglas["precio_m2_min"] or price_per_sqm > reglas["precio_m2_max"]
    r_sup = peticion.area_sqm < reglas["superficie_min"] or peticion.area_sqm > reglas["superficie_max"]
    r_hab = peticion.n_rooms > reglas["habitaciones_max"]
    r_den = sqm_per_room < reglas["densidad_min"]
    n_reglas = int(r_pm2) + int(r_sup) + int(r_hab) + int(r_den)
    p_reglas = _clip01(n_reglas / 4)

    # --- SENAL 2: desviacion respecto a la mediana de la zona ---
    # Mediana de la zona (con todos los anuncios). Si la zona no
    # estuviera en el artefacto, se usa la mediana global de respaldo.
    med_zona = m["zone_median"].get(peticion.zona_modelo, m["mediana_global"])
    price_relative_zone = price_per_sqm / med_zona
    z_zona = (price_relative_zone - m["prz_mean"]) / m["prz_std"]
    p_zona = _clip01(min(abs(z_zona), tope) / tope)

    # --- SENAL 3: desviacion respecto a lo que predice el modelo ---
    fila = pd.DataFrame([{
        "area_sqm": peticion.area_sqm,
        "n_rooms": peticion.n_rooms,
        "sqm_per_room": sqm_per_room,
        "typology_grouped": peticion.typology_grouped,
        "zona_modelo": peticion.zona_modelo,
        "river_bank": peticion.river_bank,
    }])[COLUMNAS]
    pred_log = modelo.predict(fila)[0]
    precio_esperado = float(np.exp(pred_log))
    residuo = np.log(peticion.monthly_price) - pred_log
    z_modelo = residuo / m["r_std"]
    p_modelo = _clip01(min(abs(z_modelo), tope) / tope)

    # --- SENAL 4: Isolation Forest ---
    fila_iso = pd.DataFrame([{
        "monthly_price": peticion.monthly_price,
        "area_sqm": peticion.area_sqm,
        "n_rooms": peticion.n_rooms,
        "price_per_sqm": price_per_sqm,
        "sqm_per_room": sqm_per_room,
    }])[m["vars_iso"]]
    score_iso = float(-m["iso"].score_samples(fila_iso)[0])
    p_iso = _clip01((score_iso - m["iso_min"]) / (m["iso_max"] - m["iso_min"]))

    # --- Puntuacion compuesta ---
    anomaly_score = round(
        pesos["reglas"] * p_reglas + pesos["modelo"] * p_modelo +
        pesos["zona"] * p_zona + pesos["iso"] * p_iso, 4
    )

    log.info(
        "anomalia zona=%s precio=%.0f -> score=%.3f (reglas=%d)",
        peticion.zona_modelo, peticion.monthly_price, anomaly_score, n_reglas,
    )

    return RespuestaAnomalia(
        anomaly_score=anomaly_score,
        precio_esperado_eur=round(precio_esperado, 2),
        z_modelo=round(float(z_modelo), 2),
        z_zona=round(float(z_zona), 2),
        n_reglas_activadas=n_reglas,
        desglose=DesgloseSenales(
            reglas=round(p_reglas, 4),
            zona=round(p_zona, 4),
            modelo=round(p_modelo, 4),
            iso=round(p_iso, 4),
        ),
        aviso="Indicio estadistico, no prueba de fraude. Requiere revision.",
    )
