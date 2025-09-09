# ===========================
# backend/app/schemas/sales.py
# ===========================

from pydantic import Field, validator
from typing import Optional, List, Dict, Any
from datetime import date, datetime, time
from decimal import Decimal

from app.schemas.base import BaseSchema, TenantSchema, TimestampSchema


class SalesDataBase(BaseSchema):
    """Base sales data schema"""
    date: date
    time: Optional[time] = None
    location_id: Optional[str] = None
    product_id: Optional[str] = None
    quantity: float = Field(..., gt=0)
    revenue: float = Field(..., ge=0)
    cost: Optional[float] = Field(None, ge=0)
    transactions: Optional[int] = Field(None, ge=0)
    customer_count: Optional[int] = Field(None, ge=0)
    
    @validator("revenue")
    def validate_revenue(cls, v, values):
        if v < 0:
            raise ValueError("Revenue cannot be negative")
        return v


class SalesDataCreate(SalesDataBase, TenantSchema):
    """Schema para criação de dados de vendas"""
    metadata: Optional[Dict[str, Any]] = None


class SalesDataUpdate(BaseSchema):
    """Schema para atualização de dados de vendas"""
    quantity: Optional[float] = Field(None, gt=0)
    revenue: Optional[float] = Field(None, ge=0)
    cost: Optional[float] = Field(None, ge=0)
    transactions: Optional[int] = Field(None, ge=0)
    customer_count: Optional[int] = Field(None, ge=0)
    metadata: Optional[Dict[str, Any]] = None


class SalesDataResponse(SalesDataBase, TenantSchema, TimestampSchema):
    """Schema de resposta de dados de vendas"""
    id: int
    profit: Optional[float] = None
    average_ticket: Optional[float] = None
    
    @validator("profit", pre=True, always=True)
    def calculate_profit(cls, v, values):
        if "revenue" in values and "cost" in values and values["cost"]:
            return values["revenue"] - values["cost"]
        return v


class SalesMetrics(BaseSchema):
    """Métricas de vendas"""
    total_revenue: float
    total_quantity: float
    total_transactions: int
    average_daily_revenue: float
    average_ticket: float
    growth_rate: float
    best_day: date
    worst_day: date
    trend: str = Field(..., regex="^(up|down|stable)$")


class SalesAnalysis(BaseSchema):
    """Análise de vendas"""
    period: Dict[str, date]
    metrics: SalesMetrics
    by_product: List[Dict[str, Any]]
    by_location: List[Dict[str, Any]]
    by_weekday: List[Dict[str, Any]]
    seasonality: Dict[str, float]
    anomalies: List[Dict[str, Any]]


class SalesImport(BaseSchema):
    """Schema para importação de vendas"""
    file_format: str = Field(..., regex="^(csv|excel|json)$")
    date_column: str = "date"
    revenue_column: str = "revenue"
    quantity_column: str = "quantity"
    product_column: Optional[str] = None
    location_column: Optional[str] = None
    skip_rows: int = Field(0, ge=0)
    encoding: str = "utf-8"