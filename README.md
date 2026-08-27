# Observatorio Inteligente de Vivienda en Alquiler

**Bilbao Metropolitano — Predicción de precios, detección de anomalías y análisis territorial**

TFM del Máster en Data Science, Big Data & Business Analytics (UCM).

Plataforma de datos end-to-end para el análisis del mercado del alquiler
residencial en el Área Funcional de Bilbao Metropolitano.

## Contexto

El País Vasco queda excluido del Sistema Estatal de Referencia del Precio
del Alquiler por su régimen foral en materia catastral, al construirse dicho
índice sobre información del Catastro estatal.

Este proyecto cubre ese vacío con una aportación diferencial: **comparar el
precio que se pide en los anuncios con el que realmente se paga**, según los
depósitos de fianza recogidos por la estadística oficial vasca.

## Resultados principales

| Hallazgo | Valor |
|---|---|
| Brecha media entre precio de oferta y de transacción | **8,50 %** |
| Dispersión de la brecha entre barrios | ±8,39 puntos |
| Barrios de Bilbao con comparación posible | 21 |
| Error del modelo de predicción de precio (MAPE) | **12,81 %** |
| Precisión del detector de anomalías (10 primeros casos) | **100 %** |

La brecha presenta una variabilidad entre barrios equivalente a su propia media.
Se exploró la hipótesis de que fuera mayor en las zonas de menor renta y los
datos no la sostienen.

## Datos

| Fuente | Aporta | Volumen |
|---|---|---|
| Anuncios de alquiler (Kaggle) | Precio de oferta a nivel de anuncio | 79.749 procesados, 888 en el ámbito |
| EMAL — Gobierno Vasco | Precio de transacción por barrio | 505 registros, 2016–2025 |
| Open Data Euskadi | Límites municipales | 35 municipios |
| GeoBilbao | Límites de barrio | 46 barrios |

Captura de anuncios: julio de 2022. Los datos en bruto no se redistribuyen en
este repositorio.

## Arquitectura

```
Fuentes → Ingesta (Python) → PostgreSQL + PostGIS (modelo estrella)
                           → MongoDB (datos crudos y auditoría)
                           → Procesamiento y variables derivadas
                           → Modelos (precio, anomalías)
                           → API y visualización
```

## Estado

| Fase | Estado |
|---|---|
| 0 — Alcance y criterios de éxito | Completada |
| 1 — Modelado de datos e ingesta | Completada |
| 2 — Procesamiento y enriquecimiento | Completada |
| 3 — Modelización | Completada |
| 4 — Visualización | En curso |
| 5 — API y monitorización | Pendiente |

## Stack

Python 3.12 · PostgreSQL 17 + PostGIS 3.5 · MongoDB 8 · scikit-learn · SHAP ·
GeoPandas · FastAPI

## Estructura

- `data_ingestion/` — transformación y carga de las cuatro fuentes
- `db/migrations/` — esquema de base de datos versionado
- `notebooks/` — análisis exploratorio y modelización
- `models/artifacts/` — modelo entrenado
- `scripts/` — verificación de conexiones y utilidades
- `docs/` — documentación del proyecto

## Configuración

```bash
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Copiar `.env.example` a `.env` y completar las credenciales.

Verificar la instalación con `python scripts/test_conexion.py`.

## Notas metodológicas

El proyecto documenta varias incidencias de integración que no se manifiestan
como error de ejecución: generación de combinaciones territoriales inexistentes,
tratamiento de valores nulos en restricciones de unicidad, declaración errónea
del sistema de referencia en cartografía oficial, y discordancia de nomenclatura
entre fuentes públicas del mismo territorio.

La resolución de esta última —41 denominaciones comerciales de barrio frente a
la nomenclatura administrativa— constituye una aportación metodológica del
trabajo y exigió verificación mediante el viario.