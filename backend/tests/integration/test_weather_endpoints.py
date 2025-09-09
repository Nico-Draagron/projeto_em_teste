# tests/integration/test_weather_endpoints.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_get_current_weather_unauthenticated():
    response = client.get("/weather/current")
    assert response.status_code in (401, 403)
