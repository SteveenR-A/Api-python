#!/usr/bin/env python3
"""Carga .env y prueba conexión directa a MariaDB usando las variables.
Imprime CONEXION_OK o la traza completa en caso de error.
"""
import os
from dotenv import load_dotenv
import mariadb
import traceback


def main():
    load_dotenv()
    host = os.getenv('DB_HOST')
    user = os.getenv('DB_USER')
    password = os.getenv('DB_PASSWORD')
    db = os.getenv('DB_NAME')

    print(f"Usando: host={host}, user={user}, db={db}")

    try:
        conn = mariadb.connect(host=host, user=user, password=password, database=db, connect_timeout=5)
        print("CONEXION_OK")
        conn.close()
    except Exception as e:
        print("CONEXION_FALLIDA")
        traceback.print_exc()


if __name__ == '__main__':
    main()
