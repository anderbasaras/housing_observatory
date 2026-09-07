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
