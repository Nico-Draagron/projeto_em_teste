# backend/app/core/config.py

import os
from typing import Any, Dict, Optional, List
from pydantic import BaseSettings, PostgresDsn, validator, EmailStr
from pathlib import Path
import secrets

class Settings(BaseSettings):
    """
    Configurações da aplicação usando Pydantic BaseSettings
    """
    
    # API Configuration
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "WeatherBiz Analytics"
    PROJECT_VERSION: str = "1.0.0"
    PROJECT_DESCRIPTION: str = "Platform for weather impact analysis on business"
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_MIN_LENGTH: int = 8
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000"
    ]
    
    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: str | List[str]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    # Database
    DATABASE_URL: Optional[PostgresDsn] = None
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "weatherbiz")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    
    @validator("DATABASE_URL", pre=True)
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        return PostgresDsn.build(
            scheme="postgresql",
            user=values.get("POSTGRES_USER"),
            password=values.get("POSTGRES_PASSWORD"),
            host=values.get("POSTGRES_SERVER"),
            port=values.get("POSTGRES_PORT"),
            path=f"/{values.get('POSTGRES_DB') or ''}",
        )
    
    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")
    REDIS_DB: int = 0
    CACHE_TTL: int = 3600  # 1 hour default
    
    # Email/SMTP
    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    SMTP_PORT: int = 587
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_USER: Optional[str] = os.getenv("SMTP_USER")
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD")
    SMTP_FROM_EMAIL: EmailStr = os.getenv("SMTP_FROM_EMAIL", "noreply@weatherbiz.com")
    SMTP_FROM_NAME: str = "WeatherBiz Analytics"
    
    # External APIs
    NOMADS_API_URL: str = "https://nomads.ncep.noaa.gov"
    OPENWEATHER_API_KEY: Optional[str] = os.getenv("OPENWEATHER_API_KEY")
    OPENWEATHER_BASE_URL: str = "https://api.openweathermap.org/data/2.5"
    INMET_API_URL: str = "https://apitempo.inmet.gov.br"
    
    # Google Gemini AI
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-pro")
    
    # WhatsApp Business API
    WHATSAPP_API_URL: Optional[str] = os.getenv("WHATSAPP_API_URL")
    WHATSAPP_API_TOKEN: Optional[str] = os.getenv("WHATSAPP_API_TOKEN")
    WHATSAPP_PHONE_NUMBER: Optional[str] = os.getenv("WHATSAPP_PHONE_NUMBER")
    
    # File Storage
    UPLOAD_DIR: Path = Path("uploads")
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: List[str] = [".csv", ".xlsx", ".xls", ".json"]
    
    # ML Models
    MODELS_DIR: Path = Path("app/ml/models")
    MODEL_RETRAIN_DAYS: int = 30
    MODEL_MIN_DATA_POINTS: int = 100
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    
    # Feature Flags
    FEATURE_FLAGS: Dict[str, bool] = {
        "ai_agent": True,
        "whatsapp_notifications": False,
        "advanced_ml": True,
        "export_powerpoint": False,
        "multi_location": True
    }
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: Optional[str] = os.getenv("LOG_FILE")
    
    # Monitoring
    SENTRY_DSN: Optional[str] = os.getenv("SENTRY_DSN")
    PROMETHEUS_ENABLED: bool = os.getenv("PROMETHEUS_ENABLED", "false").lower() == "true"
    
    # Support
    SUPPORT_EMAIL: EmailStr = "support@weatherbiz.com"
    DOCUMENTATION_URL: str = "https://docs.weatherbiz.com"
    
    # Development
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    TESTING: bool = os.getenv("TESTING", "false").lower() == "true"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Create settings instance
settings = Settings()


# ===========================
# backend/app/core/security.py
# ===========================

from datetime import datetime, timedelta
from typing import Any, Union, Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session
import secrets
import hashlib
import re
from .config import settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Cria JWT access token
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode = {
        "exp": expire.timestamp(),
        "sub": str(subject),
        "type": "access"
    }
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt


def create_refresh_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Cria JWT refresh token
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
    
    to_encode = {
        "exp": expire.timestamp(),
        "sub": str(subject),
        "type": "refresh"
    }
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica se senha plain text corresponde ao hash
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Gera hash da senha
    """
    return pwd_context.hash(password)


def validate_password(password: str) -> tuple[bool, str]:
    """
    Valida força da senha
    """
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        return False, f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters long"
    
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit"
    
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character"
    
    return True, "Password is valid"


def generate_api_key() -> tuple[str, str]:
    """
    Gera API key e seu hash
    Returns: (api_key, api_key_hash)
    """
    api_key = secrets.token_urlsafe(32)
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    return api_key, api_key_hash


def generate_password_reset_token(email: str) -> str:
    """
    Gera token para reset de senha
    """
    delta = timedelta(hours=1)
    now = datetime.utcnow()
    expires = now + delta
    
    to_encode = {
        "exp": expires.timestamp(),
        "email": email,
        "type": "password_reset"
    }
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt


def verify_password_reset_token(token: str) -> Optional[str]:
    """
    Verifica token de reset de senha
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        
        if payload.get("type") != "password_reset":
            return None
        
        return payload.get("email")
        
    except JWTError:
        return None


def generate_email_verification_token(email: str) -> str:
    """
    Gera token para verificação de email
    """
    delta = timedelta(hours=24)
    now = datetime.utcnow()
    expires = now + delta
    
    to_encode = {
        "exp": expires.timestamp(),
        "email": email,
        "type": "email_verification"
    }
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt


def verify_email_verification_token(token: str) -> Optional[str]:
    """
    Verifica token de verificação de email
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        
        if payload.get("type") != "email_verification":
            return None
        
        return payload.get("email")
        
    except JWTError:
        return None


# ===========================
# backend/app/core/database.py
# ===========================

from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from .config import settings
import logging

logger = logging.getLogger(__name__)

# Create engine
if settings.TESTING:
    # Use in-memory SQLite for testing
    SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=NullPool
    )
else:
    # Use PostgreSQL for development/production
    engine = create_engine(
        str(settings.DATABASE_URL),
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20
    )

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class
Base = declarative_base()

# Metadata for migrations
metadata = MetaData()


def get_db() -> Session:
    """
    Dependency to get database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize database with tables
    """
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {str(e)}")
        raise


# ===========================
# backend/app/core/exceptions.py
# ===========================

from typing import Any, Optional


class WeatherBizException(Exception):
    """Base exception for WeatherBiz application"""
    def __init__(self, message: str = "An error occurred", status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class AuthenticationError(WeatherBizException):
    """Authentication failed"""
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, 401)


class AuthorizationError(WeatherBizException):
    """Authorization failed"""
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, 403)


class ValidationError(WeatherBizException):
    """Validation error"""
    def __init__(self, message: str = "Validation failed", errors: Optional[dict] = None):
        super().__init__(message, 422)
        self.errors = errors or {}


class NotFoundError(WeatherBizException):
    """Resource not found"""
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, 404)


class ConflictError(WeatherBizException):
    """Conflict error"""
    def __init__(self, message: str = "Resource conflict"):
        super().__init__(message, 409)


class TenantError(WeatherBizException):
    """Tenant-related error"""
    def __init__(self, message: str = "Tenant error"):
        super().__init__(message, 400)


class RateLimitError(WeatherBizException):
    """Rate limit exceeded"""
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, 429)


class WeatherAPIError(WeatherBizException):
    """Weather API error"""
    def __init__(self, message: str = "Weather API error"):
        super().__init__(message, 502)


class DataNotFoundError(NotFoundError):
    """Data not found"""
    def __init__(self, message: str = "Data not found"):
        super().__init__(message)


class AnalysisError(WeatherBizException):
    """Analysis error"""
    def __init__(self, message: str = "Analysis failed"):
        super().__init__(message, 500)


class ModelNotFoundError(NotFoundError):
    """ML Model not found"""
    def __init__(self, message: str = "Model not found"):
        super().__init__(message)


class PredictionError(WeatherBizException):
    """Prediction error"""
    def __init__(self, message: str = "Prediction failed"):
        super().__init__(message, 500)


class AlertError(WeatherBizException):
    """Alert error"""
    def __init__(self, message: str = "Alert error"):
        super().__init__(message, 500)


class NotificationError(WeatherBizException):
    """Notification error"""
    def __init__(self, message: str = "Notification error"):
        super().__init__(message, 500)


class ExportError(WeatherBizException):
    """Export error"""
    def __init__(self, message: str = "Export failed"):
        super().__init__(message, 500)


class AIServiceError(WeatherBizException):
    """AI Service error"""
    def __init__(self, message: str = "AI service error"):
        super().__init__(message, 500)


class PaymentError(WeatherBizException):
    """Payment error"""
    def __init__(self, message: str = "Payment processing failed"):
        super().__init__(message, 402)


class IntegrationError(WeatherBizException):
    """External integration error"""
    def __init__(self, message: str = "External integration failed"):
        super().__init__(message, 502)


# ===========================
# backend/app/core/cache.py
# ===========================

import json
import redis.asyncio as redis
from typing import Optional, Any, Union
from datetime import timedelta
import pickle
import logging
from .config import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Manager for Redis cache operations
    """
    
    def __init__(self):
        self.redis_client = None
        self.default_ttl = settings.CACHE_TTL
        
    async def connect(self):
        """
        Connect to Redis
        """
        try:
            self.redis_client = await redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD,
                db=settings.REDIS_DB,
                decode_responses=False  # For binary data support
            )
            
            # Test connection
            await self.redis_client.ping()
            logger.info("Connected to Redis cache")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            self.redis_client = None
    
    async def disconnect(self):
        """
        Disconnect from Redis
        """
        if self.redis_client:
            await self.redis_client.close()
    
    async def get(self, key: str, default: Any = None) -> Any:
        """
        Get value from cache
        """
        if not self.redis_client:
            return default
        
        try:
            value = await self.redis_client.get(key)
            
            if value is None:
                return default
            
            # Try to deserialize
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                try:
                    return pickle.loads(value)
                except:
                    return value.decode('utf-8') if isinstance(value, bytes) else value
                    
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {str(e)}")
            return default
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set value in cache
        """
        if not self.redis_client:
            return False
        
        try:
            # Serialize value
            if isinstance(value, (str, int, float)):
                serialized = str(value)
            elif isinstance(value, (dict, list)):
                serialized = json.dumps(value)
            else:
                serialized = pickle.dumps(value)
            
            # Set with TTL
            ttl = ttl or self.default_ttl
            
            if ttl > 0:
                await self.redis_client.setex(key, ttl, serialized)
            else:
                await self.redis_client.set(key, serialized)
            
            return True
            
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {str(e)}")
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Delete key from cache
        """
        if not self.redis_client:
            return False
        
        try:
            result = await self.redis_client.delete(key)
            return result > 0
            
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {str(e)}")
            return False
    
    async def exists(self, key: str) -> bool:
        """
        Check if key exists
        """
        if not self.redis_client:
            return False
        
        try:
            return await self.redis_client.exists(key) > 0
            
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {str(e)}")
            return False
    
    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """
        Increment counter
        """
        if not self.redis_client:
            return None
        
        try:
            return await self.redis_client.incrby(key, amount)
            
        except Exception as e:
            logger.error(f"Cache increment error for key {key}: {str(e)}")
            return None
    
    async def expire(self, key: str, ttl: int) -> bool:
        """
        Set expiration for key
        """
        if not self.redis_client:
            return False
        
        try:
            return await self.redis_client.expire(key, ttl)
            
        except Exception as e:
            logger.error(f"Cache expire error for key {key}: {str(e)}")
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """
        Clear all keys matching pattern
        """
        if not self.redis_client:
            return 0
        
        try:
            keys = await self.redis_client.keys(pattern)
            
            if keys:
                return await self.redis_client.delete(*keys)
            
            return 0
            
        except Exception as e:
            logger.error(f"Cache clear pattern error for {pattern}: {str(e)}")
            return 0
    
    async def get_ttl(self, key: str) -> int:
        """
        Get TTL for key
        """
        if not self.redis_client:
            return -1
        
        try:
            return await self.redis_client.ttl(key)
            
        except Exception as e:
            logger.error(f"Cache get TTL error for key {key}: {str(e)}")
            return -1
    
    async def flush_db(self) -> bool:
        """
        Flush entire database (use with caution!)
        """
        if not self.redis_client:
            return False
        
        try:
            await self.redis_client.flushdb()
            return True
            
        except Exception as e:
            logger.error(f"Cache flush DB error: {str(e)}")
            return False


# Create global cache manager instance
cache_manager = CacheManager()


# Decorator for caching function results
def cache_result(ttl: int = None, key_prefix: str = None):
    """
    Decorator to cache function results
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Generate cache key
            key_parts = [key_prefix or func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(key_parts)
            
            # Try to get from cache
            cached = await cache_manager.get(cache_key)
            if cached is not None:
                return cached
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache result
            await cache_manager.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator


# ===========================
# backend/app/core/utils.py
# ===========================

import hashlib
import random
import string
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import re
import unicodedata
import numpy as np
from scipy import stats


def generate_slug(text: str) -> str:
    """
    Generate URL-friendly slug from text
    """
    # Normalize unicode
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')
    
    # Convert to lowercase and replace spaces
    text = re.sub(r'[^\w\s-]', '', text.lower())
    text = re.sub(r'[-\s]+', '-', text)
    
    return text.strip('-')


def generate_random_string(length: int = 10) -> str:
    """
    Generate random alphanumeric string
    """
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))


def hash_string(text: str) -> str:
    """
    Generate SHA256 hash of string
    """
    return hashlib.sha256(text.encode()).hexdigest()


def calculate_correlation(x: List[float], y: List[float]) -> float:
    """
    Calculate Pearson correlation coefficient
    """
    if len(x) != len(y) or len(x) < 2:
        return 0.0
    
    correlation, _ = stats.pearsonr(x, y)
    return float(correlation)


def detect_outliers(data: List[float], threshold: float = 3.0) -> List[int]:
    """
    Detect outliers using Z-score method
    """
    if len(data) < 3:
        return []
    
    z_scores = np.abs(stats.zscore(data))
    return [i for i, z in enumerate(z_scores) if z > threshold]


def calculate_confidence_interval(
    data: List[float],
    confidence: float = 0.95
) -> tuple[float, float]:
    """
    Calculate confidence interval
    """
    if not data:
        return (0, 0)
    
    mean = np.mean(data)
    sem = stats.sem(data)
    interval = sem * stats.t.ppf((1 + confidence) / 2, len(data) - 1)
    
    return (mean - interval, mean + interval)


def format_currency(amount: float, currency: str = "BRL") -> str:
    """
    Format amount as currency
    """
    if currency == "BRL":
        return f"R$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    elif currency == "USD":
        return f"$ {amount:,.2f}"
    else:
        return f"{amount:.2f}"


def parse_date_range(date_range: str) -> tuple[datetime, datetime]:
    """
    Parse date range string (e.g., "2024-01-01 to 2024-01-31")
    """
    parts = date_range.split(" to ")
    
    if len(parts) != 2:
        raise ValueError("Invalid date range format")
    
    start_date = datetime.fromisoformat(parts[0])
    end_date = datetime.fromisoformat(parts[1])
    
    return start_date, end_date


def safe_divide(numerator: float, denominator: float, default: float = 0) -> float:
    """
    Safe division with default value for division by zero
    """
    if denominator == 0:
        return default
    return numerator / denominator


def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """
    Split list into chunks
    """
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def flatten_dict(d: Dict, parent_key: str = '', sep: str = '_') -> Dict:
    """
    Flatten nested dictionary
    """
    items = []
    
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    
    return dict(items)


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe storage
    """
    # Remove path components
    filename = filename.replace('/', '_').replace('\\', '_')
    
    # Remove special characters
    filename = re.sub(r'[^\w\s.-]', '', filename)
    
    # Limit length
    name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
    if len(name) > 100:
        name = name[:100]
    
    return f"{name}.{ext}" if ext else name


def calculate_percentage_change(old_value: float, new_value: float) -> float:
    """
    Calculate percentage change between two values
    """
    if old_value == 0:
        return 100.0 if new_value > 0 else 0.0
    
    return ((new_value - old_value) / old_value) * 100