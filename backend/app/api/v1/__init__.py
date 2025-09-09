# backend/app/api/v1/__init__.py
"""
API v1 Package
Contains all endpoint modules for the WeatherBiz Analytics API
"""

from .api import api_router

__all__ = ["api_router"]
