import os
import time
from typing import Optional
import mariadb
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_bcrypt import Bcrypt
from datetime import datetime

# Cargar variables de entorno desde .env
load_dotenv()

# --- Parte de Database ---

class DatabaseConnectionError(Exception):
    pass

def create_connection(host: Optional[str] = None, user: Optional[str] = None, password: Optional[str] = None, database: Optional[str] = None, connect_timeout: int = 5):
    """
    Crea y retorna una conexión a la base de datos MariaDB.
    Lee de variables de entorno si los argumentos son None.
    """
    host = host or os.getenv('DB_HOST', '127.0.0.1')
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
    """Obtiene una conexión, con reintentos simples."""
    last_exc = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            return create_connection()
        except DatabaseConnectionError as e:
            last_exc = e
            if attempt < retries:
                
                time.sleep(delay)
    raise DatabaseConnectionError(f"No se pudo conectar a la base de datos después de {retries} intentos: {last_exc}")

# --- Parte de la Aplicación (API) ---

def create_app():
    app = Flask(__name__)
    bcrypt = Bcrypt(app)

    def row_to_dict(cur, row):
        """Convertir una fila (tuple) a dict usando cur.description como claves."""
        if row is None:
            return None
        cols = [d[0] for d in getattr(cur, 'description', [])]
        return {cols[i]: row[i] for i in range(min(len(cols), len(row)))}

    def normalize_product(prod: dict) -> dict:
        """Asegura tipos consistentes para los campos de Productos.

        Convierte precios a float y stocks a int para evitar que la GUI muestre valores
        con punto decimal cuando corresponda.
        """
        if not prod:
            return prod
        p = prod.copy()
        # Campos numéricos que deben ser float
        for f in ('precio_compra', 'porcentaje_ganancia', 'precio_venta'):
            try:
                p[f] = float(p.get(f)) if p.get(f) is not None else 0.0
                # si es entero exacto, mantener como número con .0 (la GUI puede formatear)
            except Exception:
                p[f] = 0.0
        # Campos que deben ser int
        for f in ('stock', 'stock_minimo', 'id_proveedor'):
            try:
                val = p.get(f)
                if val is None:
                    p[f] = None if f == 'id_proveedor' else 0
                else:
                    p[f] = int(val)
            except Exception:
                p[f] = 0 if f != 'id_proveedor' else None
        # Asegurar id como int si existe
        if 'id' in p and p['id'] is not None:
            try:
                p['id'] = int(p['id'])
            except Exception:
                pass
        return p

    def get_last_insert_id(cur, conn=None):
        """Fallback para obtener el último id insertado en caso cursor.lastrowid sea None.

        Intenta usar LAST_INSERT_ID() en la conexión si está disponible.
        """
        try:
            # Algunas conexiones/ drivers pueden exponer lastrowid; si no, intentar con SELECT LAST_INSERT_ID()
            lid = getattr(cur, 'lastrowid', None)
            if lid:
                return int(lid)
        except Exception:
            pass
        try:
            if conn is not None:
                c2 = conn.cursor()
                c2.execute('SELECT LAST_INSERT_ID()')
                row = c2.fetchone()
                c2.close()
                if row:
                    return int(row[0])
        except Exception:
            pass
        return None

    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({'status': 'ok'}), 200

    # --- CRUD Proveedores [cite: 1180] ---
    @app.route('/proveedores', methods=['GET'])
    def get_proveedores():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id_proveedor AS id, nombre, direccion, telefono, email FROM Proveedores")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        proveedores = []
        for r in rows:
            proveedores.append({'id': r[0], 'nombre': r[1], 'direccion': r[2], 'telefono': r[3], 'email': r[4]})
        return jsonify(proveedores)

    @app.route('/proveedores/<int:prov_id>', methods=['GET'])
    def get_proveedor(prov_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id_proveedor AS id, nombre, direccion, telefono, email FROM Proveedores WHERE id_proveedor = %s", (prov_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if not row:
            return jsonify({'error': 'No encontrado'}), 404
        prov = {'id': row[0], 'nombre': row[1], 'direccion': row[2], 'telefono': row[3], 'email': row[4]}
        return jsonify(prov), 200

    @app.route('/proveedores', methods=['POST'])
    def add_proveedor():
        data = request.json or {}
        conn = get_connection()
        cursor = conn.cursor()
        sql = "INSERT INTO Proveedores (nombre, direccion, telefono, email) VALUES (%s, %s, %s, %s)"
        val = (data.get('nombre'), data.get('direccion'), data.get('telefono'), data.get('email'))
        cursor.execute(sql, val)
        conn.commit()
        new_id = getattr(cursor, 'lastrowid', None)
        cursor.close()
        conn.close()
        return jsonify({"id": new_id, "mensaje": f"Proveedor '{data.get('nombre')}' añadido"}), 201

    @app.route('/proveedores/<int:prov_id>', methods=['PUT'])
    def update_proveedor(prov_id):
        data = request.get_json() or {}
        fields, vals = [], []
        for key in ('nombre', 'direccion', 'telefono', 'email'):
            if key in data:
                fields.append(f"{key} = %s")
                vals.append(data[key])
        if not fields:
            return jsonify({'error': 'No hay campos para actualizar'}), 400
        vals.append(prov_id)
        sql = f"UPDATE Proveedores SET {', '.join(fields)} WHERE id_proveedor = %s"
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(sql, tuple(vals))
        conn.commit()
        updated = getattr(cur, 'rowcount', 0)
        cur.close()
        conn.close()
        return jsonify({'updated': updated}), 200

    @app.route('/proveedores/<int:prov_id>', methods=['DELETE'])
    def delete_proveedor(prov_id):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute('DELETE FROM Proveedores WHERE id_proveedor = %s', (prov_id,))
        conn.commit()
        deleted = getattr(cur, 'rowcount', 0)
        cur.close()
        conn.close()
        if not deleted:
            return jsonify({'deleted': 0}), 404
        return jsonify({'deleted': deleted}), 200

    # --- CRUD Productos [cite: 1178] ---
    @app.route('/productos', methods=['GET'])
    def productos_list():
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute('SELECT id_producto AS id, nombre, descripcion, precio_compra, porcentaje_ganancia, precio_venta, stock, stock_minimo, id_proveedor FROM Productos')
            rows = cur.fetchall()
            productos = [normalize_product(row_to_dict(cur, r)) for r in rows]
            cur.close()
            conn.close()
            return jsonify(productos), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/productos/<int:producto_id>', methods=['GET'])
    def producto_get(producto_id):
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute('SELECT id_producto AS id, nombre, descripcion, precio_compra, porcentaje_ganancia, precio_venta, stock, stock_minimo, id_proveedor FROM Productos WHERE id_producto = %s', (producto_id,))
            row = cur.fetchone()
            producto = normalize_product(row_to_dict(cur, row))
            cur.close()
            conn.close()
            if not producto:
                return jsonify({'error': 'No encontrado'}), 404
            return jsonify(producto), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/productos', methods=['POST'])
    def producto_create():
        data = request.get_json() or {}
        try:
            precio_compra = float(data.get('precio_compra', 0))
            porcentaje_ganancia = float(data.get('porcentaje_ganancia', 0))
            precio_venta = precio_compra * (1 + porcentaje_ganancia / 100)
            # Normalizar tipos para evitar inconsistencias
            stock = int(data.get('stock', 0) or 0)
            stock_minimo = int(data.get('stock_minimo', 0) or 0)
            id_proveedor = data.get('id_proveedor')
            try:
                id_proveedor = int(id_proveedor) if id_proveedor is not None and id_proveedor != '' else None
            except Exception:
                id_proveedor = None

            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                'INSERT INTO Productos (nombre, descripcion, precio_compra, porcentaje_ganancia, precio_venta, stock, stock_minimo, id_proveedor) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                (data.get('nombre'), data.get('descripcion'), precio_compra, porcentaje_ganancia, precio_venta, stock, stock_minimo, id_proveedor)
            )
            conn.commit()
            new_id = get_last_insert_id(cur, conn)
            cur.close()
            conn.close()
            return jsonify({'id': new_id}), 201
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/productos/<int:producto_id>', methods=['PUT'])
    def producto_update(producto_id):
        data = request.get_json() or {}
        if not data:
            return jsonify({'error': 'No hay campos para actualizar'}), 400
        
        try:
            # Obtener datos actuales para recalcular precio_venta si es necesario
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT precio_compra, porcentaje_ganancia FROM Productos WHERE id_producto = %s", (producto_id,))
            producto_row = cur.fetchone()
            if not producto_row:
                cur.close()
                conn.close()
                return jsonify({'error': 'Producto no encontrado'}), 404
            
            producto = {'precio_compra': float(producto_row[0]), 'porcentaje_ganancia': float(producto_row[1])}

            fields, vals = [], []
            for key in ('nombre', 'descripcion', 'stock', 'stock_minimo', 'id_proveedor', 'precio_compra', 'porcentaje_ganancia'):
                if key in data:
                    # Normalizar tipos según el campo
                    val = data[key]
                    if key in ('stock', 'stock_minimo'):
                        try:
                            val = int(val)
                        except Exception:
                            val = 0
                    elif key in ('precio_compra', 'porcentaje_ganancia'):
                        try:
                            val = float(val)
                        except Exception:
                            val = 0.0
                    elif key == 'id_proveedor':
                        try:
                            val = int(val) if val is not None and val != '' else None
                        except Exception:
                            val = None

                    fields.append(f"{key} = %s")
                    vals.append(val)
                    producto[key] = val # Actualizar valor local

            # Recalcular precio_venta si cambiaron los componentes
            if 'precio_compra' in data or 'porcentaje_ganancia' in data:
                precio_compra = float(producto.get('precio_compra', 0))
                porcentaje_ganancia = float(producto.get('porcentaje_ganancia', 0))
                precio_venta = precio_compra * (1 + porcentaje_ganancia / 100)
                fields.append('precio_venta = %s')
                vals.append(precio_venta)

            if not fields:
                return jsonify({'error': 'No hay campos para actualizar'}), 400

            vals.append(producto_id)
            sql = f"UPDATE Productos SET {', '.join(fields)} WHERE id_producto = %s"
            
            cur.execute(sql, tuple(vals))
            conn.commit()
            updated = getattr(cur, 'rowcount', 0)
            cur.close()
            conn.close()
            return jsonify({'updated': updated}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/productos/<int:producto_id>', methods=['DELETE'])
    def producto_delete(producto_id):
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute('DELETE FROM Productos WHERE id_producto = %s', (producto_id,))
            conn.commit()
            deleted = getattr(cur, 'rowcount', 0)
            cur.close()
            conn.close()
            if not deleted:
                return jsonify({'deleted': 0}), 404
            return jsonify({'deleted': deleted}), 200
        except mariadb.Error as e:
            # Capturar error de restricción (ej. ON DELETE RESTRICT)
            return jsonify({'error': f'No se puede borrar: {e}'}), 500
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # --- CRUD Clientes [cite: 1179] ---
    @app.route('/clientes', methods=['GET'])
    def clientes_list():
        conn = get_connection()
        cur = conn.cursor()
        cur.execute('SELECT id_cliente AS id, nombre, direccion, telefono, email FROM Clientes')
        rows = cur.fetchall()
        cur.close()
        conn.close()
        clientes = [{'id': r[0], 'nombre': r[1], 'direccion': r[2], 'telefono': r[3], 'email': r[4]} for r in rows]
        return jsonify(clientes), 200

    @app.route('/clientes/<int:cliente_id>', methods=['GET'])
    def cliente_get(cliente_id):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute('SELECT id_cliente AS id, nombre, direccion, telefono, email FROM Clientes WHERE id_cliente = %s', (cliente_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return jsonify({'error': 'No encontrado'}), 404
        return jsonify({'id': row[0], 'nombre': row[1], 'direccion': row[2], 'telefono': row[3], 'email': row[4]}), 200

    @app.route('/clientes', methods=['POST'])
    def cliente_create():
        data = request.get_json() or {}
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute('INSERT INTO Clientes (nombre, direccion, telefono, email) VALUES (%s, %s, %s, %s)',
                        (data.get('nombre'), data.get('direccion'), data.get('telefono'), data.get('email')))
            conn.commit()
            new_id = get_last_insert_id(cur, conn)
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            cur.close()
            conn.close()
            return jsonify({'error': str(e)}), 500
        cur.close()
        conn.close()
        return jsonify({'id': new_id}), 201

    @app.route('/clientes/<int:cliente_id>', methods=['PUT'])
    def cliente_update(cliente_id):
        data = request.get_json() or {}
        fields, vals = [], []
        for key in ('nombre', 'direccion', 'telefono', 'email'):
            if key in data:
                fields.append(f"{key} = %s")
                vals.append(data[key])
        if not fields:
            return jsonify({'error': 'No hay campos para actualizar'}), 400
        vals.append(cliente_id)
        sql = f"UPDATE Clientes SET {', '.join(fields)} WHERE id_cliente = %s"
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(sql, tuple(vals))
        conn.commit()
        updated = getattr(cur, 'rowcount', 0)
        cur.close()
        conn.close()
        return jsonify({'updated': updated}), 200

    @app.route('/clientes/<int:cliente_id>', methods=['DELETE'])
    def cliente_delete(cliente_id):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute('DELETE FROM Clientes WHERE id_cliente = %s', (cliente_id,))
        conn.commit()
        deleted = getattr(cur, 'rowcount', 0)
        cur.close()
        conn.close()
        if not deleted:
            return jsonify({'deleted': 0}), 404
        return jsonify({'deleted': deleted}), 200

    # --- Login y Usuarios [cite: 1175] ---
    @app.route('/login', methods=['POST'])
    def login():
        data = request.get_json() or {}
        username = data.get('username')
        password = data.get('password')
        if not username or not password:
            return jsonify({'error': 'Username y password son requeridos'}), 400

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM Usuarios WHERE username = %s", (username,))
        user = row_to_dict(cur, cur.fetchone())
        cur.close()
        conn.close()

        if user and bcrypt.check_password_hash(user.get('password', ''), password):
            return jsonify({'message': 'Login exitoso', 'user': {'id': user.get('id_usuario'), 'username': user.get('username'), 'rol': user.get('rol')}}), 200
        else:
            return jsonify({'error': 'Credenciales inválidas'}), 401

    @app.route('/usuarios', methods=['POST'])
    def usuario_create():
        data = request.get_json() or {}
        username = data.get('username')
        password = data.get('password')
        rol = data.get('rol', 'vendedor')
        if not username or not password:
            return jsonify({'error': 'username y password son requeridos'}), 400
        
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute('INSERT INTO Usuarios (username, password, rol) VALUES (%s, %s, %s)',
                        (username, hashed_password, rol))
            conn.commit()
            new_id = get_last_insert_id(cur, conn)
        except mariadb.IntegrityError:
            return jsonify({'error': 'El nombre de usuario ya existe'}), 409
        finally:
            cur.close()
            conn.close()
        return jsonify({'id': new_id}), 201

    # --- CRUD (Simplificado) para Compras, Ventas y Detalles ---
    # Endpoints para Ventas y Detalle_Ventas (simplificados pero transaccionales)
    @app.route('/ventas', methods=['POST'])
    def ventas_create():
        """Crear una venta. Espera JSON con: fecha_venta (YYYY-MM-DD opcional), id_cliente (opcional), total."""
        data = request.get_json() or {}
        fecha_venta = data.get('fecha_venta') or datetime.now().strftime('%Y-%m-%d')
        id_cliente = data.get('id_cliente')
        try:
            total = float(data.get('total', 0))
        except Exception:
            return jsonify({'error': 'total inválido'}), 400

        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute('INSERT INTO Ventas (fecha_venta, id_cliente, total) VALUES (%s, %s, %s)', (fecha_venta, id_cliente, total))
            conn.commit()
            new_id = getattr(cur, 'lastrowid', None)
            cur.close()
            conn.close()
            return jsonify({'id': new_id}), 201
        except Exception as e:
            try:
                cur.close()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass
            return jsonify({'error': str(e)}), 500

    @app.route('/detalle_ventas', methods=['POST'])
    def detalle_ventas_create():
        """Crear un detalle de venta y reducir el stock del producto de forma transaccional.

        JSON esperado: id_venta, id_producto, cantidad, precio_unitario
        """
        data = request.get_json() or {}
        try:
            id_venta = int(data.get('id_venta'))
            id_producto = int(data.get('id_producto'))
            cantidad = int(data.get('cantidad'))
            precio_unitario = float(data.get('precio_unitario', 0))
        except Exception:
            return jsonify({'error': 'Parámetros inválidos (id_venta, id_producto, cantidad, precio_unitario son requeridos)'}), 400

        conn = None
        cur = None
        try:
            conn = get_connection()
            cur = conn.cursor()
            # Bloquear fila del producto para evitar condiciones de carrera
            cur.execute('SELECT stock FROM Productos WHERE id_producto = %s FOR UPDATE', (id_producto,))
            row = cur.fetchone()
            if not row:
                conn.rollback()
                return jsonify({'error': 'Producto no encontrado'}), 404
            stock_actual = int(row[0])
            if cantidad <= 0:
                conn.rollback()
                return jsonify({'error': 'Cantidad debe ser mayor que 0'}), 400
            if stock_actual < cantidad:
                conn.rollback()
                return jsonify({'error': f'Stock insuficiente. Disponible: {stock_actual}'},), 400

            # Insertar detalle de venta
            cur.execute('INSERT INTO Detalle_Ventas (id_venta, id_producto, cantidad, precio_unitario) VALUES (%s, %s, %s, %s)',
                        (id_venta, id_producto, cantidad, precio_unitario))

            # Reducir stock
            cur.execute('UPDATE Productos SET stock = stock - %s WHERE id_producto = %s', (cantidad, id_producto))

            conn.commit()
            new_id = getattr(cur, 'lastrowid', None)
            cur.close()
            conn.close()
            return jsonify({'id': new_id}), 201
        except mariadb.IntegrityError as e:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return jsonify({'error': str(e)}), 500

    # --- REPORTES [cite: 1181, 1182, 1183, 1184, 1185] ---

    def validate_dates(desde, hasta):
        if not desde or not hasta:
            return None, (jsonify({'error': 'Parametros desde y hasta son requeridos (YYYY-MM-DD)'}), 400)
        try:
            d_desde = datetime.strptime(desde, '%Y-%m-%d').date()
            d_hasta = datetime.strptime(hasta, '%Y-%m-%d').date()
            return (d_desde, d_hasta), None
        except Exception:
            return None, (jsonify({'error': 'Formato de fecha inválido, use YYYY-MM-DD'}), 400)

    @app.route('/reportes/compras', methods=['GET'])
    def reporte_compras():
        desde, hasta = request.args.get('desde'), request.args.get('hasta')
        dates, error = validate_dates(desde, hasta)
        if error: return error

        conn = get_connection()
        cur = conn.cursor()
        try:
            sql = (
                "SELECT c.id_compra AS id, c.fecha_compra, c.total, p.id_proveedor, p.nombre AS proveedor "
                "FROM Compras c LEFT JOIN Proveedores p ON c.id_proveedor = p.id_proveedor "
                "WHERE c.fecha_compra BETWEEN %s AND %s ORDER BY c.fecha_compra"
            )
            cur.execute(sql, (desde, hasta))
            compras = [row_to_dict(cur, r) for r in cur.fetchall()]
            
            cur.execute('SELECT COALESCE(SUM(total),0) FROM Compras WHERE fecha_compra BETWEEN %s AND %s', (desde, hasta))
            suma_total = cur.fetchone()[0]
            
            return jsonify({'desde': desde, 'hasta': hasta, 'suma_total': float(suma_total), 'compras': compras}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            cur.close()
            conn.close()

    @app.route('/reportes/ventas', methods=['GET'])
    def reporte_ventas():
        desde, hasta = request.args.get('desde'), request.args.get('hasta')
        dates, error = validate_dates(desde, hasta)
        if error: return error

        conn = get_connection()
        cur = conn.cursor()
        try:
            sql = (
                "SELECT v.id_venta AS id, v.fecha_venta, v.total, c.id_cliente, c.nombre AS cliente "
                "FROM Ventas v LEFT JOIN Clientes c ON v.id_cliente = c.id_cliente "
                "WHERE v.fecha_venta BETWEEN %s AND %s ORDER BY v.fecha_venta"
            )
            cur.execute(sql, (desde, hasta))
            ventas = [row_to_dict(cur, r) for r in cur.fetchall()]

            cur.execute('SELECT COALESCE(SUM(total), 0) FROM Ventas WHERE fecha_venta BETWEEN %s AND %s', (desde, hasta))
            suma_total = cur.fetchone()[0]

            return jsonify({'desde': desde, 'hasta': hasta, 'suma_total': float(suma_total), 'ventas': ventas}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            cur.close()
            conn.close()

    @app.route('/reportes/ganancias', methods=['GET'])
    def reporte_ganancias():
        desde, hasta = request.args.get('desde'), request.args.get('hasta')
        dates, error = validate_dates(desde, hasta)
        if error: return error

        conn = get_connection()
        cur = conn.cursor()
        try:
            sql_productos = (
                "SELECT p.nombre as producto, SUM(dv.cantidad) as cantidad_vendida, "
                "SUM(dv.cantidad * dv.precio_unitario) as total_ventas, "
                "SUM(dv.cantidad * p.precio_compra) as total_costo, "
                "SUM(dv.cantidad * (dv.precio_unitario - p.precio_compra)) as ganancia "
                "FROM Detalle_Ventas dv "
                "JOIN Ventas v ON dv.id_venta = v.id_venta "
                "JOIN Productos p ON dv.id_producto = p.id_producto "
                "WHERE v.fecha_venta BETWEEN %s AND %s "
                "GROUP BY p.nombre"
            )
            cur.execute(sql_productos, (desde, hasta))
            ganancias_por_producto = [row_to_dict(cur, r) for r in cur.fetchall()]

            sql_total = (
                "SELECT SUM(dv.cantidad * (dv.precio_unitario - p.precio_compra)) as ganancia_total "
                "FROM Detalle_Ventas dv "
                "JOIN Ventas v ON dv.id_venta = v.id_venta "
                "JOIN Productos p ON dv.id_producto = p.id_producto "
                "WHERE v.fecha_venta BETWEEN %s AND %s"
            )
            cur.execute(sql_total, (desde, hasta))
            ganancia_total = cur.fetchone()[0]

            return jsonify({
                'desde': desde,
                'hasta': hasta,
                'ganancia_total': float(ganancia_total or 0.0),
                'ganancias_por_producto': ganancias_por_producto
            }), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            cur.close()
            conn.close()

    @app.route('/reportes/existencias_minimas', methods=['GET'])
    def reporte_existencias_minimas():
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT nombre, stock, stock_minimo FROM Productos WHERE stock <= stock_minimo")
            productos = [row_to_dict(cur, r) for r in cur.fetchall()]
            return jsonify(productos), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            cur.close()
            conn.close()

    @app.route('/reportes/existencias', methods=['GET'])
    def reporte_existencias():
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT nombre, stock FROM Productos ORDER BY nombre")
            productos = [row_to_dict(cur, r) for r in cur.fetchall()]
            return jsonify(productos), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            cur.close()
            conn.close()

    return app

# --- Bloque para ejecutar el servidor ---
if __name__ == '__main__':
    app = create_app()
    port = int(os.getenv('PORT', 5000))
    print(f"--- Servidor API corriendo en http://127.0.0.1:{port} ---")
    app.run(host='127.0.0.1', port=port, debug=True)
