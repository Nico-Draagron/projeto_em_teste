# GET/POST /weather, /forecast
# ===========================
# backend/app/api/v1/endpoints/weather.py
# ===========================

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional, Any
from datetime import datetime, date, timedelta

from app.api import deps
from app.models.database import User, Company, WeatherData
from app.models.schemas import (
    WeatherDataCreate,
    WeatherDataResponse,
    WeatherResponse,
    WeatherForecast,
    WeatherMetrics,
    PaginatedResponse
)
from app.services.weather_service import WeatherService, WeatherSource
from app.core.exceptions import WeatherAPIError, DataNotFoundError

router = APIRouter()


@router.get("/current", response_model=WeatherResponse)
async def get_current_weather(
    location_id: Optional[str] = Query(None, description="Location ID"),
    source: str = Query("nomads", description="Data source"),
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Get current weather conditions
    """
    service = WeatherService(db, company.id)
    
    try:
        weather_source = WeatherSource(source)
        current_weather = await service.get_current_weather(
            location_id=location_id,
            source=weather_source
        )
        return current_weather
    except WeatherAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e)
        )


@router.get("/forecast", response_model=List[WeatherForecast])
async def get_weather_forecast(
    days: int = Query(7, ge=1, le=30, description="Number of days"),
    location_id: Optional[str] = Query(None),
    hourly: bool = Query(False, description="Get hourly forecast"),
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Get weather forecast
    """
    service = WeatherService(db, company.id)
    
    try:
        forecast = await service.get_forecast(
            days=days,
            location_id=location_id,
            hourly=hourly
        )
        return forecast
    except WeatherAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e)
        )


@router.get("/historical")
async def get_historical_weather(
    start_date: date = Query(...),
    end_date: date = Query(...),
    location_id: Optional[str] = Query(None),
    variables: Optional[List[str]] = Query(None),
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Get historical weather data
    """
    service = WeatherService(db, company.id)
    
    try:
        historical_data = await service.get_historical_data(
            start_date=datetime.combine(start_date, datetime.min.time()),
            end_date=datetime.combine(end_date, datetime.max.time()),
            location_id=location_id,
            variables=variables
        )
        return {
            "data": historical_data,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }
        }
    except DataNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/trends")
async def analyze_weather_trends(
    period_days: int = Query(30, ge=7, le=365),
    location_id: Optional[str] = Query(None),
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Analyze weather trends
    """
    service = WeatherService(db, company.id)
    
    try:
        trends = await service.analyze_trends(
            period_days=period_days,
            location_id=location_id
        )
        return trends
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing trends: {str(e)}"
        )


@router.get("/extreme-events")
async def get_extreme_weather_events(
    lookback_days: int = Query(90, ge=7, le=365),
    location_id: Optional[str] = Query(None),
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Identify extreme weather events
    """
    service = WeatherService(db, company.id)
    
    try:
        extreme_events = await service.get_extreme_events(
            lookback_days=lookback_days,
            location_id=location_id
        )
        return {
            "events": extreme_events,
            "total": len(extreme_events),
            "period": {
                "start": (datetime.utcnow() - timedelta(days=lookback_days)).isoformat(),
                "end": datetime.utcnow().isoformat()
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error identifying extreme events: {str(e)}"
        )


@router.get("/alerts")
async def get_weather_alerts(
    active_only: bool = Query(True),
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Get official weather alerts
    """
    service = WeatherService(db, company.id)
    
    alerts = await service.get_weather_alerts(active_only=active_only)
    
    return {
        "alerts": alerts,
        "total": len(alerts),
        "active": len([a for a in alerts if a.get("end_time", datetime.utcnow()) >= datetime.utcnow()])
    }


@router.get("/metrics", response_model=WeatherMetrics)
async def calculate_weather_metrics(
    start_date: date = Query(...),
    end_date: date = Query(...),
    location_id: Optional[str] = Query(None),
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Calculate aggregated weather metrics
    """
    service = WeatherService(db, company.id)
    
    try:
        metrics = await service.calculate_metrics(
            start_date=datetime.combine(start_date, datetime.min.time()),
            end_date=datetime.combine(end_date, datetime.max.time()),
            location_id=location_id
        )
        return metrics
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating metrics: {str(e)}"
        )


@router.post("/", response_model=WeatherDataResponse)
async def create_weather_data(
    weather_data: WeatherDataCreate,
    current_user: User = Depends(deps.require_role("manager")),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Manually create weather data entry
    """
    # Check for duplicate
    existing = db.query(WeatherData).filter(
        WeatherData.company_id == company.id,
        WeatherData.date == weather_data.date,
        WeatherData.location_id == weather_data.location_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Weather data for this date/location already exists"
        )
    
    # Create weather data
    db_weather = WeatherData(
        company_id=company.id,
        **weather_data.dict()
    )
    
    db.add(db_weather)
    db.commit()
    db.refresh(db_weather)
    
    return db_weather


@router.post("/sync")
async def sync_weather_data(
    start_date: date = Query(...),
    end_date: date = Query(...),
    source: str = Query("nomads"),
    current_user: User = Depends(deps.require_role("manager")),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Sync weather data from external source
    """
    service = WeatherService(db, company.id)
    
    # This would trigger a background task to fetch and store weather data
    # For now, return a job status
    
    return {
        "message": "Weather sync started",
        "job_id": "sync_job_id",
        "status": "processing",
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat()
        },
        "source": source
    }
