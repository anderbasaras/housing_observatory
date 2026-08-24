-- =====================================================================
-- 006_river_bank.sql
--
-- QUE HACE
-- Clasifica cada municipio segun su posicion respecto a la ria del
-- Nervion.
--
-- POR QUE IMPORTA
-- La division entre ambas margenes es el eje socioeconomico historico
-- del Gran Bilbao. La margen izquierda concentro la industria pesada y
-- la vivienda obrera; la derecha, la residencia burguesa. Esa division
-- sigue explicando buena parte de la diferencia de precios observada.
--
-- CATEGORIAS
--   capital    : Bilbao. Se clasifica aparte por cuanto la ria lo
--                atraviesa, no discurriendo por ninguna de sus margenes
--   derecha    : municipios de la margen derecha
--   izquierda  : municipios de la margen izquierda
--   txorierri  : corredor del Txorierri, al norte y ajeno a la ria
--   interior   : municipios de valle interior, aguas arriba
-- =====================================================================

SET search_path TO core, public;

-- Ampliar el dominio admitido antes de asignar valores
ALTER TABLE dim_zone DROP CONSTRAINT IF EXISTS dim_zone_river_bank_check;
ALTER TABLE dim_zone ADD CONSTRAINT dim_zone_river_bank_check
    CHECK (river_bank IN ('capital','derecha','izquierda','txorierri','interior'));

UPDATE dim_zone SET river_bank = 'capital'
WHERE municipality = 'Bilbao';

UPDATE dim_zone SET river_bank = 'derecha'
WHERE municipality IN ('Getxo','Leioa','Erandio','Sopela','Berango',
                       'Plentzia','Gorliz','Barrika','Urduliz','Lemoiz');

UPDATE dim_zone SET river_bank = 'izquierda'
WHERE municipality IN ('Barakaldo','Sestao','Portugalete','Santurtzi',
                       'Ortuella','Muskiz','Zierbena','Valle de Trapaga',
                       'Abanto y Ciervana');

UPDATE dim_zone SET river_bank = 'txorierri'
WHERE municipality IN ('Loiu','Sondika','Derio','Zamudio','Lezama','Larrabetzu');

UPDATE dim_zone SET river_bank = 'interior'
WHERE municipality IN ('Basauri','Galdakao','Arrigorriaga','Etxebarri',
                       'Zaratamo','Zeberio','Arrankudiaga-Zollo',
                       'Ugao-Miraballes','Alonsotegi');