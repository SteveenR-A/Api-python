from flask import Flask, jsonify, request
import database


def create_app():
    app = Flask(__name__)

    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({'status': 'ok'}), 200

    # Endpoint para OBTENER todos los proveedores (GET)
    @app.route('/proveedores', methods=['GET'])
    def get_proveedores():
        conn = database.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM Proveedores")
        proveedores = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify(proveedores)

    # Endpoint para CREAR un nuevo proveedor (POST)
    @app.route('/proveedores', methods=['POST'])
    def add_proveedor():
        nuevo_proveedor = request.json or {}

        conn = database.get_connection()
        cursor = conn.cursor()

        sql = "INSERT INTO Proveedores (nombre, direccion, telefono, email) VALUES (?, ?, ?, ?)"
        val = (
            nuevo_proveedor.get('nombre'),
            nuevo_proveedor.get('direccion'),
            nuevo_proveedor.get('telefono'),
            nuevo_proveedor.get('email'),
        )

        cursor.execute(sql, val)
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({"mensaje": f"Proveedor '{nuevo_proveedor.get('nombre')}' añadido exitosamente"}), 201

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
            cur.execute('SELECT id, nombre, descripcion, precio, cantidad, creado_en FROM productos')
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
            cur.execute('SELECT id, nombre, descripcion, precio, cantidad, creado_en FROM productos WHERE id = ?', (producto_id,))
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
        if not nombre:
            return jsonify({'error': 'nombre es requerido'}), 400
        try:
            conn = database.get_connection()
            cur = conn.cursor()
            cur.execute('INSERT INTO productos (nombre, descripcion, precio, cantidad) VALUES (?, ?, ?, ?)',
                        (nombre, descripcion, precio, cantidad))
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
            for key in ('nombre', 'descripcion', 'precio', 'cantidad'):
                if key in data:
                    fields.append(f"{key} = ?")
                    vals.append(data[key])
            if not fields:
                return jsonify({'error': 'No hay campos para actualizar'}), 400
            vals.append(producto_id)
            sql = 'UPDATE productos SET ' + ', '.join(fields) + ' WHERE id = ?'
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
            cur.execute('DELETE FROM productos WHERE id = ?', (producto_id,))
            conn.commit()
            deleted = getattr(cur, 'rowcount', None)
            cur.close()
            conn.close()
            if not deleted:
                return jsonify({'deleted': 0}), 404
            return jsonify({'deleted': deleted}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return app


app = create_app()


if __name__ == '__main__':
    app.run(debug=True)
    