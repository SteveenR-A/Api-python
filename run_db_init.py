import os
from dotenv import load_dotenv
import mariadb

load_dotenv()
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_NAME = os.getenv('DB_NAME', 'inventario')
SQL_FILE = os.path.join(os.path.dirname(__file__), 'db_init.sql')

print(f"Leyendo SQL desde: {SQL_FILE}")
if not os.path.exists(SQL_FILE):
    raise SystemExit(f"No existe el archivo {SQL_FILE}")

with open(SQL_FILE, 'r', encoding='utf-8') as f:
    sql = f.read()

# Conectar sin especificar database para permitir DROP/CREATE DATABASE
try:
    conn = mariadb.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        autocommit=True,
        connect_timeout=5
    )
except Exception as e:
    print('ERROR: no se pudo conectar al servidor MariaDB/MySQL:')
    print(repr(e))
    raise SystemExit(1)

cur = conn.cursor()

# Ejecutar sentencias: dividir por ; y ejecutar cada bloque que no sea vacío
statements = [s.strip() for s in sql.split(';') if s.strip()]
print(f"Encontradas {len(statements)} sentencias (aprox). Ejecución...\n")

for i, stmt in enumerate(statements, start=1):
    try:
        cur.execute(stmt)
        print(f"[{i}/{len(statements)}] OK")
    except Exception as e:
        print(f"[{i}/{len(statements)}] ERROR al ejecutar sentencia:\n{stmt[:200]}...\n{repr(e)}\n")

print('\nEjecución finalizada. Comprueba con: mariadb -u {DB_USER} -p<pwd> -e "USE inventario; SHOW TABLES;"')
cur.close()
conn.close()
