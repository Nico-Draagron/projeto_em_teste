# backend/app/api/v1/api.py
"""
Main API Router - WeatherBiz Analytics
Consolidates all API endpoints for the application
"""

from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth,
    companies,
    users,
    dashboard,
    correlations,
    predictions,
    settings,
    data_import,
    reports,
    timeseries,
    billing,
    integrations,
    # Already implemented endpoints (mentioned as done)
    sales,
    weather,
    insights,
    alerts,
    notifications,
    exports,
    chat
)

api_router = APIRouter()

# Authentication & Authorization
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"]
)

# Company Management (Multi-tenant)
api_router.include_router(
    companies.router,
    prefix="/companies",
    tags=["Companies"]
)

# User Management
api_router.include_router(
    users.router,
    prefix="/users",
    tags=["Users"]
)

# Dashboard & Analytics
api_router.include_router(
    dashboard.router,
    prefix="/dashboard",
    tags=["Dashboard"]
)

# Correlations Analysis
api_router.include_router(
    correlations.router,
    prefix="/correlations",
    tags=["Correlations"]
)

# ML Predictions
api_router.include_router(
    predictions.router,
    prefix="/predictions",
    tags=["Predictions"]
)

# Settings & Configuration
api_router.include_router(
    settings.router,
    prefix="/settings",
    tags=["Settings"]
)

# Data Import & Upload
api_router.include_router(
    data_import.router,
    prefix="/data-import",
    tags=["Data Import"]
)

# Reports Generation
api_router.include_router(
    reports.router,
    prefix="/reports",
    tags=["Reports"]
)

# Time Series Analysis
api_router.include_router(
    timeseries.router,
    prefix="/timeseries",
    tags=["Time Series"]
)

# Billing & Subscription
api_router.include_router(
    billing.router,
    prefix="/billing",
    tags=["Billing"]
)

# External Integrations
api_router.include_router(
    integrations.router,
    prefix="/integrations",
    tags=["Integrations"]
)

# Sales Data Management (Already implemented)
api_router.include_router(
    sales.router,
    prefix="/sales",
    tags=["Sales"]
)

# Weather Data Management (Already implemented)
api_router.include_router(
    weather.router,
    prefix="/weather",
    tags=["Weather"]
)

# Business Insights (Already implemented)
api_router.include_router(
    insights.router,
    prefix="/insights",
    tags=["Insights"]
)

# Alerts Management (Already implemented)
api_router.include_router(
    alerts.router,
    prefix="/alerts",
    tags=["Alerts"]
)

# Notifications System (Already implemented)
api_router.include_router(
    notifications.router,
    prefix="/notifications",
    tags=["Notifications"]
)

# Data Exports (Already implemented)
api_router.include_router(
    exports.router,
    prefix="/exports",
    tags=["Exports"]
)

# AI Chat Agent (Already implemented)
api_router.include_router(
    chat.router,
    prefix="/chat",
    tags=["AI Chat"]
)