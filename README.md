# API Flask - Proyecto
# Proyecto: API de Inventario (compacta)

Este repositorio contiene una API REST compacta (`app_compacto.py`) y una interfaz gráfica cliente (`gui.py`) para gestionar un inventario simple.

Archivos principales

- `app_compacto.py` — Servidor Flask auto-contenido (CRUD, login, reportes). Lee la configuración desde `.env`.
- `gui.py` — Interfaz de escritorio basada en CustomTkinter que consume la API.
- `requirements.txt` — Dependencias Python necesarias.
- `.env` — Variables de entorno con credenciales de la DB (NO subir a repositorios públicos).
- `db_init.sql` — (opcional) script SQL para (re)crear la base `inventario`.
- `run.sh` — Script cómodo para arrancar la API o la GUI desde el venv.

Requisitos

- Python 3.8+
- MariaDB/MySQL en el host o accesible vía red
- Un entorno virtual (recomendado)

Instalación rápida

1. Crea y activa un entorno virtual:

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Instala dependencias:

```bash
pip install -r requirements.txt
```

3. Configura tu `.env` en la raíz con las credenciales de base de datos, por ejemplo:

```
DB_HOST=127.0.0.1
DB_USER=root
DB_PASSWORD=1234
DB_NAME=inventario
```

4. (Opcional) Inicializa la base de datos con `db_init.sql` si quieres partir de cero:

```bash
# usando cliente mysql/mariadb
mariadb -u root -p1234 < db_init.sql
# o
mysql -u root -p1234 < db_init.sql
```

Uso

- Arrancar la API compacta:

```bash
./run.sh api
# o
python app_compacto.py
```

- Arrancar la GUI (intenta levantar la API si no está en marcha):

```bash
./run.sh gui
# o
python gui.py
```

Exportar reportes a Excel
-------------------------

La interfaz de reportes incluye un botón "Exportar a Excel" que permite guardar el reporte actual en un archivo .xlsx. Para usarlo:

1. Abre la GUI y ve a "Reportes" → selecciona el tipo de reporte que quieras (Ventas, Compras, Ganancias, Existencias, etc.).
2. Filtra por fechas si aplica y genera el reporte.
3. Haz clic en el botón "Exportar a Excel" (arriba a la derecha en la ventana del reporte) y elige la ubicación y el nombre del archivo.

Dependencias
------------
Para que la exportación a Excel funcione, instala las siguientes dependencias además de las ya listadas:

```bash
pip install pandas openpyxl
```

Esto también está incluido en `requirements.txt`.

Notas

- `gui.py` intenta arrancar `app_compacto.py` en background si no detecta la API en `API_URL`.
- Mantén tu `.env` seguro y no lo subas a repositorios públicos.

Problemas comunes

- Si la GUI muestra errores de conexión, verifica que la API responde en `http://127.0.0.1:5000/health`.
- Si hay errores de autenticación, usa el botón para crear un usuario de prueba (`admin` / `admin`) desde la ventana de login y luego haz login.

Contacto

Si necesitas que automatice tests, cree scripts adicionales o archive archivos no utilizados, dímelo y lo hago.
