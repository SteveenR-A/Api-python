import os
from dotenv import load_dotenv

# Carga las variables de entorno desde el archivo .env
load_dotenv()

# Lee las variables y las asigna a constantes de Python
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
# Por defecto usamos 'inventario' (coincide con el esquema del proyecto)
DB_NAME = os.getenv("DB_NAME", "inventario")


# Normalizar 'localhost' a '127.0.0.1' para evitar que algunos conectores intenten
# usar socket UNIX en lugar de TCP, lo que puede causar errores en entornos donde
# el servidor MariaDB escucha en TCP. Esto respeta la variable de entorno pero
# hace el cambio transparente si el usuario puso 'localhost'.
if DB_HOST == 'localhost':
	DB_HOST = '127.0.0.1'

