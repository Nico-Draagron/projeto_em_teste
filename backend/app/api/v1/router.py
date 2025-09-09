# Router principal da API v1
# ===========================
# backend/app/api/v1/router.py (ATUALIZADO)
# ===========================
"""
Main API router that includes all endpoint routers
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    companies,
    users,
    sales,
    weather,
    insights,
    alerts,
    notifications,
    exports,
    chat,
    predictions,
    dashboard,
    correlations,
    settings,
    data_import,
    reports,
    timeseries,
    billing,
    integrations
)

api_router = APIRouter()

# Authentication & Authorization
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"]
)

# Company Management
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

# Sales Data
api_router.include_router(
    sales.router,
    prefix="/sales",
    tags=["Sales"]
)

# Weather Data
api_router.include_router(
    weather.router,
    prefix="/weather",
    tags=["Weather"]
)

# Insights & Analysis
api_router.include_router(
    insights.router,
    prefix="/insights",
    tags=["Insights"]
)

# Predictions & ML
api_router.include_router(
    predictions.router,
    prefix="/predictions",
    tags=["Predictions"]
)

# Correlations
api_router.include_router(
    correlations.router,
    prefix="/correlations",
    tags=["Correlations"]
)

# Time Series
api_router.include_router(
    timeseries.router,
    prefix="/timeseries",
    tags=["Time Series"]
)

# Alerts
api_router.include_router(
    alerts.router,
    prefix="/alerts",
    tags=["Alerts"]
)

# Notifications
api_router.include_router(
    notifications.router,
    prefix="/notifications",
    tags=["Notifications"]
)

# Reports & Exports
api_router.include_router(
    exports.router,
    prefix="/exports",
    tags=["Exports"]
)

api_router.include_router(
    reports.router,
    prefix="/reports",
    tags=["Reports"]
)

# Chat & AI
api_router.include_router(
    chat.router,
    prefix="/chat",
    tags=["AI Chat"]
)

# Dashboard
api_router.include_router(
    dashboard.router,
    prefix="/dashboard",
    tags=["Dashboard"]
)

# Data Import
api_router.include_router(
    data_import.router,
    prefix="/import",
    tags=["Data Import"]
)

# Settings
api_router.include_router(
    settings.router,
    prefix="/settings",
    tags=["Settings"]
)

# Billing & Subscriptions
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