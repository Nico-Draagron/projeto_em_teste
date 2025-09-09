# tests/integration/test_users_endpoints.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_get_users_unauthenticated():
    response = client.get("/users")
    assert response.status_code in (401, 403)
