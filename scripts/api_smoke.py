#!/usr/bin/env python3
"""Smoke test simple para verificar CRUD básicos contra la API.
Hace POST -> GET -> PUT -> DELETE para Productos, Clientes y Proveedores.
Lee la URL de la API desde la variable de entorno API_URL o usa http://127.0.0.1:5000.
"""
import os
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


API_URL = os.getenv('API_URL', 'http://127.0.0.1:5000')


def make_session(retries: int = 3, backoff_factor: float = 0.5, status_forcelist=(429, 500, 502, 503, 504)):
    s = requests.Session()
    retry = Retry(total=retries, read=retries, connect=retries, backoff_factor=backoff_factor, status_forcelist=status_forcelist, allowed_methods=frozenset(['GET','POST','PUT','DELETE','HEAD','OPTIONS']))
    adapter = HTTPAdapter(max_retries=retry)
    s.mount('http://', adapter)
    s.mount('https://', adapter)
    return s


SESSION = make_session()


def assert_up():
    try:
        r = SESSION.get(f"{API_URL}/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def smoke_resource(resource, create_payload):
    base = f"{API_URL}/{resource}"
    print(f"\n=== Probar {resource} -> {base}")
    # listar
    try:
        r = SESSION.get(base, timeout=4)
        print(f"GET {resource}: {r.status_code}")
    except Exception as e:
        print("ERROR GET:", e)
        return False

    # crear
    try:
        r = SESSION.post(base, json=create_payload, timeout=6)
        print(f"POST {resource}: {r.status_code} -> {r.text}")
        if r.status_code not in (200, 201):
            return False
        new_id = r.json().get('id')
    except Exception as e:
        print("ERROR POST:", e)
        return False

    # obtener
    try:
        r = SESSION.get(f"{base}/{new_id}", timeout=4)
        print(f"GET {resource}/{new_id}: {r.status_code} -> {r.text}")
        if r.status_code != 200:
            return False
    except Exception as e:
        print("ERROR GET id:", e)
        return False

    # actualizar (si tiene campo 'nombre' lo cambiamos)
    upd = {}
    if 'nombre' in create_payload:
        upd['nombre'] = create_payload['nombre'] + ' - actualizado'
    else:
        upd = {k: create_payload.get(k) for k in create_payload.keys()}
    try:
        r = SESSION.put(f"{base}/{new_id}", json=upd, timeout=6)
        print(f"PUT {resource}/{new_id}: {r.status_code} -> {r.text}")
    except Exception as e:
        print("ERROR PUT:", e)
        return False

    # borrar
    try:
        r = SESSION.delete(f"{base}/{new_id}", timeout=6)
        print(f"DELETE {resource}/{new_id}: {r.status_code} -> {r.text}")
    except Exception as e:
        print("ERROR DELETE:", e)
        return False

    return True


def main():
    print("API_URL=", API_URL)
    if not assert_up():
        print("La API no responde en /health. Arranca la API y reintenta.")
        return 2

    ts = int(time.time())
    ok = True

    # Productos: necesitamos precio_compra y porcentaje_ganancia o precio; usamos precio_compra+porcentaje
    prod_payload = {
        'nombre': f'Producto prueba {ts}',
        'descripcion': 'Creado por smoke test',
        'precio_compra': 10.0,
        'porcentaje_ganancia': 50.0,
        'stock': 5,
        'stock_minimo': 1
    }
    ok &= smoke_resource('productos', prod_payload)

    # Clientes
    cli_payload = {'nombre': f'Cliente prueba {ts}', 'direccion': 'Calle Falsa 123', 'telefono': '000', 'email': 'cli@example.com'}
    ok &= smoke_resource('clientes', cli_payload)

    # Proveedores
    prov_payload = {'nombre': f'Proveedor prueba {ts}', 'direccion': 'Av. Principal', 'telefono': '111', 'email': 'prov@example.com'}
    ok &= smoke_resource('proveedores', prov_payload)

    if ok:
        print('\nSmoke tests completados OK')
        return 0
    else:
        print('\nSmoke tests: fallaron algunos pasos')
        return 1


if __name__ == '__main__':
    exit(main())
