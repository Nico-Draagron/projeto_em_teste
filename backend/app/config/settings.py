"""
Configurações centralizadas da aplicação Asterion.
Multi-tenant SaaS para análise de impacto climático em vendas.
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import field_validator, PostgresDsn, RedisDsn, EmailStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
import secrets


class Settings(BaseSettings):
    """
    Configurações da aplicação usando Pydantic BaseSettings.
    Carrega variáveis de ambiente automaticamente.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )
    
    # ==================== APLICAÇÃO ====================
    PROJECT_NAME: str = "Asterion"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False
    
    # Base path do projeto
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    
    # ==================== SEGURANÇA ====================
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Security Headers
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",  # Vite default
        "http://localhost:8000",
        "https://localhost:3000",
    ]
    
    # ==================== DATABASE ====================
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "climauser"
    POSTGRES_PASSWORD: str = "climapass"
    POSTGRES_DB: str = "climadb"
    POSTGRES_PORT: int = 5432
    
    # Database URL construída dinamicamente
    DATABASE_URL: Optional[PostgresDsn] = None
    
    @field_validator("DATABASE_URL", mode="before")
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        # Constrói a URL do PostgreSQL
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",  # Async driver
            username=values.data.get("POSTGRES_USER"),
            password=values.data.get("POSTGRES_PASSWORD"),
            host=values.data.get("POSTGRES_SERVER"),
            port=values.data.get("POSTGRES_PORT"),
            path=values.data.get("POSTGRES_DB"),
        )
    
    # Pool de conexões
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_PRE_PING: bool = True
    DB_ECHO: bool = False  # SQL logging
    
    # ==================== REDIS ====================
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    # Redis URL construída dinamicamente
    REDIS_URL: Optional[RedisDsn] = None
    
    @field_validator("REDIS_URL", mode="before")
    def assemble_redis_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        # Constrói a URL do Redis
        password = values.data.get("REDIS_PASSWORD")
        if password:
            return f"redis://:{password}@{values.data.get('REDIS_HOST')}:{values.data.get('REDIS_PORT')}/{values.data.get('REDIS_DB')}"
        return f"redis://{values.data.get('REDIS_HOST')}:{values.data.get('REDIS_PORT')}/{values.data.get('REDIS_DB')}"
    
    # Cache TTL (segundos)
    CACHE_TTL_DEFAULT: int = 3600  # 1 hora
    CACHE_TTL_WEATHER: int = 1800  # 30 minutos para dados climáticos
    CACHE_TTL_ML_PREDICTIONS: int = 300  # 5 minutos para previsões
    
    # ==================== APIs EXTERNAS ====================
    # Google Gemini AI
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-pro"
    GEMINI_MAX_TOKENS: int = 2048
    GEMINI_TEMPERATURE: float = 0.7
    
    # NOMADS Weather API
    NOMADS_API_URL: str = "https://nomads.ncep.noaa.gov"
    NOMADS_API_USER: Optional[str] = None
    NOMADS_API_PASS: Optional[str] = None
    NOMADS_UPDATE_INTERVAL: int = 3600  # Atualização a cada hora
    
    # WhatsApp Business API
    WHATSAPP_API_URL: Optional[str] = None
    WHATSAPP_API_TOKEN: Optional[str] = None
    WHATSAPP_PHONE_NUMBER_ID: Optional[str] = None
    
    # ==================== EMAIL (SMTP) ====================
    SMTP_TLS: bool = True
    SMTP_PORT: int = 587
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_USER: Optional[EmailStr] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: Optional[EmailStr] = None
    EMAILS_FROM_NAME: str = "Asterion"
    
    # Templates de email
    EMAIL_TEMPLATES_DIR: str = "app/templates/email"
    
    # ==================== MACHINE LEARNING ====================
    ML_MODELS_PATH: Path = BASE_DIR / "app" / "ml" / "models"
    ML_MODEL_VERSION: str = "v1.0"
    ML_RETRAIN_INTERVAL_DAYS: int = 30
    ML_MIN_DATA_POINTS: int = 100  # Mínimo de pontos para treinar
    
    # ==================== MULTI-TENANCY ====================
    # Configurações para isolamento de dados por empresa
    TENANT_HEADER_NAME: str = "X-Company-ID"
    ENABLE_MULTI_TENANT: bool = True
    MAX_COMPANIES_PER_USER: int = 5
    
    # Limites por plano (futuro billing)
    PLAN_LIMITS: Dict[str, Dict[str, int]] = {
        "free": {
            "max_users": 3,
            "max_alerts": 10,
            "max_api_calls_daily": 1000,
            "data_retention_days": 30
        },
        "starter": {
            "max_users": 10,
            "max_alerts": 50,
            "max_api_calls_daily": 10000,
            "data_retention_days": 90
        },
        "professional": {
            "max_users": 50,
            "max_alerts": 200,
            "max_api_calls_daily": 100000,
            "data_retention_days": 365
        },
        "enterprise": {
            "max_users": -1,  # Ilimitado
            "max_alerts": -1,
            "max_api_calls_daily": -1,
            "data_retention_days": -1
        }
    }
    
    # ==================== RATE LIMITING ====================
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    RATE_LIMIT_PER_DAY: int = 10000
    
    # ==================== LOGGING ====================
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: Optional[str] = "logs/app.log"
    
    # ==================== NOTIFICAÇÕES ====================
    NOTIFICATION_CHANNELS: List[str] = ["internal", "email", "whatsapp"]
    NOTIFICATION_RETRY_ATTEMPTS: int = 3
    NOTIFICATION_RETRY_DELAY: int = 60  # segundos
    
    # ==================== EXPORTS ====================
    EXPORT_MAX_ROWS: int = 100000
    EXPORT_FORMATS: List[str] = ["csv", "excel", "pdf"]
    EXPORT_TEMP_DIR: str = "/tmp/exports"
    
    # ==================== MONITORING ====================
    PROMETHEUS_ENABLED: bool = True
    PROMETHEUS_PORT: int = 9090
    
    # ==================== DESENVOLVIMENTO ====================
    # Primeiro superusuário (criado automaticamente em dev)
    FIRST_SUPERUSER: EmailStr = "admin@weatherbiz.com"
    FIRST_SUPERUSER_PASSWORD: str = "changeme123"
    FIRST_COMPANY_NAME: str = "Asterion Demo Company"
    
    # ==================== CELERY (Tarefas Assíncronas) ====================
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None
    
    @field_validator("CELERY_BROKER_URL", mode="before")
    def get_celery_broker(cls, v: Optional[str], values: Dict[str, Any]) -> str:
        if v:
            return v
        # Usa Redis como broker padrão
        return values.data.get("REDIS_URL", "redis://localhost:6379/1")
    
    @field_validator("CELERY_RESULT_BACKEND", mode="before")
    def get_celery_backend(cls, v: Optional[str], values: Dict[str, Any]) -> str:
        if v:
            return v
        # Usa Redis como backend padrão
        return values.data.get("REDIS_URL", "redis://localhost:6379/2")
    
    class Config:
        """Configuração do Pydantic."""
        case_sensitive = True
        env_file = ".env"
        env_file_encoding = "utf-8"
        
        # Validação de tipos
        validate_assignment = True
        
        # Schema JSON
        json_schema_extra = {
            "example": {
                "PROJECT_NAME": "Asterion",
                "DEBUG": False,
                "DATABASE_URL": "postgresql://user:pass@localhost/db",
                "REDIS_URL": "redis://localhost:6379/0"
            }
        }


# Instância global das configurações
settings = Settings()

# Validação de configurações críticas em produção
if not settings.DEBUG:
    assert settings.SECRET_KEY != "changeme", "SECRET_KEY deve ser alterada em produção!"
    assert settings.FIRST_SUPERUSER_PASSWORD != "changeme123", "Senha padrão deve ser alterada!"
    assert settings.DATABASE_URL, "DATABASE_URL é obrigatória!"
    assert settings.REDIS_URL, "REDIS_URL é obrigatória!"

# Export
__all__ = ["settings", "Settings"]