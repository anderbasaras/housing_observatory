"""Carga de artefactos del modelo.

Este modulo carga el Pipeline entrenado y sus metadatos UNA sola vez,
cuando arranca la aplicacion. Asi no se lee el .pkl del disco en cada
peticion, que seria lento e innecesario.

El Pipeline lleva DENTRO el preprocesado (one-hot de las categoricas),
por lo que recibe los datos "en crudo" y no hay que codificar a mano.
"""

from pathlib import Path
import joblib

# Ruta a la carpeta de artefactos, relativa a la raiz del proyecto.
# __file__ es este archivo (api/model_loader.py); subimos un nivel
# (parent.parent) para llegar a la raiz del repositorio.
RAIZ = Path(__file__).resolve().parent.parent
DIR_ARTEFACTOS = RAIZ / "models" / "artifacts"

# Carga del Pipeline entrenado (preprocesado + Gradient Boosting).
modelo = joblib.load(DIR_ARTEFACTOS / "price_model.pkl")

# Carga de los metadatos: listas de columnas y valores validos.
meta = joblib.load(DIR_ARTEFACTOS / "price_model_meta.pkl")

# Del meta extraemos las 6 columnas que el modelo espera, en orden.
COLUMNAS = meta["numericas"] + meta["categoricas"]

# A partir de los nombres one-hot del meta deducimos los valores
# validos de cada categorica. Por ejemplo, de "typology_grouped_flat"
# extraemos el valor "flat". Esto nos permite validar las entradas
# sin escribir las listas a mano.
def _valores_validos(prefijo: str) -> set:
    marca = prefijo + "_"
    return {
        nombre[len(marca):]
        for nombre in meta["nombres_transformados"]
        if nombre.startswith(marca)
    }

TIPOLOGIAS_VALIDAS = _valores_validos("typology_grouped")
ZONAS_VALIDAS = _valores_validos("zona_modelo")
MARGENES_VALIDOS = _valores_validos("river_bank")
