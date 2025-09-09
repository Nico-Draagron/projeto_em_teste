"""
Models do sistema WeatherBiz Analytics.
Centraliza importação de todos os modelos SQLAlchemy.
"""

# Importa modelos para registro no Base.metadata
from app.models.user import User
from app.models.company import Company, CompanyPlan
from app.models.notification import Notification, NotificationPreference
from app.models.weather import WeatherData, WeatherStation
from app.models.sales import SalesData, Product, ProductCategory
from app.models.alert import Alert, AlertRule, AlertHistory
from app.models.chat import ChatHistory, ChatContext
from app.models.export import ExportJob, ExportTemplate
from app.models.ml_model import MLModel, ModelTrainingJob, ModelPerformance

# Export all models
__all__ = [
    # User & Company
    "User",
    "Company",
    "CompanyPlan",
    
    # Notifications
    "Notification",
    "NotificationPreference",
    
    # Weather
    "WeatherData",
    "WeatherStation",
    
    # Sales
    "SalesData",
    "Product",
    "ProductCategory",
    
    # Alerts
    "Alert",
    "AlertRule",
    "AlertHistory",
    
    # Chat AI
    "ChatHistory",
    "ChatContext",
    
    # Export
    "ExportJob",
    "ExportTemplate",
    
    # ML
    "MLModel",
    "ModelTrainingJob",
    "ModelPerformance"
]