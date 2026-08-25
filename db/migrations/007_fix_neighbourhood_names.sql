-- ---------------------------------------------------------------------
-- Fusion de los duplicados restantes
--
-- Tres barrios quedaron registrados dos veces: una desde la
-- cartografia (con geometria) y otra desde la estadistica o el
-- scraping (con datos). Se consolidan en un unico registro.
-- ---------------------------------------------------------------------

-- Iturrigorri - Peñascal
UPDATE dim_zone k SET boundary = d.boundary, centroid = d.centroid
FROM dim_zone d
WHERE k.municipality = 'Bilbao' AND k.neighbourhood = 'Iturrigorri - Peñascal'
  AND d.municipality = 'Bilbao' AND d.neighbourhood = 'ITURRIGORRI-PEÑASCAL';

DELETE FROM dim_zone
WHERE municipality = 'Bilbao' AND neighbourhood = 'ITURRIGORRI-PEÑASCAL';

-- Masustegi - Monte Caramelo
UPDATE dim_zone k SET boundary = d.boundary, centroid = d.centroid
FROM dim_zone d
WHERE k.municipality = 'Bilbao' AND k.neighbourhood = 'Masustegi - Monte Caramelo'
  AND d.municipality = 'Bilbao' AND d.neighbourhood = 'MASUSTEGI-MONTE CARAMELO';

DELETE FROM dim_zone
WHERE municipality = 'Bilbao' AND neighbourhood = 'MASUSTEGI-MONTE CARAMELO';

-- Basurto: la cartografia usa la grafia en euskera (Basurtu) y la
-- estadistica la castellana (Basurto). Los anuncios apuntan a la
-- primera y los datos oficiales a la segunda.
UPDATE fact_listing f SET zone_id = k.zone_id
FROM dim_zone k, dim_zone d
WHERE k.municipality = 'Bilbao' AND k.neighbourhood = 'Basurto'
  AND d.municipality = 'Bilbao' AND d.neighbourhood = 'Basurtu'
  AND f.zone_id = d.zone_id;

UPDATE dim_zone k SET boundary = d.boundary, centroid = d.centroid
FROM dim_zone d
WHERE k.municipality = 'Bilbao' AND k.neighbourhood = 'Basurto'
  AND d.municipality = 'Bilbao' AND d.neighbourhood = 'Basurtu';

DELETE FROM dim_zone
WHERE municipality = 'Bilbao' AND neighbourhood = 'Basurtu';

-- La correspondencia de Basurtu deja de ser necesaria
DELETE FROM dim_zone_mapping WHERE listing_name = 'Basurtu';