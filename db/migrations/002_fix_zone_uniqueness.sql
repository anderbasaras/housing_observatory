-- =====================================================================
-- 002_fix_zone_uniqueness.sql
--
-- PROBLEMA QUE ARREGLA
-- En PostgreSQL dos valores NULL no se consideran iguales. Por eso la
-- restriccion UNIQUE(municipality, neighbourhood) permitia crear varias
-- filas para el mismo municipio sin barrio, y se duplicaron zonas: una
-- fila creada al cargar los anuncios y otra al cargar la EMAL.
--
-- SOLUCION
-- Primero se fusionan las filas duplicadas, repuntando los datos que
-- apuntaban a ellas. Despues se crea un indice unico parcial que
-- impide que el problema vuelva a producirse.
-- =====================================================================

SET search_path TO core, public;

-- ---------------------------------------------------------------------
-- PASO 1: fusionar las filas duplicadas de municipio
-- Se conserva la de menor identificador.
-- ---------------------------------------------------------------------

CREATE TEMP TABLE zone_merge AS
SELECT municipality,
       MIN(zone_id) AS keep_id
FROM core.dim_zone
WHERE neighbourhood IS NULL
GROUP BY municipality
HAVING COUNT(*) > 1;

-- Repuntar los anuncios hacia la fila que se conserva
UPDATE core.fact_listing f
SET zone_id = m.keep_id
FROM core.dim_zone z
JOIN zone_merge m ON m.municipality = z.municipality
WHERE f.zone_id = z.zone_id
  AND z.neighbourhood IS NULL
  AND f.zone_id <> m.keep_id;

-- Repuntar los precios oficiales
UPDATE core.fact_official_rent o
SET zone_id = m.keep_id
FROM core.dim_zone z
JOIN zone_merge m ON m.municipality = z.municipality
WHERE o.zone_id = z.zone_id
  AND z.neighbourhood IS NULL
  AND o.zone_id <> m.keep_id;

-- Consolidar codigo INE y geometria en la fila que se conserva
UPDATE core.dim_zone k
SET municipality_ine = COALESCE(k.municipality_ine, src.municipality_ine),
    boundary        = COALESCE(k.boundary, src.boundary),
    centroid        = COALESCE(k.centroid, src.centroid)
FROM core.dim_zone src
JOIN zone_merge m ON m.municipality = src.municipality
WHERE k.zone_id = m.keep_id
  AND src.neighbourhood IS NULL
  AND src.zone_id <> m.keep_id;

-- Eliminar las filas sobrantes
DELETE FROM core.dim_zone z
USING zone_merge m
WHERE z.municipality = m.municipality
  AND z.neighbourhood IS NULL
  AND z.zone_id <> m.keep_id;

DROP TABLE zone_merge;

-- ---------------------------------------------------------------------
-- PASO 2: impedir que vuelva a ocurrir
-- Indice unico parcial: solo afecta a las filas de municipio.
-- ---------------------------------------------------------------------

CREATE UNIQUE INDEX IF NOT EXISTS idx_zone_municipality_only
    ON dim_zone (municipality)
    WHERE neighbourhood IS NULL;