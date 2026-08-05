"""
QUE HACE ESTE FICHERO
Comprueba que el ordenador puede hablar con MongoDB Atlas.
Es el equivalente a test_conexion.py pero para la base NoSQL.

COMO FUNCIONA
Lee la direccion del cluster del fichero .env, se conecta y le manda
un "ping". Si contesta, la conexion esta bien montada.
"""

import os
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError

load_dotenv()
uri = os.getenv("MONGODB_URI")

if not uri:
    print("ERROR: no se encuentra MONGODB_URI en el fichero .env")
    exit(1)

print(f"Conectando a: {uri.split('@')[-1][:45]}...")

try:
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    client.admin.command("ping")

    info = client.server_info()
    print("\nCONEXION CORRECTA")
    print(f"  MongoDB: version {info['version']}")
    print(f"  Bases de datos existentes: {client.list_database_names()}")

except PyMongoError as e:
    print(f"\nERROR DE CONEXION:\n{e}")
