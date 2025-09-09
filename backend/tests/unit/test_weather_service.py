# tests/unit/test_weather_service.py
import pytest
from app.services.weather_service import WeatherService

@pytest.fixture
def weather_service():
    return WeatherService()

def test_get_current_weather_none(weather_service):
    weather = weather_service.get_current_weather()
    assert weather is None
