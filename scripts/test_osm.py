"""
QUE HACE ESTE FICHERO
Pregunta a OpenStreetMap que estaciones de metro, tren y equipamientos
hay en Bilbao y alrededores. Solo mira, no guarda nada.

QUE ES OPENSTREETMAP
Un mapa colaborativo mundial, como una Wikipedia de mapas. Cualquiera
puede consultarlo gratis. Tiene etiquetados los transportes, hospitales,
colegios y comercios.
"""

import osmnx as ox

LUGAR = "Bilbao, Bizkaia, Spain"

print("Consultando OpenStreetMap. Puede tardar un minuto...")
print()

consultas = [
    ("Metro",      {"railway": "station", "station": "subway"}),
    ("Tren",       {"railway": "station"}),
    ("Hospitales", {"amenity": "hospital"}),
    ("Colegios",   {"amenity": "school"}),
    ("Farmacias",  {"amenity": "pharmacy"}),
]

for nombre, etiquetas in consultas:
    try:
        g = ox.features_from_place(LUGAR, tags=etiquetas)
        print(f"  {nombre:12s} {len(g):4d} elementos")
    except Exception as e:
        print(f"  {nombre:12s} ERROR: {e}")
