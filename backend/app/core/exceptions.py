# Exceções customizadas
"""
Exceções customizadas para o sistema Asterion.
Centraliza tratamento de erros e mensagens consistentes.
"""

from typing import Optional, Dict, Any
from fastapi import HTTPException, status
from datetime import datetime


# ==================== BASE EXCEPTIONS ====================

class WeatherBizException(Exception):
    """
    Exceção base para todas as exceções customizadas do sistema.
    """
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.timestamp = datetime.utcnow().isoformat()
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte exceção para dicionário."""
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp
        }


class APIException(HTTPException):
    """
    Exceção base para erros de API com status HTTP.
    """
    
    def __init__(
        self,
        status_code: int,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ):
        detail = {
            "error": error_code or self.__class__.__name__,
            "message": message,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        super().__init__(
            status_code=status_code,
            detail=detail,
            headers=headers
        )


# ==================== AUTHENTICATION EXCEPTIONS ====================

class AuthenticationError(APIException):
    """Erro de autenticação."""
    
    def __init__(self, message: str = "Falha na autenticação"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message=message,
            error_code="AUTHENTICATION_ERROR",
            headers={"WWW-Authenticate": "Bearer"}
        )


class InvalidCredentials(AuthenticationError):
    """Credenciais inválidas."""
    
    def __init__(self):
        super().__init__(message="Email ou senha incorretos")


class TokenExpired(AuthenticationError):
    """Token expirado."""
    
    def __init__(self):
        super().__init__(message="Token expirado. Faça login novamente")


class InvalidToken(AuthenticationError):
    """Token inválido."""
    
    def __init__(self):
        super().__init__(message="Token inválido ou malformado")


class RefreshTokenRequired(AuthenticationError):
    """Refresh token necessário."""
    
    def __init__(self):
        super().__init__(message="Refresh token necessário para esta operação")


# ==================== AUTHORIZATION EXCEPTIONS ====================

class AuthorizationError(APIException):
    """Erro de autorização."""
    
    def __init__(self, message: str = "Sem permissão para acessar este recurso"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            message=message,
            error_code="AUTHORIZATION_ERROR"
        )


class InsufficientPermissions(AuthorizationError):
    """Permissões insuficientes."""
    
    def __init__(self, required_permission: Optional[str] = None):
        message = "Permissões insuficientes para esta operação"
        if required_permission:
            message = f"Permissão necessária: {required_permission}"
        super().__init__(message=message)


class TenantAccessDenied(AuthorizationError):
    """Acesso negado a recursos de outro tenant."""
    
    def __init__(self):
        super().__init__(
            message="Acesso negado: recurso pertence a outra empresa"
        )


# ==================== VALIDATION EXCEPTIONS ====================

class ValidationError(APIException):
    """Erro de validação de dados."""
    
    def __init__(
        self,
        message: str = "Dados inválidos",
        fields: Optional[Dict[str, str]] = None
    ):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message=message,
            error_code="VALIDATION_ERROR",
            details={"fields": fields} if fields else None
        )


class DuplicateError(APIException):
    """Recurso duplicado."""
    
    def __init__(self, resource: str, field: str, value: Any):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            message=f"{resource} já existe com {field}: {value}",
            error_code="DUPLICATE_ERROR",
            details={"resource": resource, "field": field, "value": value}
        )


# ==================== RESOURCE EXCEPTIONS ====================

class NotFoundError(APIException):
    """Recurso não encontrado."""
    
    def __init__(self, resource: str, identifier: Any = None):
        message = f"{resource} não encontrado"
        if identifier:
            message = f"{resource} com ID {identifier} não encontrado"
        
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            message=message,
            error_code="NOT_FOUND",
            details={"resource": resource, "identifier": identifier}
        )


class ResourceLocked(APIException):
    """Recurso bloqueado para edição."""
    
    def __init__(self, resource: str):
        super().__init__(
            status_code=status.HTTP_423_LOCKED,
            message=f"{resource} está bloqueado para edição",
            error_code="RESOURCE_LOCKED"
        )


class ResourceDeleted(APIException):
    """Tentativa de acessar recurso deletado."""
    
    def __init__(self, resource: str):
        super().__init__(
            status_code=status.HTTP_410_GONE,
            message=f"{resource} foi deletado",
            error_code="RESOURCE_DELETED"
        )


# ==================== BUSINESS LOGIC EXCEPTIONS ====================

class BusinessLogicError(APIException):
    """Erro de lógica de negócio."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=message,
            error_code="BUSINESS_LOGIC_ERROR",
            details=details
        )


class PlanLimitExceeded(BusinessLogicError):
    """Limite do plano excedido."""
    
    def __init__(self, limit_type: str, current: int, limit: int):
        super().__init__(
            message=f"Limite do plano excedido para {limit_type}",
            details={
                "limit_type": limit_type,
                "current": current,
                "limit": limit,
                "upgrade_required": True
            }
        )


class InsufficientData(BusinessLogicError):
    """Dados insuficientes para operação."""
    
    def __init__(self, operation: str, min_required: int, current: int):
        super().__init__(
            message=f"Dados insuficientes para {operation}",
            details={
                "operation": operation,
                "minimum_required": min_required,
                "current_count": current
            }
        )


# ==================== INTEGRATION EXCEPTIONS ====================

class ExternalServiceError(APIException):
    """Erro em serviço externo."""
    
    def __init__(
        self,
        service: str,
        message: str = "Erro ao comunicar com serviço externo",
        retry_after: Optional[int] = None
    ):
        headers = {"Retry-After": str(retry_after)} if retry_after else None
        
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            message=message,
            error_code="EXTERNAL_SERVICE_ERROR",
            details={"service": service},
            headers=headers
        )


class WeatherAPIError(ExternalServiceError):
    """Erro na API de dados climáticos."""
    
    def __init__(self, message: str = "Erro ao obter dados climáticos"):
        super().__init__(service="NOMADS", message=message)


class GeminiAPIError(ExternalServiceError):
    """Erro na API do Google Gemini."""
    
    def __init__(self, message: str = "Erro ao processar com IA"):
        super().__init__(service="Gemini AI", message=message)


class EmailServiceError(ExternalServiceError):
    """Erro no serviço de email."""
    
    def __init__(self, message: str = "Erro ao enviar email"):
        super().__init__(service="Email", message=message)


class WhatsAppAPIError(ExternalServiceError):
    """Erro na API do WhatsApp."""
    
    def __init__(self, message: str = "Erro ao enviar mensagem WhatsApp"):
        super().__init__(service="WhatsApp", message=message)


# ==================== ML/AI EXCEPTIONS ====================

class MLModelError(APIException):
    """Erro relacionado a modelos de ML."""
    
    def __init__(self, message: str, model_name: Optional[str] = None):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=message,
            error_code="ML_MODEL_ERROR",
            details={"model": model_name} if model_name else None
        )


class ModelNotFound(MLModelError):
    """Modelo ML não encontrado."""
    
    def __init__(self, model_name: str, company_id: int):
        super().__init__(
            message=f"Modelo {model_name} não encontrado para empresa {company_id}",
            model_name=model_name
        )


class PredictionError(MLModelError):
    """Erro durante predição."""
    
    def __init__(self, message: str = "Erro ao gerar predição"):
        super().__init__(message=message)


class TrainingError(MLModelError):
    """Erro durante treinamento de modelo."""
    
    def __init__(self, message: str = "Erro ao treinar modelo"):
        super().__init__(message=message)


# ==================== DATABASE EXCEPTIONS ====================

class DatabaseError(APIException):
    """Erro de banco de dados."""
    
    def __init__(self, message: str = "Erro no banco de dados"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=message,
            error_code="DATABASE_ERROR"
        )


class ConnectionError(DatabaseError):
    """Erro de conexão com banco."""
    
    def __init__(self):
        super().__init__(message="Erro ao conectar com banco de dados")


class TransactionError(DatabaseError):
    """Erro em transação."""
    
    def __init__(self, message: str = "Erro durante transação"):
        super().__init__(message=message)


# ==================== RATE LIMITING EXCEPTIONS ====================

class RateLimitExceeded(APIException):
    """Rate limit excedido."""
    
    def __init__(self, retry_after: int):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            message="Muitas requisições. Tente novamente mais tarde",
            error_code="RATE_LIMIT_EXCEEDED",
            details={"retry_after_seconds": retry_after},
            headers={"Retry-After": str(retry_after)}
        )


# ==================== FILE EXCEPTIONS ====================

class FileError(APIException):
    """Erro relacionado a arquivos."""
    
    def __init__(self, message: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=message,
            error_code="FILE_ERROR"
        )


class FileTooLarge(FileError):
    """Arquivo muito grande."""
    
    def __init__(self, max_size_mb: int):
        super().__init__(
            message=f"Arquivo muito grande. Máximo permitido: {max_size_mb}MB"
        )


class InvalidFileType(FileError):
    """Tipo de arquivo inválido."""
    
    def __init__(self, allowed_types: list):
        super().__init__(
            message=f"Tipo de arquivo inválido. Permitidos: {', '.join(allowed_types)}"
        )


# ==================== EXPORT EXCEPTIONS ====================

class ExportError(APIException):
    """Erro na exportação de dados."""
    
    def __init__(self, message: str = "Erro ao exportar dados"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=message,
            error_code="EXPORT_ERROR"
        )


class ExportLimitExceeded(ExportError):
    """Limite de exportação excedido."""
    
    def __init__(self, max_rows: int):
        super().__init__(
            message=f"Limite de exportação excedido. Máximo: {max_rows} linhas"
        )


# ==================== NOTIFICATION EXCEPTIONS ====================

class NotificationError(APIException):
    """Erro ao enviar notificação."""
    
    def __init__(self, channel: str, message: str = "Erro ao enviar notificação"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=message,
            error_code="NOTIFICATION_ERROR",
            details={"channel": channel}
        )


# Export
__all__ = [
    # Base
    "WeatherBizException",
    "APIException",
    
    # Authentication
    "AuthenticationError",
    "InvalidCredentials",
    "TokenExpired",
    "InvalidToken",
    "RefreshTokenRequired",
    
    # Authorization
    "AuthorizationError",
    "InsufficientPermissions",
    "TenantAccessDenied",
    
    # Validation
    "ValidationError",
    "DuplicateError",
    
    # Resources
    "NotFoundError",
    "ResourceLocked",
    "ResourceDeleted",
    
    # Business Logic
    "BusinessLogicError",
    "PlanLimitExceeded",
    "InsufficientData",
    
    # External Services
    "ExternalServiceError",
    "WeatherAPIError",
    "GeminiAPIError",
    "EmailServiceError",
    "WhatsAppAPIError",
    
    # ML/AI
    "MLModelError",
    "ModelNotFound",
    "PredictionError",
    "TrainingError",
    
    # Database
    "DatabaseError",
    "ConnectionError",
    "TransactionError",
    
    # Rate Limiting
    "RateLimitExceeded",
    
    # Files
    "FileError",
    "FileTooLarge",
    "InvalidFileType",
    
    # Export
    "ExportError",
    "ExportLimitExceeded",
    
    # Notifications
    "NotificationError"
]