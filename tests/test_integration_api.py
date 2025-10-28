import os
import pytest
import requests

API_URL = os.getenv('API_URL', 'http://127.0.0.1:5000')
RUN_INTEGRATION = os.getenv('RUN_INTEGRATION', '0') == '1'


@pytest.mark.skipif(not RUN_INTEGRATION, reason='Integration tests disabled. Set RUN_INTEGRATION=1 to enable')
def test_health():
    r = requests.get(f"{API_URL}/health", timeout=5)
    assert r.status_code == 200
    assert r.json().get('status') == 'ok'


@pytest.mark.skipif(not RUN_INTEGRATION, reason='Integration tests disabled')
def test_get_productos():
    r = requests.get(f"{API_URL}/productos", timeout=5)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.skipif(not RUN_INTEGRATION, reason='Integration tests disabled')
def test_create_producto():
    payload = {'nombre': 'IT_Test_Product', 'descripcion': 'integration test', 'precio': 9.99, 'cantidad': 1}
    r = requests.post(f"{API_URL}/productos", json=payload, timeout=5)
    assert r.status_code == 201
    j = r.json()
    assert 'id' in j and isinstance(j['id'], int)


@pytest.mark.skipif(not RUN_INTEGRATION, reason='Integration tests disabled')
def test_reporte_compras():
    # call the compras report for a wide date range
    params = {'desde': '2000-01-01', 'hasta': '2100-01-01'}
    r = requests.get(f"{API_URL}/reportes/compras", params=params, timeout=5)
    assert r.status_code == 200
    j = r.json()
    assert 'compras' in j and 'suma_total' in j
