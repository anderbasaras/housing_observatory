-- =====================================================================
-- 004_view_listing_mapped.sql
--
-- QUE HACE
-- Crea una "vista": una consulta guardada que se comporta como una
-- tabla. Cada vez que se consulta, traduce al vuelo el barrio del
-- anuncio a su nombre oficial usando la tabla de correspondencias.
--
-- POR QUE UNA VISTA Y NO CAMBIAR LOS DATOS
-- 1. El dato original queda intacto y se puede volver atras.
-- 2. Permite comparar escenarios: con o sin las correspondencias
--    dudosas, con o sin determinados ambitos.
-- 3. Si se corrige una correspondencia, no hay que recargar nada.
-- =====================================================================

SET search_path TO core, public;

CREATE OR REPLACE VIEW v_listing_mapped AS
SELECT
    f.listing_id,
    f.fingerprint,
    f.monthly_price,
    f.area_sqm,
    f.price_per_sqm,
    f.n_rooms,
    f.raw_title,
    f.street_type,
    z.municipality,
    z.neighbourhood                                AS neighbourhood_raw,
    COALESCE(m.official_name, z.neighbourhood)     AS neighbourhood_official,
    COALESCE(m.confidence, 'unmapped')             AS mapping_confidence,
    pt.typology,
    pt.rooms_band,
    pt.area_band,
    dq.column_shift_flag
FROM core.fact_listing f
JOIN core.dim_zone z            ON f.zone_id = z.zone_id
LEFT JOIN core.dim_zone_mapping m ON m.listing_name = z.neighbourhood
JOIN core.dim_property_type pt  ON f.property_type_id = pt.property_type_id
JOIN core.dim_data_quality dq   ON f.quality_id = dq.quality_id;

COMMENT ON VIEW v_listing_mapped IS
    'Anuncios con barrio normalizado a nomenclatura oficial EMAL. Conserva la denominacion original y el nivel de confianza de la correspondencia';