
# backend/app/tasks/__init__.py
"""
Tasks assíncronas do WeatherBiz Analytics
"""

from app.core.celery_app import celery_app

__all__ = ["celery_app"]
