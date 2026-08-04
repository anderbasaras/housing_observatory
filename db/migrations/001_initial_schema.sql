-- =====================================================================
-- 001_initial_schema.sql
-- =====================================================================
--
-- QUE HACE ESTE FICHERO
-- Crea la estructura de tablas vacias donde luego guardaremos los datos.
--
-- COMO ESTA ORGANIZADO
-- Se usa un "modelo en estrella": una tabla central con los anuncios
-- (fact_listing) rodeada de tablas satelite que describen el CUANDO
-- (dim_time), el DONDE (dim_zone), el QUE tipo de vivienda
-- (dim_property_type) y la FIABILIDAD del dato (dim_data_quality).
--
-- Se separa asi para no repetir el nombre del barrio 800 veces:
-- se escribe una vez en dim_zone y los anuncios apuntan a el.
--
-- HAY UNA SEGUNDA TABLA DE DATOS
-- fact_official_rent guarda los precios REALES pagados segun la
-- estadistica oficial. La central guarda precios PEDIDOS en anuncios.
-- Comparar ambos es la aportacion principal del TFM.
--
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS core;
SET search_path TO core, public;

-- DIMENSIONES

-- Dimensión temporal
CREATE TABLE dim_time (
    time_id         SERIAL PRIMARY KEY,
    capture_date    DATE        NOT NULL,
    year            SMALLINT    NOT NULL,
    quarter         SMALLINT    NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    month           SMALLINT    NOT NULL CHECK (month BETWEEN 1 AND 12),
    is_snapshot     BOOLEAN     NOT NULL DEFAULT TRUE,
    UNIQUE (capture_date)
);

-- Dimensión territorial
CREATE TABLE dim_zone (
    zone_id             SERIAL PRIMARY KEY,
    neighbourhood       TEXT,
    municipality        TEXT        NOT NULL,
    municipality_ine    CHAR(5),
    river_bank          TEXT        CHECK (river_bank IN ('derecha','izquierda','interior')),
    in_functional_area  BOOLEAN     NOT NULL DEFAULT TRUE,
    centroid            GEOMETRY(Point, 4326),
    boundary            GEOMETRY(MultiPolygon, 4326),
    UNIQUE (municipality, neighbourhood)
);

-- Dimensión de tipología
CREATE TABLE dim_property_type (
    property_type_id    SERIAL PRIMARY KEY,
    typology            TEXT        NOT NULL,
    rooms_band          TEXT,
    area_band           TEXT,
    operation           TEXT        NOT NULL DEFAULT 'rent',
    UNIQUE (typology, rooms_band, area_band, operation)
);

-- Dimensión de calidad del dato
CREATE TABLE dim_data_quality (
    quality_id          SERIAL PRIMARY KEY,
    column_shift_flag   BOOLEAN     NOT NULL DEFAULT FALSE,
    neighbourhood_src   TEXT        NOT NULL CHECK (neighbourhood_src IN ('title','spatial','unknown')),
    area_imputed        BOOLEAN     NOT NULL DEFAULT FALSE,
    rooms_imputed       BOOLEAN     NOT NULL DEFAULT FALSE,
    UNIQUE (column_shift_flag, neighbourhood_src, area_imputed, rooms_imputed)
);

-- TABLAS DE HECHOS

-- Hecho principal: anuncio individual
CREATE TABLE fact_listing (
    listing_id          SERIAL PRIMARY KEY,
    fingerprint         CHAR(16)    NOT NULL,
    time_id             INTEGER     NOT NULL REFERENCES dim_time(time_id),
    zone_id             INTEGER     NOT NULL REFERENCES dim_zone(zone_id),
    property_type_id    INTEGER     NOT NULL REFERENCES dim_property_type(property_type_id),
    quality_id          INTEGER     NOT NULL REFERENCES dim_data_quality(quality_id),

    monthly_price       NUMERIC(9,2) NOT NULL CHECK (monthly_price > 0),
    area_sqm            NUMERIC(7,2)          CHECK (area_sqm > 0),
    price_per_sqm       NUMERIC(7,2) GENERATED ALWAYS AS (monthly_price / NULLIF(area_sqm,0)) STORED,
    n_rooms             SMALLINT              CHECK (n_rooms BETWEEN 0 AND 12),

    street_type         TEXT,
    street_number       SMALLINT,
    raw_title           TEXT        NOT NULL,

    -- Campos de auditoría (NO usar como variables de modelo)
    floor_level         SMALLINT,
    is_exterior         BOOLEAN,
    has_lift            BOOLEAN,

    -- Resultados de modelos
    predicted_price     NUMERIC(9,2),
    anomaly_score       NUMERIC(5,4) CHECK (anomaly_score BETWEEN 0 AND 1),

    ingested_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Hecho secundario: precio oficial de transacción (EMAL)
CREATE TABLE fact_official_rent (
    official_rent_id    SERIAL PRIMARY KEY,
    zone_id             INTEGER     NOT NULL REFERENCES dim_zone(zone_id),
    year                SMALLINT    NOT NULL,
    quarter             SMALLINT    CHECK (quarter BETWEEN 1 AND 4),
    mean_rent           NUMERIC(9,2),
    rent_per_sqm        NUMERIC(7,2),
    n_contracts         INTEGER,
    source              TEXT        NOT NULL DEFAULT 'EMAL',
    UNIQUE (zone_id, year, quarter, source)
);

-- INDICES Y COMENTARIOS

CREATE UNIQUE INDEX idx_listing_fingerprint ON fact_listing(fingerprint);
CREATE INDEX idx_listing_zone     ON fact_listing(zone_id);
CREATE INDEX idx_listing_price    ON fact_listing(price_per_sqm);
CREATE INDEX idx_zone_boundary    ON dim_zone USING GIST(boundary);
CREATE INDEX idx_zone_centroid    ON dim_zone USING GIST(centroid);
CREATE INDEX idx_official_zone_yr ON fact_official_rent(zone_id, year);

COMMENT ON TABLE  fact_listing IS 'Anuncios de alquiler. Captura transversal 1-2 julio 2022';
COMMENT ON COLUMN fact_listing.floor_level IS 'AUDITORIA: cobertura 3,2%, patron MNAR. No usar como feature';
COMMENT ON COLUMN fact_listing.has_lift IS 'AUDITORIA: cobertura 3,3%, patron MNAR. No usar como feature';
COMMENT ON TABLE  fact_official_rent IS 'EMAL. Renta pagada segun fianzas. Anual hasta 2023, trimestral desde 2024';