# backend/app/api/v1/endpoints/predictions.py
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.sales import SalesData
from app.models.weather import WeatherData
from app.models.ml_models import MLModel, PredictionHistory
from app.schemas.prediction import (
    PredictionRequest,
    PredictionResponse,
    BatchPrediction,
    ModelPerformance,
    ScenarioSimulation
)
from app.services.ml_service import MLService
from app.services.weather_api_service import WeatherAPIService
import numpy as np
import pandas as pd
import pickle
import joblib

router = APIRouter(prefix="/predictions", tags=["Predictions"])

@router.post("/sales", response_model=PredictionResponse)
async def predict_sales(
    prediction_data: PredictionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Predict sales based on weather conditions
    Using trained ML models specific to the company
    """
    company_id = current_user.company_id
    
    # Get the active ML model for this company
    ml_model = db.query(MLModel).filter(
        MLModel.company_id == company_id,
        MLModel.is_active == True,
        MLModel.model_type == "sales_prediction"
    ).first()
    
    if not ml_model:
        raise HTTPException(
            status_code=404,
            detail="No trained model available. Please train a model first."
        )
    
    # Load the model
    try:
        model = pickle.loads(ml_model.model_data)
        scaler = pickle.loads(ml_model.scaler_data) if ml_model.scaler_data else None
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error loading model: {str(e)}"
        )
    
    # Prepare features
    features = np.array([[
        prediction_data.temperature,
        prediction_data.humidity,
        prediction_data.precipitation,
        prediction_data.wind_speed,
        prediction_data.pressure,
        prediction_data.uv_index or 0,
        prediction_data.day_of_week,
        prediction_data.month,
        prediction_data.is_holiday,
        prediction_data.is_weekend
    ]])
    
    # Scale features if scaler exists
    if scaler:
        features = scaler.transform(features)
    
    # Make prediction
    prediction = model.predict(features)[0]
    
    # Calculate confidence interval (mock for now)
    confidence_lower = prediction * 0.85
    confidence_upper = prediction * 1.15
    
    # Get historical average for comparison
    historical_avg = db.query(func.avg(SalesData.revenue)).filter(
        SalesData.company_id == company_id,
        SalesData.date >= datetime.utcnow() - timedelta(days=365)
    ).scalar() or prediction
    
    # Calculate impact
    impact_percent = ((prediction - historical_avg) / historical_avg * 100) if historical_avg else 0
    
    # Save prediction to history
    prediction_history = PredictionHistory(
        company_id=company_id,
        model_id=ml_model.id,
        prediction_date=prediction_data.date,
        predicted_value=prediction,
        confidence_lower=confidence_lower,
        confidence_upper=confidence_upper,
        features=prediction_data.dict(),
        created_at=datetime.utcnow()
    )
    db.add(prediction_history)
    db.commit()
    
    return {
        "date": prediction_data.date,
        "predicted_sales": round(prediction, 2),
        "confidence_interval": {
            "lower": round(confidence_lower, 2),
            "upper": round(confidence_upper, 2)
        },
        "historical_average": round(historical_avg, 2),
        "impact_percent": round(impact_percent, 2),
        "model_confidence": ml_model.accuracy,
        "factors": {
            "temperature_impact": "positive" if prediction_data.temperature > 25 else "negative",
            "precipitation_impact": "negative" if prediction_data.precipitation > 10 else "neutral",
            "weekend_boost": 1.2 if prediction_data.is_weekend else 1.0
        }
    }

@router.post("/batch", response_model=List[BatchPrediction])
async def predict_batch(
    days_ahead: int = Query(7, ge=1, le=30),
    use_forecast: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Batch predictions for multiple days using weather forecast
    """
    company_id = current_user.company_id
    
    # Get ML model
    ml_model = db.query(MLModel).filter(
        MLModel.company_id == company_id,
        MLModel.is_active == True,
        MLModel.model_type == "sales_prediction"
    ).first()
    
    if not ml_model:
        raise HTTPException(status_code=404, detail="No trained model available")
    
    # Load model
    model = pickle.loads(ml_model.model_data)
    scaler = pickle.loads(ml_model.scaler_data) if ml_model.scaler_data else None
    
    predictions = []
    base_date = datetime.utcnow().date()
    
    # Get weather forecast if requested
    if use_forecast:
        weather_service = WeatherAPIService()
        # Get company location from settings
        company_settings = db.query(CompanySettings).filter(
            CompanySettings.company_id == company_id
        ).first()
        
        location = company_settings.default_location if company_settings else "Sao Paulo"
        forecast_data = await weather_service.get_forecast(location, days_ahead)
    else:
        # Use average historical weather
        avg_weather = db.query(
            func.avg(WeatherData.temperature).label("temp"),
            func.avg(WeatherData.humidity).label("humidity"),
            func.avg(WeatherData.precipitation).label("precip"),
            func.avg(WeatherData.wind_speed).label("wind")
        ).filter(
            WeatherData.company_id == company_id
        ).first()
        
        forecast_data = [{
            "temperature": avg_weather.temp or 20,
            "humidity": avg_weather.humidity or 60,
            "precipitation": avg_weather.precip or 5,
            "wind_speed": avg_weather.wind or 10
        }] * days_ahead
    
    # Generate predictions for each day
    for i in range(days_ahead):
        pred_date = base_date + timedelta(days=i)
        weather = forecast_data[i] if i < len(forecast_data) else forecast_data[-1]
        
        # Prepare features
        features = np.array([[
            weather.get("temperature", 20),
            weather.get("humidity", 60),
            weather.get("precipitation", 0),
            weather.get("wind_speed", 10),
            weather.get("pressure", 1013),
            weather.get("uv_index", 5),
            pred_date.weekday(),
            pred_date.month,
            0,  # is_holiday - could check calendar
            1 if pred_date.weekday() >= 5 else 0  # is_weekend
        ]])
        
        if scaler:
            features = scaler.transform(features)
        
        prediction_value = model.predict(features)[0]
        
        predictions.append({
            "date": pred_date,
            "predicted_sales": round(prediction_value, 2),
            "weather": weather,
            "confidence": ml_model.accuracy,
            "day_type": "Weekend" if pred_date.weekday() >= 5 else "Weekday"
        })
    
    return predictions

@router.get("/performance", response_model=ModelPerformance)
async def get_model_performance(
    days: int = Query(30, ge=7, le=180),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get ML model performance metrics
    """
    company_id = current_user.company_id
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Get predictions vs actual
    predictions = db.query(
        PredictionHistory.prediction_date,
        PredictionHistory.predicted_value,
        SalesData.revenue.label("actual_value")
    ).join(
        SalesData,
        and_(
            PredictionHistory.prediction_date == SalesData.date,
            PredictionHistory.company_id == SalesData.company_id
        )
    ).filter(
        PredictionHistory.company_id == company_id,
        PredictionHistory.created_at >= start_date
    ).all()
    
    if not predictions:
        return {
            "mape": 0,
            "rmse": 0,
            "mae": 0,
            "r_squared": 0,
            "predictions_count": 0,
            "accuracy_trend": []
        }
    
    # Calculate metrics
    actual = np.array([p.actual_value for p in predictions])
    predicted = np.array([p.predicted_value for p in predictions])
    
    mape = np.mean(np.abs((actual - predicted) / actual)) * 100
    rmse = np.sqrt(np.mean((actual - predicted) ** 2))
    mae = np.mean(np.abs(actual - predicted))
    
    # R-squared
    ss_res = np.sum((actual - predicted) ** 2)
    ss_tot = np.sum((actual - np.mean(actual)) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
    
    # Daily accuracy trend
    accuracy_trend = []
    for p in predictions[-7:]:  # Last 7 predictions
        error = abs((p.actual_value - p.predicted_value) / p.actual_value) * 100
        accuracy_trend.append({
            "date": p.prediction_date.strftime("%Y-%m-%d"),
            "accuracy": round(100 - error, 2)
        })
    
    return {
        "mape": round(mape, 2),
        "rmse": round(rmse, 2),
        "mae": round(mae, 2),
        "r_squared": round(r_squared, 4),
        "predictions_count": len(predictions),
        "accuracy_trend": accuracy_trend,
        "last_updated": datetime.utcnow()
    }

@router.post("/simulate", response_model=ScenarioSimulation)
async def simulate_scenario(
    scenario: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Simulate different weather scenarios and their impact
    """
    company_id = current_user.company_id
    
    # Get ML model
    ml_model = db.query(MLModel).filter(
        MLModel.company_id == company_id,
        MLModel.is_active == True
    ).first()
    
    if not ml_model:
        raise HTTPException(status_code=404, detail="No trained model available")
    
    model = pickle.loads(ml_model.model_data)
    scaler = pickle.loads(ml_model.scaler_data) if ml_model.scaler_data else None
    
    # Define scenarios
    scenarios = {
        "heatwave": {
            "temperature": 38,
            "humidity": 30,
            "precipitation": 0,
            "description": "Extreme heat conditions"
        },
        "heavy_rain": {
            "temperature": 18,
            "humidity": 90,
            "precipitation": 50,
            "description": "Heavy rainfall"
        },
        "perfect_day": {
            "temperature": 24,
            "humidity": 60,
            "precipitation": 0,
            "description": "Ideal weather conditions"
        },
        "cold_front": {
            "temperature": 10,
            "humidity": 70,
            "precipitation": 5,
            "description": "Cold weather"
        }
    }
    
    if scenario.get("custom"):
        scenarios["custom"] = scenario["custom"]
    
    results = []
    
    for scenario_name, conditions in scenarios.items():
        features = np.array([[
            conditions["temperature"],
            conditions["humidity"],
            conditions["precipitation"],
            conditions.get("wind_speed", 15),
            conditions.get("pressure", 1013),
            conditions.get("uv_index", 5),
            datetime.utcnow().weekday(),
            datetime.utcnow().month,
            0,
            0
        ]])
        
        if scaler:
            features = scaler.transform(features)
        
        prediction = model.predict(features)[0]
        
        results.append({
            "scenario": scenario_name,
            "conditions": conditions,
            "predicted_sales": round(prediction, 2),
            "description": conditions.get("description", "Custom scenario")
        })
    
    # Sort by predicted sales
    results.sort(key=lambda x: x["predicted_sales"], reverse=True)
    
    return {
        "scenarios": results,
        "best_scenario": results[0]["scenario"],
        "worst_scenario": results[-1]["scenario"],
        "range": {
            "min": results[-1]["predicted_sales"],
            "max": results[0]["predicted_sales"]
        }
    }

@router.post("/retrain")
async def retrain_model(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrain ML model with latest data
    Admin or Manager only
    """
    if current_user.role not in ["admin", "manager"]:
        raise InsufficientPermissionsError("Only admins and managers can retrain models")
    
    company_id = current_user.company_id
    
    # Get training data
    training_data = db.query(
        SalesData.revenue,
        WeatherData.temperature,
        WeatherData.humidity,
        WeatherData.precipitation,
        WeatherData.wind_speed,
        WeatherData.pressure,
        WeatherData.uv_index,
        SalesData.date
    ).join(
        WeatherData,
        and_(
            SalesData.date == WeatherData.date,
            SalesData.company_id == WeatherData.company_id
        )
    ).filter(
        SalesData.company_id == company_id,
        SalesData.date >= datetime.utcnow() - timedelta(days=365)
    ).all()
    
    if len(training_data) < 30:
        raise HTTPException(
            status_code=400,
            detail="Insufficient data for training. Need at least 30 days of data."
        )
    
    # Use ML service to train model
    ml_service = MLService()
    model, scaler, metrics = ml_service.train_sales_model(training_data)
    
    # Save new model
    new_model = MLModel(
        company_id=company_id,
        model_type="sales_prediction",
        model_name=f"Sales Predictor v{datetime.utcnow().strftime('%Y%m%d')}",
        model_data=pickle.dumps(model),
        scaler_data=pickle.dumps(scaler),
        accuracy=metrics["accuracy"],
        features=["temperature", "humidity", "precipitation", "wind_speed"],
        training_date=datetime.utcnow(),
        training_records=len(training_data),
        is_active=True
    )
    
    # Deactivate old models
    db.query(MLModel).filter(
        MLModel.company_id == company_id,
        MLModel.model_type == "sales_prediction"
    ).update({"is_active": False})
    
    db.add(new_model)
    db.commit()
    
    return {
        "message": "Model retrained successfully",
        "model_id": str(new_model.id),
        "accuracy": metrics["accuracy"],
        "training_records": len(training_data)
    }

