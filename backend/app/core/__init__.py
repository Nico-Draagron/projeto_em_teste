"""
Core module for WeatherBiz Analytics.
Exports principais classes, funções e configurações.
"""

# Configuration
from .config import settings, Settings

# Database
from .database import (
    get_db,
    init_db,
    SessionLocal,
    Base,
    engine,
    metadata
)

# Security
from .security import (
    create_access_token,
    create_refresh_token,
    verify_token,
    verify_password,
    get_password_hash,
    get_token_payload,
    SECURITY_HEADERS,
    JWT_ALGORITHM,
    pwd_context
)

# Cache
from .cache import (
    cache_manager,
    CacheManager,
    cache_result
)

# Exceptions
from .exceptions import (
    WeatherBizException,
    AuthenticationError,
    AuthorizationError,
    ValidationError,
    NotFoundError,
    ConflictError,
    ExternalAPIError,
    RateLimitExceeded,
    TenantAccessDenied,
    DataNotFoundError,
    AnalysisError,
    WeatherAPIError,
    APIException
)

# Middleware
from .middleware import (
    RequestIDMiddleware,
    LoggingMiddleware,
    TenantIsolationMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    ErrorHandlingMiddleware,
    CompressionMiddleware,
    PerformanceMonitoringMiddleware,
    register_middlewares,
    get_current_company_id,
    get_current_user_id,
    get_current_request_id,
    request_id_var,
    company_id_var,
    user_id_var
)

# Utils
from .utils import (
    generate_slug,
    generate_random_string,
    hash_string,
    calculate_hash,
    format_datetime,
    parse_datetime,
    get_date_range,
    paginate_query,
    calculate_percentage_change,
    normalize_data,
    detect_outliers,
    calculate_correlation,
    moving_average,
    exponential_smoothing,
    validate_email,
    validate_phone_number,
    validate_cpf_cnpj,
    sanitize_filename,
    get_file_extension,
    format_file_size,
    create_temp_file,
    cleanup_old_files,
    retry_on_failure
)

__version__ = "1.0.0"
__author__ = "WeatherBiz Analytics Team"

__all__ = [
    # Configuration
    "settings",
    "Settings",
    
    # Database
    "get_db",
    "init_db",
    "SessionLocal",
    "Base",
    "engine",
    "metadata",
    
    # Security
    "create_access_token",
    "create_refresh_token",
    "verify_token",
    "verify_password",
    "get_password_hash",
    "get_token_payload",
    "SECURITY_HEADERS",
    "JWT_ALGORITHM",
    "pwd_context",
    
    # Cache
    "cache_manager",
    "CacheManager",
    "cache_result",
    
    # Exceptions
    "WeatherBizException",
    "AuthenticationError",
    "AuthorizationError",
    "ValidationError",
    "NotFoundError",
    "ConflictError",
    "ExternalAPIError",
    "RateLimitExceeded",
    "TenantAccessDenied",
    "DataNotFoundError",
    "AnalysisError",
    "WeatherAPIError",
    "APIException",
    
    # Middleware
    "RequestIDMiddleware",
    "LoggingMiddleware",
    "TenantIsolationMiddleware",
    "RateLimitMiddleware",
    "SecurityHeadersMiddleware",
    "ErrorHandlingMiddleware",
    "CompressionMiddleware",
    "PerformanceMonitoringMiddleware",
    "register_middlewares",
    "get_current_company_id",
    "get_current_user_id",
    "get_current_request_id",
    "request_id_var",
    "company_id_var",
    "user_id_var",
    
    # Utils
    "generate_slug",
    "generate_random_string",
    "hash_string",
    "calculate_hash",
    "format_datetime",
    "parse_datetime",
    "get_date_range",
    "paginate_query",
    "calculate_percentage_change",
    "normalize_data",
    "detect_outliers",
    "calculate_correlation",
    "moving_average",
    "exponential_smoothing",
    "validate_email",
    "validate_phone_number",
    "validate_cpf_cnpj",
    "sanitize_filename",
    "get_file_extension",
    "format_file_size",
    "create_temp_file",
    "cleanup_old_files",
    "retry_on_failure",
]