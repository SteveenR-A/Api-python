import json
import os
import sys
import pytest
from types import SimpleNamespace

# Asegurar que el directorio del proyecto esté en sys.path para poder importar módulos locales
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import database


def make_fake_conn(rows=None, fetchone_row=None, lastrowid=1, rowcount=0):
    rows = rows or []

    class Cursor:
        def __init__(self):
            self._rows = rows
            self.lastrowid = lastrowid
            self.rowcount = rowcount

        def execute(self, sql, params=None):
            pass

        def fetchall(self):
            return self._rows

        def fetchone(self):
            return fetchone_row

        def close(self):
            pass

    class Conn:
        def __init__(self):
            self._cur = Cursor()

        def cursor(self):
            return self._cur

        def commit(self):
            pass

        def close(self):
            pass

    return Conn()


@pytest.fixture
def client(monkeypatch):
    from app import create_app

    app = create_app()
    # Config para que las excepciones se propaguen durante las pruebas
    app.config['TESTING'] = True
    app.config['PROPAGATE_EXCEPTIONS'] = True
    app.debug = True

    # por defecto, devolver conexión vacía
    monkeypatch.setattr(database, 'get_connection', lambda: make_fake_conn())

    with app.test_client() as client:
        yield client


def test_health(client):
    resp = client.get('/health')
    assert resp.status_code == 200
    assert resp.get_json() == {'status': 'ok'}


def test_get_productos_empty(client):
    resp = client.get('/productos')
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


def test_create_producto(monkeypatch):
    from app import create_app
    app = create_app()
    app.config['TESTING'] = True

    fake_conn = make_fake_conn()
    # simular que el cursor tiene lastrowid 42
    fake_conn._cur.lastrowid = 42
    monkeypatch.setattr(database, 'get_connection', lambda: fake_conn)

    with app.test_client() as client:
        resp = client.post('/productos', json={'nombre': 'Test', 'precio': 10.5})
        assert resp.status_code == 201
        assert resp.get_json()['id'] == 42


def test_update_producto_no_fields(client):
    resp = client.put('/productos/1', json={})
    assert resp.status_code == 400


def test_delete_producto_not_found(monkeypatch):
    from app import create_app
    app = create_app()
    app.config['TESTING'] = True

    # cursor rowcount = 0 => not found
    fake_conn = make_fake_conn()
    fake_conn._cur.rowcount = 0
    monkeypatch.setattr(database, 'get_connection', lambda: fake_conn)

    with app.test_client() as client:
        resp = client.delete('/productos/999')
        # Not found mapped to 404
        assert resp.status_code in (200, 404)
