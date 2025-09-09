"""
Modelo de dados climáticos para o sistema Asterion.
Armazena dados históricos e previsões meteorológicas.
"""

from typing import Optional, TYPE_CHECKING
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import (
    Column, Integer, String, DateTime, Date,
    ForeignKey, Numeric, Index, UniqueConstraint,
    JSON, Boolean
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.config.database import Base, TimestampMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.company import Company


class WeatherStation(Base, TimestampMixin, TenantMixin):
    """
    Estações meteorológicas configuradas por empresa.
    """
    
    __tablename__ = "weather_stations"
    
    # ==================== PRIMARY KEY ====================
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # ==================== STATION INFO ====================
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Nome da estação/localização"
    )
    
    code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        doc="Código da estação meteorológica"
    )
    
    source: Mapped[str] = mapped_column(
        String(50),
        default="NOMADS",
        nullable=False,
        doc="Fonte dos dados (NOMADS, etc)"
    )
    
    # ==================== LOCATION ====================
    latitude: Mapped[Decimal] = mapped_column(
        Numeric(10, 7),
        nullable=False,
        doc="Latitude da estação"
    )
    
    longitude: Mapped[Decimal] = mapped_column(
        Numeric(10, 7),
        nullable=False,
        doc="Longitude da estação"
    )
    
    altitude: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        doc="Altitude em metros"
    )
    
    city: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="Cidade"
    )
    
    state: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        doc="Estado"
    )
    
    country: Mapped[str] = mapped_column(
        String(2),
        default="BR",
        nullable=False,
        doc="País (ISO 2)"
    )
    
    # ==================== CONFIGURATION ====================
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Se é a estação principal da empresa"
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Se está ativa"
    )
    
    update_frequency: Mapped[int] = mapped_column(
        Integer,
        default=3600,
        nullable=False,
        doc="Frequência de atualização em segundos"
    )
    
    last_update: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Última atualização de dados"
    )
    
    # ==================== METADATA ====================
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Metadados adicionais"
    )
    
    # ==================== RELATIONSHIPS ====================
    company: Mapped["Company"] = relationship(
        "Company",
        back_populates="weather_stations"
    )
    
    weather_data: Mapped[list["WeatherData"]] = relationship(
        "WeatherData",
        back_populates="station",
        cascade="all, delete-orphan"
    )
    
    # ==================== INDEXES ====================
    __table_args__ = (
        # Índice único para empresa + nome
        UniqueConstraint("company_id", "name", name="uq_station_company_name"),
        
        # Índices para queries
        Index("idx_station_company_active", "company_id", "is_active"),
        Index("idx_station_location", "latitude", "longitude"),
    )
    
    # ==================== STRING REPRESENTATION ====================
    def __repr__(self) -> str:
        return f"<WeatherStation(id={self.id}, name={self.name})>"
    
    def __str__(self) -> str:
        return f"{self.name} ({self.city}, {self.state})"


class WeatherData(Base, TimestampMixin, TenantMixin):
    """
    Dados climáticos históricos e previsões.
    """
    
    __tablename__ = "weather_data"
    
    # ==================== PRIMARY KEY ====================
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # ==================== STATION REFERENCE ====================
    station_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("weather_stations.id"),
        nullable=False,
        index=True,
        doc="ID da estação meteorológica"
    )
    
    # ==================== TEMPORAL ====================
    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        doc="Data da medição/previsão"
    )
    
    hour: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Hora da medição (0-23)"
    )
    
    is_forecast: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Se é previsão ou dado histórico"
    )
    
    forecast_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Quando a previsão foi feita"
    )
    
    # ==================== TEMPERATURE ====================
    temperature: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        doc="Temperatura em Celsius"
    )
    
    temperature_min: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        doc="Temperatura mínima do dia"
    )
    
    temperature_max: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        doc="Temperatura máxima do dia"
    )
    
    feels_like: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        doc="Sensação térmica"
    )
    
    # ==================== PRECIPITATION ====================
    precipitation: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
        doc="Precipitação em mm"
    )
    
    precipitation_probability: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        doc="Probabilidade de chuva (%)"
    )
    
    snow: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
        doc="Neve em mm"
    )
    
    # ==================== HUMIDITY & PRESSURE ====================
    humidity: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        doc="Umidade relativa (%)"
    )
    
    pressure: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
        doc="Pressão atmosférica (hPa)"
    )
    
    dew_point: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        doc="Ponto de orvalho"
    )
    
    # ==================== WIND ====================
    wind_speed: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        doc="Velocidade do vento (km/h)"
    )
    
    wind_direction: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Direção do vento (graus)"
    )
    
    wind_gust: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        doc="Rajadas de vento (km/h)"
    )
    
    # ==================== VISIBILITY & UV ====================
    visibility: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
        doc="Visibilidade em km"
    )
    
    uv_index: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 1),
        nullable=True,
        doc="Índice UV"
    )
    
    # ==================== CLOUDS & CONDITIONS ====================
    cloud_cover: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        doc="Cobertura de nuvens (%)"
    )
    
    weather_condition: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="Condição do tempo (clear, rain, etc)"
    )
    
    weather_description: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Descrição detalhada"
    )
    
    weather_icon: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        doc="Código do ícone do tempo"
    )
    
    # ==================== EXTREME EVENTS ====================
    is_extreme: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Se é um evento climático extremo"
    )
    
    extreme_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        doc="Tipo de evento extremo"
    )
    
    # ==================== DATA QUALITY ====================
    data_quality: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
        doc="Qualidade dos dados (0-1)"
    )
    
    missing_fields: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        doc="Campos faltantes"
    )
    
    # ==================== RAW DATA ====================
    raw_data: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Dados brutos da API"
    )
    
    # ==================== RELATIONSHIPS ====================
    station: Mapped["WeatherStation"] = relationship(
        "WeatherStation",
        back_populates="weather_data"
    )
    
    # ==================== INDEXES ====================
    __table_args__ = (
        # Índice único para evitar duplicatas
        UniqueConstraint(
            "station_id", "date", "hour", "is_forecast",
            name="uq_weather_station_date_hour"
        ),
        
        # Índices para queries comuns
        Index("idx_weather_company_date", "company_id", "date"),
        Index("idx_weather_station_date", "station_id", "date"),
        Index("idx_weather_date_forecast", "date", "is_forecast"),
        Index("idx_weather_extreme", "is_extreme", "date"),
    )
    
    # ==================== PROPERTIES ====================
    @property
    def heat_index(self) -> Optional[float]:
        """Calcula índice de calor."""
        if self.temperature is None or self.humidity is None:
            return None
        
        T = float(self.temperature)
        RH = float(self.humidity)
        
        # Fórmula simplificada do heat index
        if T < 27:
            return T
        
        HI = -8.78469475556 + 1.61139411 * T + 2.33854883889 * RH
        HI += -0.14611605 * T * RH - 0.012308094 * T * T
        HI += -0.0164248277778 * RH * RH + 0.002211732 * T * T * RH
        HI += 0.00072546 * T * RH * RH - 0.000003582 * T * T * RH * RH
        
        return round(HI, 2)
    
    @property
    def comfort_level(self) -> str:
        """Determina nível de conforto térmico."""
        if self.temperature is None:
            return "unknown"
        
        temp = float(self.temperature)
        
        if temp < 10:
            return "very_cold"
        elif temp < 15:
            return "cold"
        elif temp < 20:
            return "cool"
        elif temp < 26:
            return "comfortable"
        elif temp < 30:
            return "warm"
        elif temp < 35:
            return "hot"
        else:
            return "very_hot"
    
    # ==================== METHODS ====================
    def to_dict(self) -> dict:
        """
        Converte dados climáticos para dicionário.
        
        Returns:
            dict: Dados climáticos
        """
        return {
            "date": self.date.isoformat() if self.date else None,
            "hour": self.hour,
            "is_forecast": self.is_forecast,
            "temperature": float(self.temperature) if self.temperature else None,
            "temperature_min": float(self.temperature_min) if self.temperature_min else None,
            "temperature_max": float(self.temperature_max) if self.temperature_max else None,
            "feels_like": float(self.feels_like) if self.feels_like else None,
            "precipitation": float(self.precipitation) if self.precipitation else None,
            "precipitation_probability": float(self.precipitation_probability) if self.precipitation_probability else None,
            "humidity": float(self.humidity) if self.humidity else None,
            "pressure": float(self.pressure) if self.pressure else None,
            "wind_speed": float(self.wind_speed) if self.wind_speed else None,
            "wind_direction": self.wind_direction,
            "visibility": float(self.visibility) if self.visibility else None,
            "uv_index": float(self.uv_index) if self.uv_index else None,
            "cloud_cover": float(self.cloud_cover) if self.cloud_cover else None,
            "weather_condition": self.weather_condition,
            "weather_description": self.weather_description,
            "weather_icon": self.weather_icon,
            "comfort_level": self.comfort_level,
            "heat_index": self.heat_index
        }
    
    # ==================== STRING REPRESENTATION ====================
    def __repr__(self) -> str:
        return f"<WeatherData(date={self.date}, temp={self.temperature}°C)>"
    
    def __str__(self) -> str:
        return f"{self.date}: {self.temperature}°C, {self.weather_condition}"