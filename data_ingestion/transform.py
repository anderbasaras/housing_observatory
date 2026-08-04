"""
QUE HACE ESTE FICHERO
Coge el CSV en bruto y lo convierte en datos limpios y ordenados.

QUE PROBLEMAS ARREGLA
1. El titulo del anuncio contiene el municipio, el barrio y la calle
   todos juntos en una frase. Los separa.
2. La columna "provincia" del origen esta mal, asi que se ignora
   por completo y todo lo geografico sale del titulo.
3. En 29 anuncios las columnas estan corridas un sitio porque el
   anuncio original no decia las habitaciones. Los detecta y rescata
   lo que se puede.
4. Hay anuncios repetidos. Les calcula una "huella digital" unica
   para poder eliminarlos.

NO GUARDA NADA EN LA BASE DE DATOS. Solo transforma.
"""

import hashlib
import re
import numpy as np
import pandas as pd

# --- Municipios del Area Funcional de Bilbao Metropolitano ---
# PENDIENTE: verificar la relacion oficial completa (35 municipios)
# frente a la fuente de la Diputacion Foral de Bizkaia

MUNICIPALITIES = {
    'abanto': 'Abanto y Ciervana', 'alonsotegi': 'Alonsotegi',
    'arrankudiaga': 'Arrankudiaga', 'arrigorriaga': 'Arrigorriaga',
    'barakaldo': 'Barakaldo', 'barrika': 'Barrika', 'basauri': 'Basauri',
    'berango': 'Berango', 'bilbao': 'Bilbao', 'derio': 'Derio',
    'erandio': 'Erandio', 'etxebarri': 'Etxebarri', 'galdakao': 'Galdakao',
    'getxo': 'Getxo', 'gorliz': 'Gorliz', 'larrabetzu': 'Larrabetzu',
    'leioa': 'Leioa', 'lemoiz': 'Lemoiz', 'lezama': 'Lezama', 'loiu': 'Loiu',
    'muskiz': 'Muskiz', 'ortuella': 'Ortuella', 'plentzia': 'Plentzia',
    'portugalete': 'Portugalete', 'santurtzi': 'Santurtzi', 'sestao': 'Sestao',
    'sondika': 'Sondika', 'sopela': 'Sopela', 'trapagaran': 'Valle de Trapaga',
    'urduliz': 'Urduliz', 'zamudio': 'Zamudio', 'zaratamo': 'Zaratamo',
    'zeberio': 'Zeberio', 'zierbena': 'Zierbena', 'usansolo': 'Usansolo',
}

#Nombres de barrios que se publican como si fueran municipios
ALIASES = {
    'algorta': 'Getxo', 'areeta': 'Getxo', 'las arenas': 'Getxo',
    'neguri': 'Getxo', 'romo': 'Getxo', 'sopelana': 'Sopela',
    'valle de trapaga': 'Valle de Trapaga', 'trapaga': 'Valle de Trapaga',
}

TYPOLOGY = {
    'piso': 'flat', 'ático': 'penthouse', 'atico': 'penthouse',
    'estudio': 'studio', 'dúplex': 'duplex', 'duplex': 'duplex',
    'casa': 'house', 'chalet': 'house', 'finca': 'house',
}

STREET_TYPES = ('calle', 'avenida', 'plaza', 'alameda', 'carretera',
                'paseo', 'camino', 'barrio', 'gran vía', 'via')

def norm(s):
    return re.sub(r'\s+', ' ', str(s)).strip()

def match_municipality(raw):
    k = norm(raw).lower()
    for alias, muni in ALIASES.items():
        if alias in k:
            return muni
    for key, muni in MUNICIPALITIES.items():
        if key in k:
            return muni
    return None

def parse_title(t):
    segs = [norm(x) for x in str(t).split(',') if norm(x)]
    out = {'municipality_raw': None, 'neighbourhood': None,
           'street_number': None, 'typology': None, 'street_type': None}
    if not segs:
        return out

    out['municipality_raw'] = segs[-1]          # ultimo = municipio
    if len(segs) >= 3:
        candidate = segs[-2]
        # Un barrio nunca es solo un numero: seria el portal
        if not candidate.isdigit():
            out['neighbourhood'] = candidate
        elif len(segs) >= 4 and not segs[-3].isdigit():
            out['neighbourhood'] = segs[-3]     # retrocede un segmento

    for s in segs[1:-1]:                        # numero suelto = portal
        if s.isdigit():
            out['street_number'] = int(s)
            break

    first = segs[0].lower()
    m = re.match(r'^(\S+)', first)
    if m:
        out['typology'] = TYPOLOGY.get(m.group(1))
    for st in STREET_TYPES:
        if re.search(rf'\ben\s+{st}\b', first):
            out['street_type'] = st
            break
    return out


def parse_shifted(v):
    t = str(v).lower()
    floor = None
    m = re.search(r'planta\s*(\d+)', t)
    if m:
        floor = int(m.group(1))
    elif 'bajo' in t:
        floor = 0
    ext = True if 'exterior' in t else (False if 'interior' in t else None)
    lift = True if re.search(r'con ascen', t) else (
        False if re.search(r'sin ascen', t) else None)
    return floor, ext, lift


def band(v, edges, labels):
    if pd.isna(v):
        return None
    for e, l in zip(edges, labels):
        if v <= e:
            return l
    return labels[-1]


def transform(path):
    df = pd.read_csv(path)
    print(f"  Filas en el CSV original: {len(df)}")

    df = df.drop_duplicates(subset=['titulo']).copy()
    print(f"  Tras eliminar titulos repetidos: {len(df)}")

    parsed = df['titulo'].apply(parse_title).apply(pd.Series)
    df = pd.concat([df.reset_index(drop=True),
                    parsed.reset_index(drop=True)], axis=1)

    df['municipality'] = df['municipality_raw'].apply(match_municipality)
    df = df[df['municipality'].notna()].copy()
    print(f"  En el Area Funcional de Bilbao: {len(df)}")

    df['monthly_price'] = pd.to_numeric(df['precio'], errors='coerce')
    df['area_sqm'] = pd.to_numeric(df['metros'], errors='coerce')
    df['n_rooms'] = pd.to_numeric(df['habitaciones'], errors='coerce')

    # Filas con columnas corridas
    df['column_shift_flag'] = df['area_sqm'].isna() & df['metros'].notna()
    df['floor_level'] = None
    df['is_exterior'] = None
    df['has_lift'] = None
    shifted = df.loc[df['column_shift_flag'], 'metros'].apply(parse_shifted)
    if len(shifted):
        df.loc[df['column_shift_flag'],
               ['floor_level', 'is_exterior', 'has_lift']] = \
            pd.DataFrame(shifted.tolist(), index=shifted.index).values
    print(f"  Filas con columnas corridas rescatadas: "
          f"{df['column_shift_flag'].sum()}")

    df['rooms_band'] = df['n_rooms'].apply(
        lambda v: band(v, [1, 2, 3, 4], ['1', '2', '3', '4', '5+']))
    df['area_band'] = df['area_sqm'].apply(
        lambda v: band(v, [50, 80, 120], ['<50', '50-80', '80-120', '>120']))

    df['fingerprint'] = df.apply(lambda r: hashlib.sha256(
        f"{norm(r['titulo']).lower()}|{r['monthly_price']}|{r['area_sqm']}"
        .encode()).hexdigest()[:16], axis=1)
    df = df.drop_duplicates(subset=['fingerprint'])

    df['neighbourhood_src'] = np.where(
        df['neighbourhood'].notna(), 'title', 'unknown')
    df['area_imputed'] = False
    df['rooms_imputed'] = False

    print(f"  REGISTROS FINALES: {len(df)}")
    return df