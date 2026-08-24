-- =====================================================================
-- 003_zone_mapping.sql
--
-- QUE HACE
-- Crea la tabla que traduce los nombres de barrio que usan los
-- anuncios a los nombres oficiales de la estadistica de alquiler.
--
-- POR QUE HACE FALTA
-- Los portales inmobiliarios usan denominaciones comerciales
-- ("Zona Indautxu", "Abandoibarra-Guggenheim") que no coinciden con
-- las oficiales. Sin esta traduccion solo se pueden comparar 11 de
-- los 41 barrios.
--
-- EL CAMPO DE CONFIANZA
-- No todas las correspondencias son igual de seguras. Se distinguen
-- tres niveles para poder repetir el analisis solo con las seguras
-- y comprobar si los resultados cambian.
-- =====================================================================

SET search_path TO core, public;

CREATE TABLE IF NOT EXISTS dim_zone_mapping (
    mapping_id          SERIAL PRIMARY KEY,
    listing_name        TEXT        NOT NULL UNIQUE,
    official_name       TEXT,
    confidence          TEXT        NOT NULL
                        CHECK (confidence IN ('exact','high','medium','excluded')),
    rationale           TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE dim_zone_mapping IS
    'Correspondencia entre denominaciones comerciales de barrio y nomenclatura oficial EMAL';
COMMENT ON COLUMN dim_zone_mapping.confidence IS
    'exact: nombre identico | high: variante o pertenencia inequivoca | medium: requiere verificacion | excluded: sin correspondencia univoca';

INSERT INTO dim_zone_mapping (listing_name, official_name, confidence, rationale) VALUES
-- Coincidencia exacta de denominacion
('Casco Viejo',        'Casco Viejo',     'exact', 'Denominacion identica'),
('Ametzola',           'Ametzola',        'exact', 'Denominacion identica'),
('San Francisco',      'San Francisco',   'exact', 'Denominacion identica'),
('Zurbaran',           'Zurbaran',        'exact', 'Denominacion identica'),
('Zabala',             'Zabala',          'exact', 'Denominacion identica'),
('Iturralde',          'Iturralde',       'exact', 'Denominacion identica'),
('Uribarri',           'Uribarri',        'exact', 'Denominacion identica'),
('Begoña',             'Begoña',          'exact', 'Denominacion identica'),
('San Ignacio',        'San Ignacio',     'exact', 'Denominacion identica'),
('Solokoetxe',         'Solokoetxe',      'exact', 'Denominacion identica'),
('Bilbao la Vieja',    'Bilbao la Vieja', 'exact', 'Denominacion identica'),
('Bolueta',            'Bolueta',         'exact', 'Denominacion identica'),
('Miribilla',          'Miribilla',       'exact', 'Denominacion identica'),
('La Peña',            'La Peña',         'exact', 'Denominacion identica'),
('Atxuri',             'Atxuri',          'exact', 'Denominacion identica'),
('Zorrotza',           'Zorrotza',        'exact', 'Denominacion identica'),
('San Adrián',         'San Adrián',      'exact', 'Denominacion identica'),
('Olabeaga',           'Olabeaga',        'exact', 'Denominacion identica'),
('Arangoiti',          'Arangoiti',       'exact', 'Denominacion identica'),

-- Variantes ortograficas o denominaciones equivalentes
('Basurtu',                     'Basurto',         'high', 'Grafia en euskera del mismo barrio'),
('San Pedro de Deusto',         'Deustu / Deusto', 'high', 'Denominacion parroquial de Deusto'),
('Zona Indautxu',               'Indautxu',        'high', 'Prefijo comercial sobre denominacion oficial'),
('La Ribera-Ibarrekolanda',     'Ibarrekolanda',   'high', 'Denominacion compuesta que incorpora el oficial'),
('Irala',                       'Iralabarri',      'high', 'Forma abreviada de uso comun'),
('Santutxu-Basarrate',          'Santutxu',        'high', 'Basarrate es via interior de Santutxu'),
('Uretamendi-Betolaza-Peñaskal','Uretamendi',      'high', 'Agrupacion comercial de la misma ladera'),
('Masustegui',                  'Uretamendi',      'high', 'Masustegi se integra en el ambito de Uretamendi'),
('Rekalde Centro',              'Errekaldeberri',  'high', 'Grafia castellana de Errekalde'),

-- Asignaciones basadas en conocimiento territorial
('Abandoibarra-Guggenheim', 'Abando',   'high', 'Abandoibarra es desarrollo urbano dentro de Abando'),
('Ensanche-Moyua',          'Abando',   'high', 'Plaza Moyua es centro del Ensanche de Abando'),
('Albia',                   'Abando',   'high', 'Jardines de Albia se situan en Abando'),
('Plaza Circular',          'Abando',   'high', 'Plaza Circular pertenece a Abando'),
('Sabino Arana-Jesuitas',   'Indautxu', 'high', 'Ambito de Sabino Arana adscrito a Indautxu'),
('Campo Volantín-Castaños', 'Castaños', 'high', 'Denominacion comercial del ambito de Castaños'),
('Campuzano',               'Indautxu', 'high', 'Campuzano se integra en Indautxu'),
('Mirador de Bilbao-Maurice Ravel', 'Uribarri', 'high', 'Promocion residencial situada en Uribarri'),
('Altamira',                'Basurto',  'high', 'Altamira se adscribe al ambito de Basurto'),
('Artatzu-Larraskitu',      'Errekaldeberri', 'high', 'Larraskitu es zona alta de Rekalde'),

-- Requieren verificacion adicional
('Zabalburu-Diputación', 'Abando', 'medium',
 'Ambito fronterizo entre Abando, Ametzola y Errekaldeberri. Pendiente de verificacion por via'),
('Alhondiga', 'Abando', 'medium',
 'Alhondiga se situa en el limite entre Abando e Indautxu'),

-- Sin correspondencia univoca
('Otxarkoaga - Txurdinaga', NULL, 'excluded',
 'La denominacion agrupa dos barrios oficiales distintos sin posibilidad de asignacion univoca')
ON CONFLICT (listing_name) DO NOTHING;

-- ---------------------------------------------------------------------
-- Revision posterior por verificacion del viario
--
-- El examen de las vias contenidas en cada denominacion evidencio que
-- dos etiquetas comerciales agrupan barrios oficiales distintos.
-- ---------------------------------------------------------------------

UPDATE dim_zone_mapping
SET official_name = NULL, confidence = 'excluded',
    rationale = 'Denominacion que agrupa vias de tres barrios oficiales (Castanos, Matiko y Uribarri). Solo uno de treinta registros corresponde efectivamente a Castanos'
WHERE listing_name = 'Campo Volantín-Castaños';

UPDATE dim_zone_mapping
SET official_name = NULL, confidence = 'excluded',
    rationale = 'El ambito de Zabalburu no constituye barrio en la nomenclatura oficial, repartiendose entre Abando, Ametzola y Bilbao la Vieja. La verificacion por viario evidencia que la mayoria de registros no corresponde a Abando'
WHERE listing_name = 'Zabalburu-Diputación';