from flask import Flask, jsonify, request
from flask_bcrypt import Bcrypt
import database


def create_app():
    app = Flask(__name__)
    bcrypt = Bcrypt(app)

    # Inicializar esquema mínimo: crear tabla Proveedores si no existe
    try:
        conn_init = database.get_connection()
        cur_init = conn_init.cursor()
        cur_init.execute(
            """
            CREATE TABLE IF NOT EXISTS Proveedores (
                id_proveedor INT AUTO_INCREMENT PRIMARY KEY,
                nombre VARCHAR(255) NOT NULL,
                direccion VARCHAR(255),
                telefono VARCHAR(50),
                email VARCHAR(255)
            )
            """
        )
        conn_init.commit()
        cur_init.close()
        conn_init.close()
    except Exception:
        # No fallamos el arranque si no hay DB; las rutas manejarán los errores.
        pass

    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({'status': 'ok'}), 200

    # Endpoint para OBTENER todos los proveedores (GET)
    @app.route('/proveedores', methods=['GET'])
    def get_proveedores():
        conn = database.get_connection()
        cursor = conn.cursor()

        # La tabla en la DB usa 'id_proveedor' como PK; alias a 'id' en la salida JSON
        cursor.execute("SELECT id_proveedor AS id, nombre, direccion, telefono, email FROM Proveedores")
        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        proveedores = []
        for r in rows:
            proveedores.append({
                'id': r[0],
                'nombre': r[1],
                'direccion': r[2],
                'telefono': r[3],
                'email': r[4],
            })

        return jsonify(proveedores)

    @app.route('/proveedores/<int:prov_id>', methods=['GET'])
    def get_proveedor(prov_id):
        conn = database.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id_proveedor AS id, nombre, direccion, telefono, email FROM Proveedores WHERE id_proveedor = %s", (prov_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if not row:
            return jsonify({'error': 'No encontrado'}), 404
        prov = {'id': row[0], 'nombre': row[1], 'direccion': row[2], 'telefono': row[3], 'email': row[4]}
        return jsonify(prov), 200

    @app.route('/proveedores/<int:prov_id>', methods=['PUT'])
    def update_proveedor(prov_id):
        data = request.get_json() or {}
        fields = []
        vals = []
        for key in ('nombre', 'direccion', 'telefono', 'email'):
            if key in data:
                fields.append(f"{key} = %s")
                vals.append(data[key])
        if not fields:
            return jsonify({'error': 'No hay campos para actualizar'}), 400
        vals.append(prov_id)
        sql = 'UPDATE Proveedores SET ' + ', '.join(fields) + ' WHERE id_proveedor = %s'
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute(sql, tuple(vals))
        conn.commit()
        updated = getattr(cur, 'rowcount', None)
        cur.close()
        conn.close()
        return jsonify({'updated': updated}), 200

    @app.route('/proveedores/<int:prov_id>', methods=['DELETE'])
    def delete_proveedor(prov_id):
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute('DELETE FROM Proveedores WHERE id_proveedor = %s', (prov_id,))
        conn.commit()
        deleted = getattr(cur, 'rowcount', None)
        cur.close()
        conn.close()
        if not deleted:
            return jsonify({'deleted': 0}), 404
        return jsonify({'deleted': deleted}), 200

    # Endpoint para CREAR un nuevo proveedor (POST)
    @app.route('/proveedores', methods=['POST'])
    def add_proveedor():
        nuevo_proveedor = request.json or {}

        conn = database.get_connection()
        cursor = conn.cursor()

        sql = "INSERT INTO Proveedores (nombre, direccion, telefono, email) VALUES (%s, %s, %s, %s)"
        val = (
            nuevo_proveedor.get('nombre'),
            nuevo_proveedor.get('direccion'),
            nuevo_proveedor.get('telefono'),
            nuevo_proveedor.get('email'),
        )

        cursor.execute(sql, val)
        conn.commit()

        # intentar obtener id insertado
        new_id = getattr(cursor, 'lastrowid', None)

        cursor.close()
        conn.close()

        return jsonify({"id": new_id, "mensaje": f"Proveedor '{nuevo_proveedor.get('nombre')}' añadido exitosamente"}), 201

    # CRUD para productos
    def row_to_producto(row):
        return {
            'id': row[0],
            'nombre': row[1],
            'descripcion': row[2],
            'precio': float(row[3]) if row[3] is not None else 0.0,
            'cantidad': int(row[4]) if row[4] is not None else 0,
            'creado_en': str(row[5]) if row[5] is not None else None,
        }

    @app.route('/productos', methods=['GET'])
    def productos_list():
        try:
            conn = database.get_connection()
            cur = conn.cursor()
            # La tabla real es `Productos` con columnas id_producto, precio_venta, stock
            cur.execute('SELECT id_producto AS id, nombre, descripcion, precio_venta AS precio, stock AS cantidad, NULL AS creado_en FROM Productos')
            rows = cur.fetchall()
            cur.close()
            conn.close()
            productos = [row_to_producto(r) for r in rows]
            return jsonify(productos), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/productos/<int:producto_id>', methods=['GET'])
    def producto_get(producto_id):
        try:
            conn = database.get_connection()
            cur = conn.cursor()
            cur.execute('SELECT id_producto AS id, nombre, descripcion, precio_venta AS precio, stock AS cantidad, NULL AS creado_en FROM Productos WHERE id_producto = %s', (producto_id,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            if not row:
                return jsonify({'error': 'No encontrado'}), 404
            return jsonify(row_to_producto(row)), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/productos', methods=['POST'])
    def producto_create():
        data = request.get_json() or {}
        nombre = data.get('nombre')
        descripcion = data.get('descripcion')
        precio = data.get('precio', 0.0)
        cantidad = data.get('cantidad', 0)
        # campos adicionales requeridos por la tabla Productos
        precio_compra = data.get('precio_compra', precio)
        porcentaje_ganancia = data.get('porcentaje_ganancia', 0.0)
        stock_minimo = data.get('stock_minimo', 0)
        id_proveedor = data.get('id_proveedor', None)
        if not nombre:
            return jsonify({'error': 'nombre es requerido'}), 400
        try:
            conn = database.get_connection()
            cur = conn.cursor()
            # Insertar mapeando a la estructura real: usar precio_compra, porcentaje_ganancia, precio_venta y stock
            cur.execute(
                'INSERT INTO Productos (nombre, descripcion, precio_compra, porcentaje_ganancia, precio_venta, stock, stock_minimo, id_proveedor) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                (nombre, descripcion, precio_compra, porcentaje_ganancia, precio, cantidad, stock_minimo, id_proveedor)
            )
            conn.commit()
            new_id = getattr(cur, 'lastrowid', None)
            cur.close()
            conn.close()
            return jsonify({'id': new_id}), 201
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/productos/<int:producto_id>', methods=['PUT'])
    def producto_update(producto_id):
        data = request.get_json() or {}
        try:
            # Construir actualización dinámica mínima
            fields = []
            vals = []
            # Mapear campos del API a columnas reales de la tabla Productos
            mapping = {
                'nombre': 'nombre',
                'descripcion': 'descripcion',
                'precio': 'precio_venta',
                'cantidad': 'stock'
            }
            for key in ('nombre', 'descripcion', 'precio', 'cantidad'):
                if key in data:
                    col = mapping.get(key, key)
                    fields.append(f"{col} = %s")
                    vals.append(data[key])
            if not fields:
                return jsonify({'error': 'No hay campos para actualizar'}), 400
            vals.append(producto_id)
            sql = 'UPDATE Productos SET ' + ', '.join(fields) + ' WHERE id_producto = %s'
            conn = database.get_connection()
            cur = conn.cursor()
            cur.execute(sql, tuple(vals))
            conn.commit()
            updated = getattr(cur, 'rowcount', None)
            cur.close()
            conn.close()
            return jsonify({'updated': updated}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/productos/<int:producto_id>', methods=['DELETE'])
    def producto_delete(producto_id):
        try:
            conn = database.get_connection()
            cur = conn.cursor()
            cur.execute('DELETE FROM Productos WHERE id_producto = %s', (producto_id,))
            conn.commit()
            deleted = getattr(cur, 'rowcount', None)
            cur.close()
            conn.close()
            if not deleted:
                return jsonify({'deleted': 0}), 404
            return jsonify({'deleted': deleted}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # CRUD para clientes
    @app.route('/clientes', methods=['GET'])
    def clientes_list():
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute('SELECT id_cliente AS id, nombre, direccion, telefono, email FROM Clientes')
        rows = cur.fetchall()
        cur.close()
        conn.close()
        clientes = []
        for r in rows:
            clientes.append({'id': r[0], 'nombre': r[1], 'direccion': r[2], 'telefono': r[3], 'email': r[4]})
        return jsonify(clientes), 200

    @app.route('/clientes/<int:cliente_id>', methods=['GET'])
    def cliente_get(cliente_id):
        conn = database.get_connection()
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
        nombre = data.get('nombre')
        if not nombre:
            return jsonify({'error': 'nombre es requerido'}), 400
        direccion = data.get('direccion')
        telefono = data.get('telefono')
        email = data.get('email')
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute('INSERT INTO Clientes (nombre, direccion, telefono, email) VALUES (%s, %s, %s, %s)',
                    (nombre, direccion, telefono, email))
        conn.commit()
        new_id = getattr(cur, 'lastrowid', None)
        cur.close()
        conn.close()
        return jsonify({'id': new_id}), 201

    @app.route('/clientes/<int:cliente_id>', methods=['PUT'])
    def cliente_update(cliente_id):
        data = request.get_json() or {}
        fields = []
        vals = []
        for key in ('nombre', 'direccion', 'telefono', 'email'):
            if key in data:
                fields.append(f"{key} = %s")
                vals.append(data[key])
        if not fields:
            return jsonify({'error': 'No hay campos para actualizar'}), 400
        vals.append(cliente_id)
        sql = 'UPDATE Clientes SET ' + ', '.join(fields) + ' WHERE id_cliente = %s'
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute(sql, tuple(vals))
        conn.commit()
        updated = getattr(cur, 'rowcount', None)
        cur.close()
        conn.close()
        return jsonify({'updated': updated}), 200

    @app.route('/clientes/<int:cliente_id>', methods=['DELETE'])
    def cliente_delete(cliente_id):
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute('DELETE FROM Clientes WHERE id_cliente = %s', (cliente_id,))
        conn.commit()
        deleted = getattr(cur, 'rowcount', None)
        cur.close()
        conn.close()
        if not deleted:
            return jsonify({'deleted': 0}), 404
        return jsonify({'deleted': deleted}), 200

    # Ruta para login
    @app.route('/login', methods=['POST'])
    def login():
        data = request.get_json() or {}
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({'error': 'Username y password son requeridos'}), 400

        conn = database.get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM Usuarios WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user and bcrypt.check_password_hash(user['password'], password):
            return jsonify({'message': 'Login exitoso', 'user': {'id': user['id_usuario'], 'username': user['username'], 'rol': user['rol']}}), 200
        else:
            return jsonify({'error': 'Credenciales inválidas'}), 401

    # CRUD para usuarios
    @app.route('/usuarios', methods=['GET'])
    def usuarios_list():
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id_usuario AS id, username, rol FROM Usuarios")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        usuarios = [{'id': r[0], 'username': r[1], 'rol': r[2]} for r in rows]
        return jsonify(usuarios), 200

    @app.route('/usuarios/<int:usuario_id>', methods=['GET'])
    def usuario_get(usuario_id):
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute('SELECT id_usuario AS id, username, rol FROM Usuarios WHERE id_usuario = %s', (usuario_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return jsonify({'error': 'No encontrado'}), 404
        return jsonify({'id': row[0], 'username': row[1], 'rol': row[2]}), 200

    @app.route('/usuarios', methods=['POST'])
    def usuario_create():
        data = request.get_json() or {}
        username = data.get('username')
        password = data.get('password')
        rol = data.get('rol', 'vendedor')
        if not username or not password:
            return jsonify({'error': 'username y password son requeridos'}), 400
        
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        
        conn = database.get_connection()
        cur = conn.cursor()
        try:
            cur.execute('INSERT INTO Usuarios (username, password, rol) VALUES (%s, %s, %s)',
                        (username, hashed_password, rol))
            conn.commit()
            new_id = getattr(cur, 'lastrowid', None)
        except database.mariadb.IntegrityError:
            return jsonify({'error': 'El nombre de usuario ya existe'}), 409
        finally:
            cur.close()
            conn.close()
        
        return jsonify({'id': new_id}), 201

    @app.route('/usuarios/<int:usuario_id>', methods=['PUT'])
    def usuario_update(usuario_id):
        data = request.get_json() or {}
        fields = []
        vals = []
        for key in ('username', 'password', 'rol'):
            if key in data:
                fields.append(f"{key} = %s")
                vals.append(data[key])
        if not fields:
            return jsonify({'error': 'No hay campos para actualizar'}), 400
        vals.append(usuario_id)
        sql = 'UPDATE Usuarios SET ' + ', '.join(fields) + ' WHERE id_usuario = %s'
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute(sql, tuple(vals))
        conn.commit()
        updated = getattr(cur, 'rowcount', None)
        cur.close()
        conn.close()
        return jsonify({'updated': updated}), 200

    @app.route('/usuarios/<int:usuario_id>', methods=['DELETE'])
    def usuario_delete(usuario_id):
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute('DELETE FROM Usuarios WHERE id_usuario = %s', (usuario_id,))
        conn.commit()
        deleted = getattr(cur, 'rowcount', None)
        cur.close()
        conn.close()
        if not deleted:
            return jsonify({'deleted': 0}), 404
        return jsonify({'deleted': deleted}), 200

    # CRUD para Compras
    @app.route('/compras', methods=['GET'])
    def compras_list():
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute('SELECT id_compra AS id, id_proveedor, fecha_compra, total FROM Compras')
        rows = cur.fetchall()
        cur.close()
        conn.close()
        compras = [{'id': r[0], 'id_proveedor': r[1], 'fecha_compra': str(r[2]) if r[2] is not None else None, 'total': float(r[3])} for r in rows]
        return jsonify(compras), 200

    @app.route('/compras/<int:compra_id>', methods=['GET'])
    def compra_get(compra_id):
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute('SELECT id_compra AS id, id_proveedor, fecha_compra, total FROM Compras WHERE id_compra = %s', (compra_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return jsonify({'error': 'No encontrado'}), 404
        return jsonify({'id': row[0], 'id_proveedor': row[1], 'fecha_compra': str(row[2]) if row[2] is not None else None, 'total': float(row[3])}), 200

    @app.route('/compras', methods=['POST'])
    def compra_create():
        data = request.get_json() or {}
        id_proveedor = data.get('id_proveedor')
        fecha_compra = data.get('fecha_compra')
        total = data.get('total', 0.0)
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute('INSERT INTO Compras (id_proveedor, fecha_compra, total) VALUES (%s, %s, %s)', (id_proveedor, fecha_compra, total))
        conn.commit()
        new_id = getattr(cur, 'lastrowid', None)
        cur.close()
        conn.close()
        return jsonify({'id': new_id}), 201

    @app.route('/compras/<int:compra_id>', methods=['PUT'])
    def compra_update(compra_id):
        data = request.get_json() or {}
        fields = []
        vals = []
        for key in ('id_proveedor', 'fecha_compra', 'total'):
            if key in data:
                fields.append(f"{key} = %s")
                vals.append(data[key])
        if not fields:
            return jsonify({'error': 'No hay campos para actualizar'}), 400
        vals.append(compra_id)
        sql = 'UPDATE Compras SET ' + ', '.join(fields) + ' WHERE id_compra = %s'
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute(sql, tuple(vals))
        conn.commit()
        updated = getattr(cur, 'rowcount', None)
        cur.close()
        conn.close()
        return jsonify({'updated': updated}), 200

    @app.route('/compras/<int:compra_id>', methods=['DELETE'])
    def compra_delete(compra_id):
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute('DELETE FROM Compras WHERE id_compra = %s', (compra_id,))
        conn.commit()
        deleted = getattr(cur, 'rowcount', None)
        cur.close()
        conn.close()
        if not deleted:
            return jsonify({'deleted': 0}), 404
        return jsonify({'deleted': deleted}), 200

    # CRUD para Detalle_Compras
    @app.route('/detalle_compras', methods=['GET'])
    def detalle_compras_list():
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute('SELECT id_detalle_compra AS id, id_compra, id_producto, cantidad, precio_compra FROM Detalle_Compras')
        rows = cur.fetchall()
        cur.close()
        conn.close()
        out = [{'id': r[0], 'id_compra': r[1], 'id_producto': r[2], 'cantidad': int(r[3]), 'precio_compra': float(r[4])} for r in rows]
        return jsonify(out), 200

    @app.route('/detalle_compras/<int:detalle_id>', methods=['GET'])
    def detalle_compra_get(detalle_id):
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute('SELECT id_detalle_compra AS id, id_compra, id_producto, cantidad, precio_compra FROM Detalle_Compras WHERE id_detalle_compra = %s', (detalle_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return jsonify({'error': 'No encontrado'}), 404
        return jsonify({'id': row[0], 'id_compra': row[1], 'id_producto': row[2], 'cantidad': int(row[3]), 'precio_compra': float(row[4])}), 200

    @app.route('/detalle_compras', methods=['POST'])
    def detalle_compra_create():
        data = request.get_json() or {}
        id_compra = data.get('id_compra')
        id_producto = data.get('id_producto')
        cantidad = data.get('cantidad', 0)
        precio_compra = data.get('precio_compra', 0.0)
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute('INSERT INTO Detalle_Compras (id_compra, id_producto, cantidad, precio_compra) VALUES (%s, %s, %s, %s)', (id_compra, id_producto, cantidad, precio_compra))
        conn.commit()
        new_id = getattr(cur, 'lastrowid', None)
        cur.close()
        conn.close()
        return jsonify({'id': new_id}), 201

    @app.route('/detalle_compras/<int:detalle_id>', methods=['PUT'])
    def detalle_compra_update(detalle_id):
        data = request.get_json() or {}
        fields = []
        vals = []
        for key in ('id_compra', 'id_producto', 'cantidad', 'precio_compra'):
            if key in data:
                fields.append(f"{key} = %s")
                vals.append(data[key])
        if not fields:
            return jsonify({'error': 'No hay campos para actualizar'}), 400
        vals.append(detalle_id)
        sql = 'UPDATE Detalle_Compras SET ' + ', '.join(fields) + ' WHERE id_detalle_compra = %s'
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute(sql, tuple(vals))
        conn.commit()
        updated = getattr(cur, 'rowcount', None)
        cur.close()
        conn.close()
        return jsonify({'updated': updated}), 200

    @app.route('/detalle_compras/<int:detalle_id>', methods=['DELETE'])
    def detalle_compra_delete(detalle_id):
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute('DELETE FROM Detalle_Compras WHERE id_detalle_compra = %s', (detalle_id,))
        conn.commit()
        deleted = getattr(cur, 'rowcount', None)
        cur.close()
        conn.close()
        if not deleted:
            return jsonify({'deleted': 0}), 404
        return jsonify({'deleted': deleted}), 200

    # CRUD para Ventas
    @app.route('/ventas', methods=['GET'])
    def ventas_list():
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute('SELECT id_venta AS id, fecha_venta, id_cliente, total FROM Ventas')
        rows = cur.fetchall()
        cur.close()
        conn.close()
        out = [{'id': r[0], 'fecha_venta': str(r[1]) if r[1] is not None else None, 'id_cliente': r[2], 'total': float(r[3])} for r in rows]
        return jsonify(out), 200

    @app.route('/ventas/<int:venta_id>', methods=['GET'])
    def venta_get(venta_id):
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute('SELECT id_venta AS id, fecha_venta, id_cliente, total FROM Ventas WHERE id_venta = %s', (venta_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return jsonify({'error': 'No encontrado'}), 404
        return jsonify({'id': row[0], 'fecha_venta': str(row[1]) if row[1] is not None else None, 'id_cliente': row[2], 'total': float(row[3])}), 200

    @app.route('/ventas', methods=['POST'])
    def venta_create():
        data = request.get_json() or {}
        fecha_venta = data.get('fecha_venta')
        id_cliente = data.get('id_cliente')
        total = data.get('total', 0.0)
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute('INSERT INTO Ventas (fecha_venta, id_cliente, total) VALUES (%s, %s, %s)', (fecha_venta, id_cliente, total))
        conn.commit()
        new_id = getattr(cur, 'lastrowid', None)
        cur.close()
        conn.close()
        return jsonify({'id': new_id}), 201

    @app.route('/ventas/<int:venta_id>', methods=['PUT'])
    def venta_update(venta_id):
        data = request.get_json() or {}
        fields = []
        vals = []
        for key in ('fecha_venta', 'id_cliente', 'total'):
            if key in data:
                fields.append(f"{key} = %s")
                vals.append(data[key])
        if not fields:
            return jsonify({'error': 'No hay campos para actualizar'}), 400
        vals.append(venta_id)
        sql = 'UPDATE Ventas SET ' + ', '.join(fields) + ' WHERE id_venta = %s'
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute(sql, tuple(vals))
        conn.commit()
        updated = getattr(cur, 'rowcount', None)
        cur.close()
        conn.close()
        return jsonify({'updated': updated}), 200

    @app.route('/ventas/<int:venta_id>', methods=['DELETE'])
    def venta_delete(venta_id):
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute('DELETE FROM Ventas WHERE id_venta = %s', (venta_id,))
        conn.commit()
        deleted = getattr(cur, 'rowcount', None)
        cur.close()
        conn.close()
        if not deleted:
            return jsonify({'deleted': 0}), 404
        return jsonify({'deleted': deleted}), 200

    # CRUD para Detalle_Ventas
    @app.route('/detalle_ventas', methods=['GET'])
    def detalle_ventas_list():
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute('SELECT id_detalle AS id, id_venta, id_producto, cantidad, precio_unitario FROM Detalle_Ventas')
        rows = cur.fetchall()
        cur.close()
        conn.close()
        out = [{'id': r[0], 'id_venta': r[1], 'id_producto': r[2], 'cantidad': int(r[3]), 'precio_unitario': float(r[4])} for r in rows]
        return jsonify(out), 200

    @app.route('/detalle_ventas/<int:detalle_id>', methods=['GET'])
    def detalle_venta_get(detalle_id):
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute('SELECT id_detalle AS id, id_venta, id_producto, cantidad, precio_unitario FROM Detalle_Ventas WHERE id_detalle = %s', (detalle_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return jsonify({'error': 'No encontrado'}), 404
        return jsonify({'id': row[0], 'id_venta': row[1], 'id_producto': row[2], 'cantidad': int(row[3]), 'precio_unitario': float(row[4])}), 200

    @app.route('/detalle_ventas', methods=['POST'])
    def detalle_venta_create():
        data = request.get_json() or {}
        id_venta = data.get('id_venta')
        id_producto = data.get('id_producto')
        cantidad = data.get('cantidad', 0)
        precio_unitario = data.get('precio_unitario', 0.0)
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute('INSERT INTO Detalle_Ventas (id_venta, id_producto, cantidad, precio_unitario) VALUES (%s, %s, %s, %s)', (id_venta, id_producto, cantidad, precio_unitario))
        conn.commit()
        new_id = getattr(cur, 'lastrowid', None)
        cur.close()
        conn.close()
        return jsonify({'id': new_id}), 201

    @app.route('/detalle_ventas/<int:detalle_id>', methods=['PUT'])
    def detalle_venta_update(detalle_id):
        data = request.get_json() or {}
        fields = []
        vals = []
        for key in ('id_venta', 'id_producto', 'cantidad', 'precio_unitario'):
            if key in data:
                fields.append(f"{key} = %s")
                vals.append(data[key])
        if not fields:
            return jsonify({'error': 'No hay campos para actualizar'}), 400
        vals.append(detalle_id)
        sql = 'UPDATE Detalle_Ventas SET ' + ', '.join(fields) + ' WHERE id_detalle = %s'
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute(sql, tuple(vals))
        conn.commit()
        updated = getattr(cur, 'rowcount', None)
        cur.close()
        conn.close()
        return jsonify({'updated': updated}), 200

    @app.route('/detalle_ventas/<int:detalle_id>', methods=['DELETE'])
    def detalle_venta_delete(detalle_id):
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute('DELETE FROM Detalle_Ventas WHERE id_detalle = %s', (detalle_id,))
        conn.commit()
        deleted = getattr(cur, 'rowcount', None)
        cur.close()
        conn.close()
        if not deleted:
            return jsonify({'deleted': 0}), 404
        return jsonify({'deleted': deleted}), 200

    # Reporte: Compras por rango de fecha
    @app.route('/reportes/compras', methods=['GET'])
    def reporte_compras():
        desde = request.args.get('desde')
        hasta = request.args.get('hasta')
        if not desde or not hasta:
            return jsonify({'error': 'Parametros desde y hasta son requeridos (YYYY-MM-DD)'}), 400
        # validar formato de fecha
        from datetime import datetime
        try:
            d_desde = datetime.strptime(desde, '%Y-%m-%d').date()
            d_hasta = datetime.strptime(hasta, '%Y-%m-%d').date()
        except Exception:
            return jsonify({'error': 'Formato de fecha inválido, use YYYY-MM-DD'}), 400

        conn = database.get_connection()
        cur = conn.cursor()
        try:
            sql = (
                "SELECT c.id_compra AS id, c.fecha_compra, c.total, p.id_proveedor AS id_proveedor, p.nombre AS proveedor "
                "FROM Compras c LEFT JOIN Proveedores p ON c.id_proveedor = p.id_proveedor "
                "WHERE c.fecha_compra BETWEEN %s AND %s ORDER BY c.fecha_compra"
            )
            cur.execute(sql, (desde, hasta))
            rows = cur.fetchall()
            compras = []
            for r in rows:
                compras.append({
                    'id': r[0],
                    'fecha_compra': str(r[1]) if r[1] is not None else None,
                    'total': float(r[2]) if r[2] is not None else 0.0,
                    'id_proveedor': r[3],
                    'proveedor': r[4],
                })

            # suma total
            cur.execute('SELECT COALESCE(SUM(total),0) FROM Compras WHERE fecha_compra BETWEEN %s AND %s', (desde, hasta))
            suma = cur.fetchone()
            suma_total = float(suma[0]) if suma and suma[0] is not None else 0.0
            return jsonify({'desde': desde, 'hasta': hasta, 'suma_total': suma_total, 'compras': compras}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            cur.close()
            conn.close()

    return app


app = create_app()


if __name__ == '__main__':
    app.run(debug=True)
    