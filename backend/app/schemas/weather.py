# ===========================
# backend/app/schemas/weather.py
# ===========================

from pydantic import Field, validator
from typing import Optional, List, Dict, Any
from datetime import date, datetime, time

from app.schemas.base import BaseSchema, TenantSchema, TimestampSchema


class WeatherDataBase(BaseSchema):
    """Base weather data schema"""
    date: date
    time: Optional[time] = None
    location_id: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=-100, le=100)
    feels_like: Optional[float] = Field(None, ge=-100, le=100)
    temp_min: Optional[float] = Field(None, ge=-100, le=100)
    temp_max: Optional[float] = Field(None, ge=-100, le=100)
    pressure: Optional[float] = Field(None, ge=800, le=1100)
    humidity: Optional[float] = Field(None, ge=0, le=100)
    wind_speed: Optional[float] = Field(None, ge=0)
    wind_direction: Optional[float] = Field(None, ge=0, le=360)
    cloudiness: Optional[float] = Field(None, ge=0, le=100)
    precipitation: Optional[float] = Field(None, ge=0)
    weather_condition: Optional[str] = None
    weather_description: Optional[str] = None
    visibility: Optional[float] = Field(None, ge=0)
    uv_index: Optional[float] = Field(None, ge=0, le=15)


class WeatherDataCreate(WeatherDataBase, TenantSchema):
    """Schema para criação de dados climáticos"""
    source: str = Field(default="manual")
    raw_data: Optional[Dict[str, Any]] = None


class WeatherDataResponse(WeatherDataBase, TenantSchema, TimestampSchema):
    """Schema de resposta de dados climáticos"""
    id: int
    source: str


class WeatherForecast(WeatherDataBase):
    """Schema para previsão do tempo"""
    forecast_date: datetime
    probability_of_precipitation: Optional[float] = Field(None, ge=0, le=100)
    confidence: Optional[float] = Field(None, ge=0, le=100)


class WeatherMetrics(BaseSchema):
    """Métricas climáticas"""
    avg_temperature: float
    min_temperature: float
    max_temperature: float
    avg_humidity: float
    total_precipitation: float
    avg_wind_speed: float
    sunny_days: int
    rainy_days: int
    cloudy_days: int


class WeatherAlert(BaseSchema):
    """Alerta climático"""
    alert_type: str
    severity: str = Field(..., regex="^(low|medium|high|critical)$")
    title: str
    description: str
    start_time: datetime
    end_time: Optional[datetime] = None
    affected_locations: List[str]
    recommendations: List[str]