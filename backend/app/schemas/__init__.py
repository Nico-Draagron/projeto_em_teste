# backend/app/schemas/__init__.py
"""
Pydantic schemas para validação e serialização
"""

from app.schemas.user import (
    UserBase, UserCreate, UserUpdate, UserResponse,
    UserLogin, UserRegister, PasswordReset
)
from app.schemas.company import (
    CompanyBase, CompanyCreate, CompanyUpdate, CompanyResponse,
    CompanySettings, CompanyStats
)
from app.schemas.auth import (
    Token, TokenPayload, RefreshToken,
    LoginResponse, RegisterResponse
)
from app.schemas.sales import (
    SalesDataBase, SalesDataCreate, SalesDataUpdate, SalesDataResponse,
    SalesMetrics, SalesAnalysis, SalesImport
)
from app.schemas.weather import (
    WeatherDataBase, WeatherDataCreate, WeatherDataResponse,
    WeatherForecast, WeatherMetrics, WeatherAlert
)
from app.schemas.alert import (
    AlertBase, AlertCreate, AlertUpdate, AlertResponse,
    AlertRuleBase, AlertRuleCreate, AlertRuleResponse
)
from app.schemas.notification import (
    NotificationBase, NotificationCreate, NotificationResponse,
    NotificationPreferences, NotificationBatch
)
from app.schemas.prediction import (
    PredictionRequest, PredictionResponse,
    ModelPerformance, ScenarioSimulation
)
from app.schemas.export import (
    ExportRequest, ExportResponse, ExportJobStatus,
    ReportTemplate, ScheduledReport
)
from app.schemas.chat import (
    ChatMessage, ChatResponse, ChatHistory,
    AIInsight, ConversationContext
)

__all__ = [
    # User
    "UserBase", "UserCreate", "UserUpdate", "UserResponse",
    "UserLogin", "UserRegister", "PasswordReset",
    
    # Company
    "CompanyBase", "CompanyCreate", "CompanyUpdate", "CompanyResponse",
    "CompanySettings", "CompanyStats",
    
    # Auth
    "Token", "TokenPayload", "RefreshToken",
    "LoginResponse", "RegisterResponse",
    
    # Sales
    "SalesDataBase", "SalesDataCreate", "SalesDataUpdate", "SalesDataResponse",
    "SalesMetrics", "SalesAnalysis", "SalesImport",
    
    # Weather
    "WeatherDataBase", "WeatherDataCreate", "WeatherDataResponse",
    "WeatherForecast", "WeatherMetrics", "WeatherAlert",
    
    # Alerts
    "AlertBase", "AlertCreate", "AlertUpdate", "AlertResponse",
    "AlertRuleBase", "AlertRuleCreate", "AlertRuleResponse",
    
    # Notifications
    "NotificationBase", "NotificationCreate", "NotificationResponse",
    "NotificationPreferences", "NotificationBatch",
    
    # Predictions
    "PredictionRequest", "PredictionResponse",
    "ModelPerformance", "ScenarioSimulation",
    
    # Export
    "ExportRequest", "ExportResponse", "ExportJobStatus",
    "ReportTemplate", "ScheduledReport",
    
    # Chat
    "ChatMessage", "ChatResponse", "ChatHistory",
    "AIInsight", "ConversationContext"
]