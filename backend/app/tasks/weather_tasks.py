# ===========================
# backend/app/tasks/weather_tasks.py
# ===========================

from typing import List, Dict, Optional
from datetime import datetime, timedelta
from celery import Task
from celery.utils.log import get_task_logger
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.database import Company, WeatherData, Location
from app.services.weather_service import WeatherService, WeatherSource
import httpx

logger = get_task_logger(__name__)


class WeatherTask(Task):
    """Base class para tasks de weather com retry automático"""
    
    autoretry_for = (httpx.HTTPError, ConnectionError)
    retry_kwargs = {"max_retries": 3, "countdown": 60}
    retry_backoff = True
    retry_jitter = True


@celery_app.task(base=WeatherTask, name="fetch_weather_data")
def fetch_weather_data(company_id: str, location_id: str, source: str = "nomads") -> Dict:
    """
    Busca dados climáticos para uma localização específica
    """
    logger.info(f"Fetching weather data for company {company_id}, location {location_id}")
    
    db = SessionLocal()
    try:
        service = WeatherService(db, company_id)
        
        # Buscar dados da API
        weather_data = service.fetch_external_weather(
            location_id=location_id,
            source=WeatherSource(source)
        )
        
        # Salvar no banco
        for data_point in weather_data:
            existing = db.query(WeatherData).filter(
                WeatherData.company_id == company_id,
                WeatherData.location_id == location_id,
                WeatherData.date == data_point["date"]
            ).first()
            
            if not existing:
                weather_record = WeatherData(
                    company_id=company_id,
                    location_id=location_id,
                    **data_point
                )
                db.add(weather_record)
        
        db.commit()
        
        logger.info(f"Successfully fetched {len(weather_data)} weather records")
        return {
            "status": "success",
            "records_fetched": len(weather_data),
            "company_id": company_id,
            "location_id": location_id
        }
        
    except Exception as e:
        logger.error(f"Error fetching weather data: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(name="fetch_all_companies_weather")
def fetch_all_companies_weather() -> Dict:
    """
    Busca dados climáticos para todas as empresas ativas
    """
    logger.info("Starting weather fetch for all companies")
    
    db = SessionLocal()
    results = []
    
    try:
        # Buscar todas as empresas ativas
        companies = db.query(Company).filter(
            Company.is_active == True
        ).all()
        
        for company in companies:
            # Buscar locations da empresa
            locations = db.query(Location).filter(
                Location.company_id == company.id
            ).all()
            
            for location in locations:
                # Agendar task individual para cada location
                task = fetch_weather_data.apply_async(
                    args=[company.id, location.id, "nomads"],
                    queue="weather"
                )
                results.append({
                    "company_id": company.id,
                    "location_id": location.id,
                    "task_id": task.id
                })
        
        logger.info(f"Scheduled {len(results)} weather fetch tasks")
        return {
            "status": "success",
            "tasks_scheduled": len(results),
            "details": results
        }
        
    except Exception as e:
        logger.error(f"Error scheduling weather tasks: {str(e)}")
        raise
    finally:
        db.close()
