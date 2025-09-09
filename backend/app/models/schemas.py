# Pydantic Models (request/response)
"""
Schemas Pydantic para validação de dados de entrada/saída da API.
Centraliza todos os schemas do sistema WeatherBiz Analytics.
"""

from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date, time
from decimal import Decimal
from pydantic import (
    BaseModel, EmailStr, Field, ConfigDict,
    field_validator, model_validator
)
from enum import Enum

# Importa enums dos models
from app.config.security import UserRole, Permission
from app.models.notification import NotificationType, NotificationPriority, NotificationChannel
from app.models.alert import AlertType, AlertSeverity, AlertStatus
from app.models.export import ExportFormat, ExportType
from app.models.ml_model import ModelType

# ==================== BASE SCHEMAS ====================

class BaseSchema(BaseModel):
    """Schema base com configurações padrão."""
    
    model_config = ConfigDict(
        from_attributes=True,  # Permite criar de SQLAlchemy models
        validate_assignment=True,  # Valida ao atribuir valores
        arbitrary_types_allowed=True,  # Permite tipos arbitrários
        str_strip_whitespace=True,  # Remove espaços em branco
        json_encoders={
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }
    )


class TimestampSchema(BaseSchema):
    """Schema com timestamps."""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PaginationParams(BaseModel):
    """Parâmetros de paginação."""
    page: int = Field(1, ge=1, description="Número da página")
    page_size: int = Field(20, ge=1, le=100, description="Tamanho da página")
    sort_by: Optional[str] = Field(None, description="Campo para ordenação")
    sort_order: str = Field("desc", pattern="^(asc|desc)$", description="Ordem")


class PaginatedResponse(BaseModel):
    """Resposta paginada."""
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool


# ==================== USER SCHEMAS ====================

class UserBase(BaseSchema):
    """Base para schemas de usuário."""
    email: EmailStr
    username: Optional[str] = None
    full_name: str
    phone: Optional[str] = None
    role: UserRole = UserRole.USER
    timezone: str = "America/Sao_Paulo"
    language: str = "pt-BR"


class UserCreate(UserBase):
    """Schema para criar usuário."""
    password: str = Field(..., min_length=8, max_length=100)
    company_id: Optional[int] = None
    
    @field_validator('password')
    def validate_password(cls, v):
        """Valida força da senha."""
        if len(v) < 8:
            raise ValueError('Senha deve ter no mínimo 8 caracteres')
        if not any(c.isupper() for c in v):
            raise ValueError('Senha deve conter pelo menos uma letra maiúscula')
        if not any(c.islower() for c in v):
            raise ValueError('Senha deve conter pelo menos uma letra minúscula')
        if not any(c.isdigit() for c in v):
            raise ValueError('Senha deve conter pelo menos um número')
        return v


class UserUpdate(BaseSchema):
    """Schema para atualizar usuário."""
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[UserRole] = None
    timezone: Optional[str] = None
    language: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    is_active: Optional[bool] = None


class UserInDB(UserBase):
    """Schema de usuário no banco."""
    id: int
    company_id: int
    is_active: bool = True
    is_verified: bool = False
    is_superuser: bool = False
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime] = None


class UserResponse(UserInDB):
    """Schema de resposta de usuário."""
    company: Optional["CompanyResponse"] = None
    permissions: List[str] = []


class PasswordChange(BaseSchema):
    """Schema para mudança de senha."""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)


class PasswordReset(BaseSchema):
    """Schema para reset de senha."""
    token: str
    new_password: str = Field(..., min_length=8, max_length=100)


# ==================== COMPANY SCHEMAS ====================

class CompanyBase(BaseSchema):
    """Base para schemas de empresa."""
    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=100)
    business_type: str = "other"
    email: EmailStr
    phone: Optional[str] = None
    website: Optional[str] = None
    timezone: str = "America/Sao_Paulo"
    currency: str = "BRL"
    language: str = "pt-BR"


class CompanyCreate(CompanyBase):
    """Schema para criar empresa."""
    legal_name: Optional[str] = None
    cnpj: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    
    @field_validator('cnpj')
    def validate_cnpj(cls, v):
        """Valida CNPJ se fornecido."""
        if v:
            # Remove caracteres não numéricos
            cnpj = ''.join(c for c in v if c.isdigit())
            if len(cnpj) != 14:
                raise ValueError('CNPJ deve ter 14 dígitos')
        return v


class CompanyUpdate(BaseSchema):
    """Schema para atualizar empresa."""
    name: Optional[str] = None
    business_type: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    timezone: Optional[str] = None
    currency: Optional[str] = None
    language: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None


class CompanyInDB(CompanyBase):
    """Schema de empresa no banco."""
    id: int
    plan: str = "free"
    status: str = "trial"
    current_users_count: int = 0
    current_alerts_count: int = 0
    created_at: datetime
    updated_at: datetime


class CompanyResponse(CompanyInDB):
    """Schema de resposta de empresa."""
    trial_days_left: Optional[int] = None
    usage_percentage: Dict[str, float] = {}
    can_add_user: bool = True
    can_add_alert: bool = True


# ==================== AUTH SCHEMAS ====================

class LoginRequest(BaseSchema):
    """Schema para login."""
    email: EmailStr
    password: str


class TokenResponse(BaseSchema):
    """Schema de resposta de token."""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseSchema):
    """Schema para refresh token."""
    refresh_token: str


# ==================== WEATHER SCHEMAS ====================

class WeatherStationBase(BaseSchema):
    """Base para schemas de estação meteorológica."""
    name: str
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    city: Optional[str] = None
    state: Optional[str] = None
    country: str = "BR"


class WeatherStationCreate(WeatherStationBase):
    """Schema para criar estação."""
    code: Optional[str] = None
    source: str = "NOMADS"
    altitude: Optional[float] = None
    is_primary: bool = False


class WeatherStationUpdate(BaseSchema):
    """Schema para atualizar estação."""
    name: Optional[str] = None
    is_primary: Optional[bool] = None
    is_active: Optional[bool] = None


class WeatherStationResponse(WeatherStationBase):
    """Schema de resposta de estação."""
    id: int
    company_id: int
    is_primary: bool
    is_active: bool
    last_update: Optional[datetime] = None
    created_at: datetime


class WeatherDataBase(BaseSchema):
    """Base para schemas de dados climáticos."""
    date: date
    temperature: Optional[float] = None
    temperature_min: Optional[float] = None
    temperature_max: Optional[float] = None
    precipitation: Optional[float] = None
    humidity: Optional[float] = None
    wind_speed: Optional[float] = None
    weather_condition: Optional[str] = None


class WeatherDataCreate(WeatherDataBase):
    """Schema para criar dados climáticos."""
    station_id: int
    hour: Optional[int] = Field(None, ge=0, le=23)
    is_forecast: bool = False
    feels_like: Optional[float] = None
    pressure: Optional[float] = None
    wind_direction: Optional[int] = Field(None, ge=0, le=360)
    visibility: Optional[float] = None
    uv_index: Optional[float] = None
    cloud_cover: Optional[float] = Field(None, ge=0, le=100)


class WeatherDataResponse(WeatherDataBase):
    """Schema de resposta de dados climáticos."""
    id: int
    station_id: int
    company_id: int
    is_forecast: bool
    comfort_level: str
    heat_index: Optional[float] = None
    created_at: datetime


class WeatherForecast(BaseSchema):
    """Schema para previsão do tempo."""
    date: date
    temperature_min: float
    temperature_max: float
    precipitation_probability: float
    weather_condition: str
    weather_description: str
    weather_icon: Optional[str] = None


# ==================== SALES SCHEMAS ====================

class ProductCategoryBase(BaseSchema):
    """Base para schemas de categoria."""
    name: str
    slug: str
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None


class ProductCategoryCreate(ProductCategoryBase):
    """Schema para criar categoria."""
    parent_id: Optional[int] = None
    weather_sensitive: bool = True
    sensitivity_factors: Optional[Dict[str, Any]] = None


class ProductCategoryResponse(ProductCategoryBase):
    """Schema de resposta de categoria."""
    id: int
    company_id: int
    parent_id: Optional[int] = None
    is_active: bool
    weather_sensitive: bool


class ProductBase(BaseSchema):
    """Base para schemas de produto."""
    sku: str
    name: str
    price: Decimal = Field(..., gt=0)
    currency: str = "BRL"


class ProductCreate(ProductBase):
    """Schema para criar produto."""
    description: Optional[str] = None
    category_id: Optional[int] = None
    cost: Optional[Decimal] = Field(None, gt=0)
    stock_quantity: Optional[int] = Field(None, ge=0)
    is_seasonal: bool = False
    weather_sensitive: bool = True


class ProductUpdate(BaseSchema):
    """Schema para atualizar produto."""
    name: Optional[str] = None
    price: Optional[Decimal] = Field(None, gt=0)
    cost: Optional[Decimal] = Field(None, gt=0)
    stock_quantity: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class ProductResponse(ProductBase):
    """Schema de resposta de produto."""
    id: int
    company_id: int
    category_id: Optional[int] = None
    is_active: bool
    is_seasonal: bool
    weather_sensitive: bool
    margin: Optional[float] = None
    is_in_season: bool


class SalesDataBase(BaseSchema):
    """Base para schemas de vendas."""
    date: date
    quantity: int = Field(..., ge=0)
    revenue: Decimal = Field(..., ge=0)


class SalesDataCreate(SalesDataBase):
    """Schema para criar dados de vendas."""
    product_id: Optional[int] = None
    product_name: Optional[str] = None
    category_name: Optional[str] = None
    store_id: Optional[str] = None
    store_name: Optional[str] = None
    cost: Optional[Decimal] = Field(None, ge=0)
    discount: Optional[Decimal] = Field(None, ge=0)
    transactions_count: Optional[int] = Field(None, ge=0)
    customers_count: Optional[int] = Field(None, ge=0)


class SalesDataResponse(SalesDataBase):
    """Schema de resposta de vendas."""
    id: int
    company_id: int
    product_id: Optional[int] = None
    profit: Optional[Decimal] = None
    margin: Optional[float] = None
    average_price: Optional[float] = None
    weather_condition_at_sale: Optional[str] = None
    temperature_at_sale: Optional[float] = None


class SalesAnalysis(BaseSchema):
    """Schema para análise de vendas."""
    period: str  # daily, weekly, monthly, yearly
    total_revenue: Decimal
    total_quantity: int
    average_ticket: Decimal
    growth_rate: float
    top_products: List[Dict[str, Any]]
    weather_impact: Dict[str, Any]


# ==================== ALERT SCHEMAS ====================

class AlertRuleBase(BaseSchema):
    """Base para schemas de regra de alerta."""
    name: str
    type: AlertType
    severity: AlertSeverity
    conditions: Dict[str, Any]
    monitor_field: str


class AlertRuleCreate(AlertRuleBase):
    """Schema para criar regra de alerta."""
    description: Optional[str] = None
    condition_logic: str = "AND"
    monitor_source: str = "weather"
    threshold_value: Optional[float] = None
    check_frequency: int = 3600
    cooldown_minutes: int = 60
    notification_channels: List[str] = []
    notification_recipients: List[int] = []


class AlertRuleUpdate(BaseSchema):
    """Schema para atualizar regra de alerta."""
    name: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[AlertSeverity] = None
    conditions: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class AlertRuleResponse(AlertRuleBase):
    """Schema de resposta de regra de alerta."""
    id: int
    company_id: int
    is_active: bool
    trigger_count: int
    last_triggered: Optional[datetime] = None


class AlertBase(BaseSchema):
    """Base para schemas de alerta."""
    title: str
    message: str
    type: AlertType
    severity: AlertSeverity


class AlertCreate(AlertBase):
    """Schema para criar alerta manual."""
    trigger_data: Optional[Dict[str, Any]] = None
    expires_at: Optional[datetime] = None
    recommendations: Optional[List[str]] = None


class AlertResponse(AlertBase):
    """Schema de resposta de alerta."""
    id: int
    company_id: int
    status: AlertStatus
    triggered_at: datetime
    trigger_value: Optional[float] = None
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    is_expired: bool
    duration: Optional[int] = None
    response_time: Optional[int] = None


# ==================== NOTIFICATION SCHEMAS ====================

class NotificationBase(BaseSchema):
    """Base para schemas de notificação."""
    type: NotificationType
    priority: NotificationPriority
    title: str
    message: str


class NotificationCreate(NotificationBase):
    """Schema para criar notificação."""
    user_id: int
    channels: List[NotificationChannel] = [NotificationChannel.INTERNAL]
    data: Optional[Dict[str, Any]] = None
    action_url: Optional[str] = None
    action_text: Optional[str] = None
    scheduled_for: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class NotificationResponse(NotificationBase):
    """Schema de resposta de notificação."""
    id: int
    user_id: int
    company_id: int
    status: str
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime


class NotificationPreferenceUpdate(BaseSchema):
    """Schema para atualizar preferências de notificação."""
    email_enabled: Optional[bool] = None
    whatsapp_enabled: Optional[bool] = None
    push_enabled: Optional[bool] = None
    system_notifications: Optional[bool] = None
    alert_notifications: Optional[bool] = None
    insight_notifications: Optional[bool] = None
    report_notifications: Optional[bool] = None
    min_priority: Optional[NotificationPriority] = None


# ==================== CHAT SCHEMAS ====================

class ChatMessageBase(BaseSchema):
    """Base para schemas de mensagem de chat."""
    message: str
    message_type: str = "text"


class ChatMessageCreate(ChatMessageBase):
    """Schema para criar mensagem de chat."""
    context_data: Optional[Dict[str, Any]] = None


class ChatMessageResponse(ChatMessageBase):
    """Schema de resposta de mensagem de chat."""
    id: int
    role: str
    response_data: Optional[Dict[str, Any]] = None
    intent: Optional[str] = None
    entities: Optional[Dict[str, Any]] = None
    confidence_score: Optional[float] = None
    created_at: datetime


class ChatContextResponse(BaseSchema):
    """Schema de resposta de contexto de chat."""
    id: int
    session_id: str
    title: Optional[str] = None
    message_count: int
    is_active: bool
    started_at: datetime
    last_activity: datetime
    messages: List[ChatMessageResponse] = []


# ==================== EXPORT SCHEMAS ====================

class ExportJobBase(BaseSchema):
    """Base para schemas de job de exportação."""
    name: str
    type: ExportType
    format: ExportFormat


class ExportJobCreate(ExportJobBase):
    """Schema para criar job de exportação."""
    template_id: Optional[int] = None
    config: Dict[str, Any]
    filters: Dict[str, Any] = {}
    date_start: Optional[datetime] = None
    date_end: Optional[datetime] = None
    notify_on_complete: bool = True


class ExportJobResponse(ExportJobBase):
    """Schema de resposta de job de exportação."""
    id: int
    job_id: str
    company_id: int
    status: str
    progress: int
    file_url: Optional[str] = None
    file_size_bytes: Optional[int] = None
    row_count: Optional[int] = None
    is_ready: bool
    is_expired: bool
    created_at: datetime
    completed_at: Optional[datetime] = None


# ==================== ML SCHEMAS ====================

class MLModelBase(BaseSchema):
    """Base para schemas de modelo ML."""
    name: str
    type: ModelType
    algorithm: str


class MLModelCreate(MLModelBase):
    """Schema para criar modelo ML."""
    version: str
    description: Optional[str] = None
    features: List[str]
    target_variable: str
    hyperparameters: Dict[str, Any] = {}


class MLModelResponse(MLModelBase):
    """Schema de resposta de modelo ML."""
    id: int
    company_id: int
    version: str
    status: str
    is_primary: bool
    accuracy: Optional[float] = None
    rmse: Optional[float] = None
    r2_score: Optional[float] = None
    trained_at: Optional[datetime] = None
    prediction_count: int


class PredictionRequest(BaseSchema):
    """Schema para requisição de predição."""
    model_id: Optional[int] = None
    model_type: Optional[ModelType] = None
    features: Dict[str, Any]
    date_range: Optional[Dict[str, date]] = None


class PredictionResponse(BaseSchema):
    """Schema de resposta de predição."""
    model_id: int
    model_name: str
    prediction: Union[float, List[float], Dict[str, Any]]
    confidence: float
    explanation: Optional[str] = None
    timestamp: datetime


# ==================== INSIGHTS SCHEMAS ====================

class InsightBase(BaseSchema):
    """Base para schemas de insight."""
    type: str  # correlation, trend, anomaly, recommendation
    title: str
    description: str
    importance: str  # low, medium, high, critical


class InsightResponse(InsightBase):
    """Schema de resposta de insight."""
    id: Optional[int] = None
    data: Dict[str, Any]
    confidence: float
    source: str
    created_at: datetime


class CorrelationAnalysis(BaseSchema):
    """Schema para análise de correlação."""
    variable1: str
    variable2: str
    correlation_coefficient: float
    p_value: float
    significance: str  # none, weak, moderate, strong
    sample_size: int
    period: Dict[str, date]


# ==================== DASHBOARD SCHEMAS ====================

class DashboardKPI(BaseSchema):
    """Schema para KPI do dashboard."""
    name: str
    value: Union[float, int, str]
    change: Optional[float] = None
    change_type: str = "percent"  # percent, absolute
    trend: str = "neutral"  # up, down, neutral
    period: str  # today, week, month, year


class DashboardWidget(BaseSchema):
    """Schema para widget do dashboard."""
    type: str  # chart, table, kpi, map
    title: str
    data: Dict[str, Any]
    config: Dict[str, Any] = {}
    position: Dict[str, int]  # x, y, width, height


class DashboardResponse(BaseSchema):
    """Schema de resposta do dashboard."""
    kpis: List[DashboardKPI]
    widgets: List[DashboardWidget]
    last_update: datetime
    alerts_count: int
    notifications_count: int


# ==================== REPORT SCHEMAS ====================

class ReportRequest(BaseSchema):
    """Schema para requisição de relatório."""
    template_id: Optional[int] = None
    type: str
    format: ExportFormat = ExportFormat.PDF
    date_start: date
    date_end: date
    filters: Dict[str, Any] = {}
    include_charts: bool = True
    include_insights: bool = True


class ReportSection(BaseSchema):
    """Schema para seção de relatório."""
    title: str
    type: str  # text, chart, table, insights
    content: Union[str, Dict[str, Any], List[Any]]
    order: int


class ReportResponse(BaseSchema):
    """Schema de resposta de relatório."""
    title: str
    subtitle: Optional[str] = None
    generated_at: datetime
    period: Dict[str, date]
    sections: List[ReportSection]
    export_url: Optional[str] = None


# ==================== ERROR SCHEMAS ====================

class ErrorResponse(BaseSchema):
    """Schema de resposta de erro."""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime
    request_id: Optional[str] = None


class ValidationErrorResponse(ErrorResponse):
    """Schema de erro de validação."""
    fields: Dict[str, List[str]]


# ==================== SUCCESS SCHEMAS ====================

class SuccessResponse(BaseSchema):
    """Schema de resposta de sucesso genérica."""
    success: bool = True
    message: str
    data: Optional[Any] = None


class DeleteResponse(BaseSchema):
    """Schema de resposta de exclusão."""
    success: bool = True
    message: str = "Recurso excluído com sucesso"
    deleted_id: int


# ==================== HEALTH CHECK ====================

class HealthCheckResponse(BaseSchema):
    """Schema de health check."""
    status: str = "healthy"
    timestamp: datetime
    version: str
    services: Dict[str, str]  # database, redis, ml_models, etc.


# Update forward references
UserResponse.model_rebuild()
CompanyResponse.model_rebuild()

# Export all schemas
__all__ = [
    # Base
    "BaseSchema",
    "TimestampSchema",
    "PaginationParams",
    "PaginatedResponse",
    
    # User
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserInDB",
    "UserResponse",
    "PasswordChange",
    "PasswordReset",
    
    # Company
    "CompanyBase",
    "CompanyCreate",
    "CompanyUpdate",
    "CompanyInDB",
    "CompanyResponse",
    
    # Auth
    "LoginRequest",
    "TokenResponse",
    "RefreshTokenRequest",
    
    # Weather
    "WeatherStationBase",
    "WeatherStationCreate",
    "WeatherStationUpdate",
    "WeatherStationResponse",
    "WeatherDataBase",
    "WeatherDataCreate",
    "WeatherDataResponse",
    "WeatherForecast",
    
    # Sales
    "ProductCategoryBase",
    "ProductCategoryCreate",
    "ProductCategoryResponse",
    "ProductBase",
    "ProductCreate",
    "ProductUpdate",
    "ProductResponse",
    "SalesDataBase",
    "SalesDataCreate",
    "SalesDataResponse",
    "SalesAnalysis",
    
    # Alert
    "AlertRuleBase",
    "AlertRuleCreate",
    "AlertRuleUpdate",
    "AlertRuleResponse",
    "AlertBase",
    "AlertCreate",
    "AlertResponse",
    
    # Notification
    "NotificationBase",
    "NotificationCreate",
    "NotificationResponse",
    "NotificationPreferenceUpdate",
    
    # Chat
    "ChatMessageBase",
    "ChatMessageCreate",
    "ChatMessageResponse",
    "ChatContextResponse",
    
    # Export
    "ExportJobBase",
    "ExportJobCreate",
    "ExportJobResponse",
    
    # ML
    "MLModelBase",
    "MLModelCreate",
    "MLModelResponse",
    "PredictionRequest",
    "PredictionResponse",
    
    # Insights
    "InsightBase",
    "InsightResponse",
    "CorrelationAnalysis",
    
    # Dashboard
    "DashboardKPI",
    "DashboardWidget",
    "DashboardResponse",
    
    # Report
    "ReportRequest",
    "ReportSection",
    "ReportResponse",
    
    # Error & Success
    "ErrorResponse",
    "ValidationErrorResponse",
    "SuccessResponse",
    "DeleteResponse",
    
    # Health
    "HealthCheckResponse"
]