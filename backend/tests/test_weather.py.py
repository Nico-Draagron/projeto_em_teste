# backend/tests/test_weather.py
"""
Weather endpoint tests
"""

import pytest
from fastapi.testclient import TestClient
from datetime import date

class TestWeatherEndpoints:
    """Test weather data endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self, client, auth_headers):
        self.client = client
        self.headers = auth_headers
    
    def test_get_current_weather(self):
        """Test getting current weather"""
        response = self.client.get(
            "/api/v1/weather/current?location=São Paulo",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "temperature" in data
        assert "humidity" in data
        assert "condition" in data
    
    def test_get_weather_forecast(self):
        """Test getting weather forecast"""
        response = self.client.get(
            "/api/v1/weather/forecast?location=São Paulo&days=5",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 5
    
    def test_create_weather_data(self):
        """Test creating weather data"""
        response = self.client.post(
            "/api/v1/weather",
            json={
                "date": str(date.today()),
                "location": "São Paulo",
                "temperature": 25.5,
                "humidity": 65,
                "precipitation": 0,
                "condition": "sunny"
            },
            headers=self.headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["temperature"] == 25.5
        assert data["condition"] == "sunny"