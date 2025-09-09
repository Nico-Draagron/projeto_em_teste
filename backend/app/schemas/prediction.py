# ===========================
# backend/app/schemas/prediction.py
# ===========================

from pydantic import Field, validator
from typing import Optional, List, Dict, Any
from datetime import date, datetime

from app.schemas.base import BaseSchema


class PredictionRequest(BaseSchema):
    """Request para previsão"""
    start_date: date
    end_date: date
    product_id: Optional[str] = None
    location_id: Optional[str] = None
    weather_scenario: Optional[Dict[str, float]] = None
    include_confidence: bool = True
    
    @validator("end_date")
    def end_after_start(cls, v, values):
        if "start_date" in values and v < values["start_date"]:
            raise ValueError("end_date must be after start_date")
        return v


class PredictionResponse(BaseSchema):
    """Response de previsão"""
    predictions: List[Dict[str, Any]]
    summary: Dict[str, float]
    confidence_intervals: Optional[Dict[str, Any]] = None
    model_info: Dict[str, Any]
    generated_at: datetime


class ModelPerformance(BaseSchema):
    """Performance do modelo"""
    model_id: str
    model_type: str
    accuracy: float
    mse: float
    mae: float
    r2_score: float
    trained_at: datetime
    training_samples: int
    features: List[str]


class ScenarioSimulation(BaseSchema):
    """Simulação de cenário"""
    scenario_name: str
    weather_conditions: Dict[str, float]
    impact_type: str = Field(..., regex="^(sales|demand|profit)$")
    target_date: Optional[date] = None
    compare_with_baseline: bool = True