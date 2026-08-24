-- =====================================================================
-- 005_clean_impute.sql
--
-- QUE HACE
-- 1. Anade columnas para marcar registros problematicos
-- 2. Excluye dos registros mal geolocalizados
-- 3. Rellena los valores que faltan con criterio documentado
-- 4. Marca los valores extremos sin borrarlos
--
-- POR QUE MARCAR EN VEZ DE BORRAR
-- Los valores extremos son precisamente lo que debe detectar el
-- modulo de anomalias de la fase siguiente. Si se eliminan ahora,
-- ese modulo se queda sin casos que encontrar.
-- =====================================================================

SET search_path TO core, public;

-- ---------------------------------------------------------------------
-- PASO 1: columnas de control
-- ---------------------------------------------------------------------

ALTER TABLE fact_listing
    ADD COLUMN IF NOT EXISTS is_excluded     BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS exclusion_note  TEXT,
    ADD COLUMN IF NOT EXISTS is_outlier      BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS outlier_note    TEXT;

COMMENT ON COLUMN fact_listing.is_excluded IS
    'Registro descartado del analisis por error demostrable en el dato de origen';
COMMENT ON COLUMN fact_listing.is_outlier IS
    'Valor extremo conservado. No implica error: alimenta el modulo de deteccion de anomalias';

-- ---------------------------------------------------------------------
-- PASO 2: exclusion por error geografico
--
-- Dos registros situados en Castromocho (Palencia) fueron asignados a
-- Getxo por el campo de provincia del origen, ya identificado como no
-- fiable. El titulo del anuncio permite constatar el error.
-- ---------------------------------------------------------------------

UPDATE fact_listing
SET is_excluded = TRUE,
    exclusion_note = 'Localizado en Castromocho (Palencia). Asignacion territorial erronea del proceso de extraccion'
WHERE raw_title ILIKE '%castromocho%';

-- ---------------------------------------------------------------------
-- PASO 3: imputacion del numero de habitaciones
--
-- Los registros sin dato corresponden en su practica totalidad a
-- estudios. La ausencia no es aleatoria: un estudio carece de
-- habitaciones diferenciadas, por lo que los portales omiten
-- sistematicamente el campo. Se asigna cero, que no constituye una
-- estimacion sino el valor que corresponde por definicion.
-- ---------------------------------------------------------------------

UPDATE fact_listing f
SET n_rooms = 0
FROM dim_property_type pt
WHERE f.property_type_id = pt.property_type_id
  AND f.n_rooms IS NULL
  AND pt.typology = 'studio';

-- El atico y el duplex sin dato reciben la mediana de su tipologia
UPDATE fact_listing f
SET n_rooms = 2
FROM dim_property_type pt
WHERE f.property_type_id = pt.property_type_id
  AND f.n_rooms IS NULL
  AND pt.typology IN ('penthouse', 'duplex');

-- ---------------------------------------------------------------------
-- PASO 4: superficie de las tipologias no afectadas en bloque
--
-- El atico y el duplex carentes de superficie reciben la mediana
-- observada en su propia tipologia.
-- ---------------------------------------------------------------------

UPDATE fact_listing f
SET area_sqm = 80
FROM dim_property_type pt
WHERE f.property_type_id = pt.property_type_id
  AND f.area_sqm IS NULL
  AND pt.typology = 'penthouse';

UPDATE fact_listing f
SET area_sqm = 100
FROM dim_property_type pt
WHERE f.property_type_id = pt.property_type_id
  AND f.area_sqm IS NULL
  AND pt.typology = 'duplex';

-- ---------------------------------------------------------------------
-- PASO 5: los estudios quedan sin superficie imputada
--
-- La totalidad de los veintisiete estudios del conjunto carece de
-- superficie, como consecuencia del desplazamiento de columnas que
-- afecta de forma sistematica a esta tipologia. No existe por tanto
-- mediana propia que sirva de referencia.
--
-- Se ha descartado la imputacion a partir del precio y del valor
-- unitario de la zona, por cuanto introduciria circularidad en el
-- calculo posterior del precio por metro cuadrado, magnitud sobre la
-- que se sustenta el analisis comparativo del trabajo.
--
-- Se opta por conservar el valor ausente y hacerlo constar. Los
-- estudios permanecen disponibles para los analisis basados en precio
-- total y quedan excluidos de aquellos que requieren superficie.
-- ---------------------------------------------------------------------

UPDATE fact_listing f
SET outlier_note = 'Superficie no disponible: tipologia afectada en bloque por el desplazamiento de columnas'
FROM dim_property_type pt
WHERE f.property_type_id = pt.property_type_id
  AND f.area_sqm IS NULL
  AND pt.typology = 'studio';

-- ---------------------------------------------------------------------
-- PASO 6: marcado de valores extremos
--
-- Se marcan sin eliminar. Constituyen el material sobre el que debe
-- operar el modulo de deteccion de anomalias.
-- ---------------------------------------------------------------------

UPDATE fact_listing
SET is_outlier = TRUE,
    outlier_note = COALESCE(outlier_note || '. ', '') ||
                   'Valor unitario fuera del intervalo de consistencia'
WHERE is_excluded = FALSE
  AND price_per_sqm IS NOT NULL
  AND (price_per_sqm < 5 OR price_per_sqm > 28);

UPDATE fact_listing
SET is_outlier = TRUE,
    outlier_note = COALESCE(outlier_note || '. ', '') ||
                   'Superficie fuera del intervalo de consistencia'
WHERE is_excluded = FALSE
  AND (area_sqm < 25 OR area_sqm > 300);