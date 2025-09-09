# tests/integration/test_sales_endpoints.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_get_sales_unauthenticated():
    response = client.get("/sales")
    assert response.status_code in (401, 403)
