# Observatorio Inteligente de Vivienda en Alquiler

TFM del Máster en Data Science, Big Data & Business Analytics (UCM).

Plataforma de datos end-to-end para el análisis del mercado del alquiler
residencial en el Área Funcional de Bilbao Metropolitano: predicción de
precios, detección de anomalías y análisis territorial.

## Contexto

El País Vasco queda excluido del Sistema Estatal de Referencia del Precio
del Alquiler por su régimen foral en materia catastral. Este proyecto
cubre ese vacío comparando precios de oferta con precios de transacción
real a escala de barrio.

## Estado

En desarrollo — Fase 1: modelado de datos.

## Stack

Python 3.12 · PostgreSQL 17 + PostGIS 3.5 · MongoDB · PySpark · FastAPI

## Estructura

- `db/migrations/` — esquema de base de datos
- `data_ingestion/` — scripts de carga
- `docs/` — documentación del proyecto
- `notebooks/` — análisis exploratorio

## Configuración

Copiar `.env.example` a `.env` y completar las credenciales.