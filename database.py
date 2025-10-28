import os
import time
from typing import Optional
import mariadb
from dotenv import load_dotenv


load_dotenv()


class DatabaseConnectionError(Exception):
    pass


def create_connection(host: Optional[str] = None, user: Optional[str] = None, password: Optional[str] = None, database: Optional[str] = None, connect_timeout: int = 5):
    """Crea y retorna una conexión a la base de datos MariaDB.

    Si alguno de los parámetros es None, se leerá desde las variables de entorno
    (`DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`). Esto hace que la conexión
    use directamente las variables definidas en `.env`.
    """
    host = host or os.getenv('DB_HOST', '127.0.0.1')
    # Normalizar 'localhost' a TCP loopback para evitar usar socket UNIX accidentalmente
    if host == 'localhost':
        host = '127.0.0.1'
    user = user or os.getenv('DB_USER')
    password = password or os.getenv('DB_PASSWORD')
    database = database or os.getenv('DB_NAME')

    try:
        conn = mariadb.connect(
            user=user,
            password=password,
            host=host,
            database=database,
            connect_timeout=connect_timeout
        )
        return conn
    except mariadb.Error as e:
        raise DatabaseConnectionError(str(e))


def get_connection(retries: int = 1, delay: float = 0.5) -> Optional[object]:
    """Obtiene una conexión, con reintentos simples.

    Por defecto realiza 1 intento. Para mayor resiliencia, aumentar `retries`.
    Devuelve la conexión si tiene éxito o lanza DatabaseConnectionError si falla.
    """
    last_exc = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            return create_connection()
        except DatabaseConnectionError as e:
            last_exc = e
            if attempt < retries:
                time.sleep(delay)
    # Si llegamos aquí, todos los intentos fallaron
    raise DatabaseConnectionError(f"No se pudo conectar a la base de datos después de {retries} intentos: {last_exc}")

