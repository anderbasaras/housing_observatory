"""
QUE HACE ESTE FICHERO
Comprueba que el ordenador puede hablar con la base de datos.

COMO FUNCIONA
Lee la contraseña del fichero .env (que nunca se sube a internet),
se conecta a la base y le pregunta su versión. Si responde, todo bien.
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
url = os.getenv("DATABASE_URL")

if not url:
    print("ERROR: no se encuentra DATABASE_URL en el fichero .env")
    exit(1)

print(f"Conectando a: {url.split('@')[-1][:45]}...")

try:
    engine = create_engine(url)
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version()")).scalar()
        postgis = conn.execute(text("SELECT PostGIS_Version()")).scalar()
    print("\nCONEXION CORRECTA")
    print(f"  PostgreSQL: {version.split(',')[0]}")
    print(f"  PostGIS:    {postgis}")
except Exception as e:
    print(f"\nERROR DE CONEXION:\n{e}")
