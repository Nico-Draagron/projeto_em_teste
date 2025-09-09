# Lógica de dados climáticos
"""
Service de dados climáticos para o sistema WeatherBiz Analytics.
Gerencia dados meteorológicos e integração com NOMADS.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta, timezone
import logging
import asyncio
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.orm import selectinload

from app.models.weather import WeatherStation, WeatherData
from app.models.company import Company
from app.models.schemas import (
    WeatherDataCreate, WeatherDataResponse,
    WeatherForecast, PaginationParams, PaginatedResponse
)
from app.core.exceptions import (
    NotFoundError, ValidationError, ExternalServiceError,
    WeatherAPIError, TenantAccessDenied
)
from app.integrations.nomads_api import NOMADSClient
from app.core.utils import date_range
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class WeatherService:
    """Service para gerenciamento de dados climáticos."""
    
    def __init__(self, db: AsyncSession, redis_client: Optional[redis.Redis] = None):
        """
        Inicializa o service.
        
        Args:
            db: Sessão do banco de dados
            redis_client: Cliente Redis para cache
        """
        self.db = db
        self.redis = redis_client
        self.nomads_client = NOMADSClient()
        self.cache_ttl = 1800  # 30 minutos
    
    async def get_current_weather(
        self,
        company_id: int,
        station_id: Optional[int] = None,
        use_cache: bool = True
    ) -> WeatherDataResponse:
        """
        Obtém dados climáticos atuais.
        
        Args:
            company_id: ID da empresa
            station_id: ID da estação (opcional, usa primária se não fornecido)
            use_cache: Se deve usar cache
            
        Returns:
            WeatherDataResponse: Dados climáticos atuais
            
        Raises:
            NotFoundError: Se estação não encontrada
        """
        # Busca estação
        if not station_id:
            station = await self._get_primary_station(company_id)
        else:
            station = await self._get_station(station_id, company_id)
        
        # Verifica cache
        if use_cache and self.redis:
            cache_key = f"weather:current:{station.id}"
            cached = await self.redis.get(cache_key)
            if cached:
                import json
                return WeatherDataResponse(**json.loads(cached))
        
        # Busca dados mais recentes do banco
        today = date.today()
        query = select(WeatherData).where(
            and_(
                WeatherData.station_id == station.id,
                WeatherData.date == today,
                WeatherData.is_forecast == False
            )
        ).order_by(desc(WeatherData.created_at)).limit(1)
        
        result = await self.db.execute(query)
        weather_data = result.scalar_one_or_none()
        
        # Se não tem dados recentes, busca da API
        if not weather_data or self._is_outdated(weather_data):
            weather_data = await self._fetch_current_weather(station)
        
        response = WeatherDataResponse.model_validate(weather_data)
        
        # Salva no cache
        if self.redis:
            cache_key = f"weather:current:{station.id}"
            await self.redis.setex(
                cache_key,
                self.cache_ttl,
                response.model_dump_json()
            )
        
        return response
    
    async def get_weather_forecast(
        self,
        company_id: int,
        days: int = 7,
        station_id: Optional[int] = None
    ) -> List[WeatherForecast]:
        """
        Obtém previsão do tempo.
        
        Args:
            company_id: ID da empresa
            days: Número de dias de previsão
            station_id: ID da estação
            
        Returns:
            List[WeatherForecast]: Previsões
        """
        # Busca estação
        if not station_id:
            station = await self._get_primary_station(company_id)
        else:
            station = await self._get_station(station_id, company_id)
        
        # Cache key
        if self.redis:
            cache_key = f"weather:forecast:{station.id}:{days}"
            cached = await self.redis.get(cache_key)
            if cached:
                import json
                data = json.loads(cached)
                return [WeatherForecast(**item) for item in data]
        
        # Busca previsões do banco
        start_date = date.today()
        end_date = start_date + timedelta(days=days)
        
        query = select(WeatherData).where(
            and_(
                WeatherData.station_id == station.id,
                WeatherData.date >= start_date,
                WeatherData.date <= end_date,
                WeatherData.is_forecast == True
            )
        ).order_by(WeatherData.date)
        
        result = await self.db.execute(query)
        forecasts = result.scalars().all()
        
        # Se não tem previsões suficientes, busca da API
        if len(forecasts) < days:
            forecasts = await self._fetch_weather_forecast(station, days)
        
        # Converte para response
        forecast_list = []
        for forecast in forecasts:
            forecast_list.append(WeatherForecast(
                date=forecast.date,
                temperature_min=float(forecast.temperature_min or 0),
                temperature_max=float(forecast.temperature_max or 0),
                precipitation_probability=float(forecast.precipitation_probability or 0),
                weather_condition=forecast.weather_condition or "unknown",
                weather_description=forecast.weather_description or "",
                weather_icon=forecast.weather_icon
            ))
        
        # Cache
        if self.redis and forecast_list:
            cache_key = f"weather:forecast:{station.id}:{days}"
            data = [f.model_dump() for f in forecast_list]
            await self.redis.setex(cache_key, self.cache_ttl, json.dumps(data))
        
        return forecast_list
    
    async def get_historical_weather(
        self,
        company_id: int,
        start_date: date,
        end_date: date,
        station_id: Optional[int] = None,
        aggregation: str = "daily"
    ) -> List[Dict[str, Any]]:
        """
        Obtém dados históricos de clima.
        
        Args:
            company_id: ID da empresa
            start_date: Data inicial
            end_date: Data final
            station_id: ID da estação
            aggregation: Tipo de agregação (daily, weekly, monthly)
            
        Returns:
            List[Dict]: Dados históricos agregados
        """
        # Validação de datas
        if start_date > end_date:
            raise ValidationError("Data inicial deve ser anterior à final")
        
        if (end_date - start_date).days > 365:
            raise ValidationError("Período máximo de 365 dias")
        
        # Busca estação
        if not station_id:
            station = await self._get_primary_station(company_id)
        else:
            station = await self._get_station(station_id, company_id)
        
        # Query base
        query = select(WeatherData).where(
            and_(
                WeatherData.station_id == station.id,
                WeatherData.date >= start_date,
                WeatherData.date <= end_date,
                WeatherData.is_forecast == False
            )
        ).order_by(WeatherData.date)
        
        result = await self.db.execute(query)
        weather_data = result.scalars().all()
        
        # Verifica se precisa buscar dados faltantes
        existing_dates = {wd.date for wd in weather_data}
        expected_dates = set(date_range(start_date, end_date))
        missing_dates = expected_dates - existing_dates
        
        if missing_dates:
            # Busca dados faltantes da API
            await self._fetch_historical_data(station, list(missing_dates))
            
            # Re-executa query
            result = await self.db.execute(query)
            weather_data = result.scalars().all()
        
        # Agrega dados conforme solicitado
        if aggregation == "daily":
            return self._aggregate_daily(weather_data)
        elif aggregation == "weekly":
            return self._aggregate_weekly(weather_data)
        elif aggregation == "monthly":
            return self._aggregate_monthly(weather_data)
        else:
            raise ValidationError(f"Agregação inválida: {aggregation}")
    
    async def sync_weather_data(
        self,
        company_id: int,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Sincroniza dados climáticos com API externa.
        
        Args:
            company_id: ID da empresa
            force: Se deve forçar atualização
            
        Returns:
            dict: Resultado da sincronização
        """
        # Busca todas as estações ativas da empresa
        query = select(WeatherStation).where(
            and_(
                WeatherStation.company_id == company_id,
                WeatherStation.is_active == True
            )
        )
        result = await self.db.execute(query)
        stations = result.scalars().all()
        
        if not stations:
            raise ValidationError("Nenhuma estação meteorológica configurada")
        
        results = {
            "stations_updated": 0,
            "data_points_added": 0,
            "errors": []
        }
        
        for station in stations:
            try:
                # Verifica se precisa atualizar
                if not force and station.last_update:
                    elapsed = datetime.now(timezone.utc) - station.last_update
                    if elapsed.total_seconds() < station.update_frequency:
                        continue
                
                # Busca dados atuais
                current_data = await self._fetch_current_weather(station)
                
                # Busca previsão
                forecast_data = await self._fetch_weather_forecast(station, 7)
                
                # Atualiza timestamp
                station.last_update = datetime.now(timezone.utc)
                
                results["stations_updated"] += 1
                results["data_points_added"] += 1 + len(forecast_data)
                
            except Exception as e:
                logger.error(f"Error syncing station {station.id}: {e}")
                results["errors"].append({
                    "station_id": station.id,
                    "station_name": station.name,
                    "error": str(e)
                })
        
        await self.db.commit()
        
        logger.info(f"Weather sync completed for company {company_id}: {results}")
        
        return results
    
    async def analyze_weather_trends(
        self,
        company_id: int,
        period_days: int = 30,
        station_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Analisa tendências climáticas.
        
        Args:
            company_id: ID da empresa
            period_days: Período de análise em dias
            station_id: ID da estação
            
        Returns:
            dict: Análise de tendências
        """
        # Busca estação
        if not station_id:
            station = await self._get_primary_station(company_id)
        else:
            station = await self._get_station(station_id, company_id)
        
        # Período de análise
        end_date = date.today()
        start_date = end_date - timedelta(days=period_days)
        
        # Busca dados
        query = select(WeatherData).where(
            and_(
                WeatherData.station_id == station.id,
                WeatherData.date >= start_date,
                WeatherData.date <= end_date,
                WeatherData.is_forecast == False
            )
        )
        
        result = await self.db.execute(query)
        weather_data = result.scalars().all()
        
        if not weather_data:
            return {
                "period_days": period_days,
                "data_points": 0,
                "message": "Dados insuficientes para análise"
            }
        
        # Calcula estatísticas
        temps = [float(wd.temperature) for wd in weather_data if wd.temperature]
        precips = [float(wd.precipitation) for wd in weather_data if wd.precipitation]
        humidities = [float(wd.humidity) for wd in weather_data if wd.humidity]
        
        analysis = {
            "period_days": period_days,
            "data_points": len(weather_data),
            "temperature": {
                "average": sum(temps) / len(temps) if temps else 0,
                "min": min(temps) if temps else 0,
                "max": max(temps) if temps else 0,
                "trend": self._calculate_trend(temps)
            },
            "precipitation": {
                "total": sum(precips) if precips else 0,
                "average": sum(precips) / len(precips) if precips else 0,
                "rainy_days": len([p for p in precips if p > 0]),
                "trend": self._calculate_trend(precips)
            },
            "humidity": {
                "average": sum(humidities) / len(humidities) if humidities else 0,
                "min": min(humidities) if humidities else 0,
                "max": max(humidities) if humidities else 0,
                "trend": self._calculate_trend(humidities)
            }
        }
        
        # Identifica eventos extremos
        extreme_events = []
        for wd in weather_data:
            if wd.is_extreme:
                extreme_events.append({
                    "date": wd.date.isoformat(),
                    "type": wd.extreme_type,
                    "description": wd.weather_description
                })
        
        analysis["extreme_events"] = extreme_events
        analysis["extreme_events_count"] = len(extreme_events)
        
        return analysis
    
    async def detect_weather_anomalies(
        self,
        company_id: int,
        reference_period_days: int = 365,
        threshold_std: float = 2.0
    ) -> List[Dict[str, Any]]:
        """
        Detecta anomalias climáticas.
        
        Args:
            company_id: ID da empresa
            reference_period_days: Período de referência
            threshold_std: Threshold em desvios padrão
            
        Returns:
            List[Dict]: Anomalias detectadas
        """
        station = await self._get_primary_station(company_id)
        
        # Período de referência
        end_date = date.today()
        start_date = end_date - timedelta(days=reference_period_days)
        
        # Busca dados históricos
        query = select(WeatherData).where(
            and_(
                WeatherData.station_id == station.id,
                WeatherData.date >= start_date,
                WeatherData.date <= end_date,
                WeatherData.is_forecast == False
            )
        )
        
        result = await self.db.execute(query)
        historical_data = result.scalars().all()
        
        if len(historical_data) < 30:
            return []
        
        # Calcula estatísticas de referência
        temps = [float(wd.temperature) for wd in historical_data if wd.temperature]
        mean_temp = sum(temps) / len(temps)
        std_temp = (sum((t - mean_temp) ** 2 for t in temps) / len(temps)) ** 0.5
        
        # Detecta anomalias nos últimos 7 dias
        recent_query = select(WeatherData).where(
            and_(
                WeatherData.station_id == station.id,
                WeatherData.date >= end_date - timedelta(days=7),
                WeatherData.is_forecast == False
            )
        )
        
        recent_result = await self.db.execute(recent_query)
        recent_data = recent_result.scalars().all()
        
        anomalies = []
        for wd in recent_data:
            if wd.temperature:
                temp_z_score = (float(wd.temperature) - mean_temp) / std_temp if std_temp > 0 else 0
                
                if abs(temp_z_score) > threshold_std:
                    anomalies.append({
                        "date": wd.date.isoformat(),
                        "type": "temperature",
                        "value": float(wd.temperature),
                        "expected_range": {
                            "min": mean_temp - threshold_std * std_temp,
                            "max": mean_temp + threshold_std * std_temp
                        },
                        "z_score": temp_z_score,
                        "severity": "high" if abs(temp_z_score) > 3 else "medium"
                    })
        
        return anomalies
    
    # ==================== HELPERS ====================
    
    async def _get_station(
        self,
        station_id: int,
        company_id: int
    ) -> WeatherStation:
        """Busca estação com validação de tenant."""
        query = select(WeatherStation).where(
            and_(
                WeatherStation.id == station_id,
                WeatherStation.company_id == company_id
            )
        )
        result = await self.db.execute(query)
        station = result.scalar_one_or_none()
        
        if not station:
            raise NotFoundError("WeatherStation", station_id)
        
        return station
    
    async def _get_primary_station(self, company_id: int) -> WeatherStation:
        """Busca estação primária da empresa."""
        query = select(WeatherStation).where(
            and_(
                WeatherStation.company_id == company_id,
                WeatherStation.is_primary == True
            )
        )
        result = await self.db.execute(query)
        station = result.scalar_one_or_none()
        
        if not station:
            # Se não tem primária, pega a primeira ativa
            query = select(WeatherStation).where(
                and_(
                    WeatherStation.company_id == company_id,
                    WeatherStation.is_active == True
                )
            ).limit(1)
            result = await self.db.execute(query)
            station = result.scalar_one_or_none()
        
        if not station:
            raise NotFoundError("Estação meteorológica não configurada")
        
        return station
    
    async def _fetch_current_weather(self, station: WeatherStation) -> WeatherData:
        """Busca dados atuais da API."""
        try:
            # Busca da API NOMADS
            data = await self.nomads_client.get_current_weather(
                lat=float(station.latitude),
                lon=float(station.longitude)
            )
            
            # Salva no banco
            weather_data = WeatherData(
                station_id=station.id,
                company_id=station.company_id,
                date=date.today(),
                hour=datetime.now().hour,
                is_forecast=False,
                temperature=Decimal(str(data.get("temperature", 0))),
                feels_like=Decimal(str(data.get("feels_like", 0))),
                humidity=Decimal(str(data.get("humidity", 0))),
                pressure=Decimal(str(data.get("pressure", 0))),
                wind_speed=Decimal(str(data.get("wind_speed", 0))),
                wind_direction=data.get("wind_direction"),
                precipitation=Decimal(str(data.get("precipitation", 0))),
                cloud_cover=Decimal(str(data.get("cloud_cover", 0))),
                visibility=Decimal(str(data.get("visibility", 10))),
                uv_index=Decimal(str(data.get("uv_index", 0))),
                weather_condition=data.get("weather_condition", "clear"),
                weather_description=data.get("weather_description", ""),
                weather_icon=data.get("weather_icon"),
                raw_data=data
            )
            
            self.db.add(weather_data)
            await self.db.commit()
            await self.db.refresh(weather_data)
            
            return weather_data
            
        except Exception as e:
            logger.error(f"Error fetching current weather: {e}")
            raise WeatherAPIError(f"Erro ao buscar dados climáticos: {str(e)}")
    
    async def _fetch_weather_forecast(
        self,
        station: WeatherStation,
        days: int
    ) -> List[WeatherData]:
        """Busca previsão da API."""
        try:
            # Busca da API NOMADS
            forecast_data = await self.nomads_client.get_forecast(
                lat=float(station.latitude),
                lon=float(station.longitude),
                days=days
            )
            
            forecasts = []
            for day_data in forecast_data:
                forecast = WeatherData(
                    station_id=station.id,
                    company_id=station.company_id,
                    date=day_data["date"],
                    is_forecast=True,
                    forecast_date=datetime.now(timezone.utc),
                    temperature_min=Decimal(str(day_data.get("temp_min", 0))),
                    temperature_max=Decimal(str(day_data.get("temp_max", 0))),
                    temperature=Decimal(str(day_data.get("temp_avg", 0))),
                    precipitation=Decimal(str(day_data.get("precipitation", 0))),
                    precipitation_probability=Decimal(str(day_data.get("precipitation_prob", 0))),
                    humidity=Decimal(str(day_data.get("humidity", 0))),
                    wind_speed=Decimal(str(day_data.get("wind_speed", 0))),
                    weather_condition=day_data.get("weather_condition", "clear"),
                    weather_description=day_data.get("weather_description", ""),
                    weather_icon=day_data.get("weather_icon"),
                    raw_data=day_data
                )
                
                forecasts.append(forecast)
                self.db.add(forecast)
            
            await self.db.commit()
            
            return forecasts
            
        except Exception as e:
            logger.error(f"Error fetching forecast: {e}")
            raise WeatherAPIError(f"Erro ao buscar previsão: {str(e)}")
    
    async def _fetch_historical_data(
        self,
        station: WeatherStation,
        dates: List[date]
    ) -> None:
        """Busca dados históricos da API."""
        # TODO: Implementar busca em batch da API NOMADS
        # Por ora, simula com dados aleatórios para desenvolvimento
        pass
    
    def _is_outdated(self, weather_data: WeatherData) -> bool:
        """Verifica se dados estão desatualizados."""
        if not weather_data.created_at:
            return True
        
        elapsed = datetime.now(timezone.utc) - weather_data.created_at
        return elapsed.total_seconds() > 3600  # 1 hora
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calcula tendência de uma série."""
        if len(values) < 2:
            return "stable"
        
        # Calcula regressão linear simples
        n = len(values)
        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(values) / n
        
        numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return "stable"
        
        slope = numerator / denominator
        
        # Determina tendência baseada no slope
        if slope > 0.1:
            return "increasing"
        elif slope < -0.1:
            return "decreasing"
        else:
            return "stable"
    
    def _aggregate_daily(self, weather_data: List[WeatherData]) -> List[Dict[str, Any]]:
        """Agrega dados por dia."""
        daily_data = {}
        
        for wd in weather_data:
            key = wd.date.isoformat()
            
            if key not in daily_data:
                daily_data[key] = {
                    "date": key,
                    "temperature_min": float(wd.temperature_min) if wd.temperature_min else None,
                    "temperature_max": float(wd.temperature_max) if wd.temperature_max else None,
                    "temperature_avg": [],
                    "precipitation_total": 0,
                    "humidity_avg": [],
                    "wind_speed_avg": [],
                    "weather_conditions": []
                }
            
            if wd.temperature:
                daily_data[key]["temperature_avg"].append(float(wd.temperature))
            if wd.precipitation:
                daily_data[key]["precipitation_total"] += float(wd.precipitation)
            if wd.humidity:
                daily_data[key]["humidity_avg"].append(float(wd.humidity))
            if wd.wind_speed:
                daily_data[key]["wind_speed_avg"].append(float(wd.wind_speed))
            if wd.weather_condition:
                daily_data[key]["weather_conditions"].append(wd.weather_condition)
        
        # Calcula médias
        for key in daily_data:
            data = daily_data[key]
            if data["temperature_avg"]:
                data["temperature_avg"] = sum(data["temperature_avg"]) / len(data["temperature_avg"])
            else:
                data["temperature_avg"] = None
            
            if data["humidity_avg"]:
                data["humidity_avg"] = sum(data["humidity_avg"]) / len(data["humidity_avg"])
            else:
                data["humidity_avg"] = None
            
            if data["wind_speed_avg"]:
                data["wind_speed_avg"] = sum(data["wind_speed_avg"]) / len(data["wind_speed_avg"])
            else:
                data["wind_speed_avg"] = None
            
            # Condição predominante
            if data["weather_conditions"]:
                from collections import Counter
                data["weather_condition"] = Counter(data["weather_conditions"]).most_common(1)[0][0]
            else:
                data["weather_condition"] = None
            
            del data["weather_conditions"]
        
        return list(daily_data.values())
    
    def _aggregate_weekly(self, weather_data: List[WeatherData]) -> List[Dict[str, Any]]:
        """Agrega dados por semana."""
        # TODO: Implementar agregação semanal
        return self._aggregate_daily(weather_data)
    
    def _aggregate_monthly(self, weather_data: List[WeatherData]) -> List[Dict[str, Any]]:
        """Agrega dados por mês."""
        # TODO: Implementar agregação mensal
        return self._aggregate_daily(weather_data)