# tests/integration/test_auth_endpoints.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_login_invalid():
    response = client.post("/auth/login", json={"username": "fake", "password": "wrong"})
    assert response.status_code in (400, 401)

def test_register_missing_fields():
    response = client.post("/auth/register", json={"username": "user"})
    assert response.status_code in (400, 422)
