import mariadb
import sys
from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME


def create_connection():
    """Crea y retorna una conexión a la base de datos MariaDB."""
    try:
        conn = mariadb.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            database=DB_NAME
        )
        return conn
    except mariadb.Error as e:
        print(f"Error al conectar a MariaDB: {e}")
        sys.exit(1)


# Alias para compatibilidad con código previo/tests que esperan get_connection
def get_connection():
    return create_connection()
