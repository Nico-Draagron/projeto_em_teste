# JWT, OAuth, configurações de autenticação
"""
Configurações de segurança, autenticação JWT e OAuth.
Implementa sistema de autenticação multi-tenant com refresh tokens.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
import secrets
import hashlib
import hmac
from enum import Enum

from app.config.settings import settings

# ==================== ENUMS ====================

class TokenType(str, Enum):
    """Tipos de tokens JWT."""
    ACCESS = "access"
    REFRESH = "refresh"
    RESET_PASSWORD = "reset_password"
    EMAIL_VERIFICATION = "email_verification"


class UserRole(str, Enum):
    """Roles de usuário no sistema."""
    SUPER_ADMIN = "super_admin"  # Admin geral do sistema
    COMPANY_ADMIN = "company_admin"  # Admin da empresa
    MANAGER = "manager"  # Gerente com permissões médias
    USER = "user"  # Usuário comum
    VIEWER = "viewer"  # Apenas visualização


class Permission(str, Enum):
    """Permissões granulares do sistema."""
    # Company
    COMPANY_READ = "company:read"
    COMPANY_WRITE = "company:write"
    COMPANY_DELETE = "company:delete"
    
    # Users
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_DELETE = "user:delete"
    
    # Sales
    SALES_READ = "sales:read"
    SALES_WRITE = "sales:write"
    SALES_DELETE = "sales:delete"
    
    # Weather
    WEATHER_READ = "weather:read"
    WEATHER_WRITE = "weather:write"
    
    # ML Models
    ML_READ = "ml:read"
    ML_WRITE = "ml:write"
    ML_TRAIN = "ml:train"
    
    # Alerts
    ALERT_READ = "alert:read"
    ALERT_WRITE = "alert:write"
    ALERT_DELETE = "alert:delete"
    
    # Reports
    REPORT_READ = "report:read"
    REPORT_GENERATE = "report:generate"
    REPORT_EXPORT = "report:export"
    
    # Chat AI
    CHAT_USE = "chat:use"
    CHAT_HISTORY = "chat:history"
    
    # Billing (futuro)
    BILLING_READ = "billing:read"
    BILLING_WRITE = "billing:write"


# ==================== PASSWORD HASHING ====================

# Contexto para hashing de senhas usando bcrypt
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12  # Número de rounds para bcrypt
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica se a senha está correta.
    
    Args:
        plain_password: Senha em texto plano
        hashed_password: Hash da senha armazenado
        
    Returns:
        bool: True se a senha está correta
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Gera hash bcrypt de uma senha.
    
    Args:
        password: Senha em texto plano
        
    Returns:
        str: Hash bcrypt da senha
    """
    return pwd_context.hash(password)


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Valida a força de uma senha.
    
    Args:
        password: Senha a validar
        
    Returns:
        tuple: (válida, mensagem de erro se inválida)
    """
    if len(password) < 8:
        return False, "Senha deve ter no mínimo 8 caracteres"
    
    if not any(c.isupper() for c in password):
        return False, "Senha deve conter pelo menos uma letra maiúscula"
    
    if not any(c.islower() for c in password):
        return False, "Senha deve conter pelo menos uma letra minúscula"
    
    if not any(c.isdigit() for c in password):
        return False, "Senha deve conter pelo menos um número"
    
    # Caracteres especiais opcionais mas recomendados
    special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    if not any(c in special_chars for c in password):
        # Apenas aviso, não bloqueia
        pass
    
    return True, "Senha válida"


# ==================== JWT TOKEN MANAGEMENT ====================

def create_token(
    data: Dict[str, Any],
    token_type: TokenType = TokenType.ACCESS,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Cria um token JWT.
    
    Args:
        data: Dados a codificar no token
        token_type: Tipo do token
        expires_delta: Tempo de expiração customizado
        
    Returns:
        str: Token JWT codificado
    """
    to_encode = data.copy()
    
    # Define expiração baseada no tipo de token
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        if token_type == TokenType.ACCESS:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )
        elif token_type == TokenType.REFRESH:
            expire = datetime.now(timezone.utc) + timedelta(
                days=settings.REFRESH_TOKEN_EXPIRE_DAYS
            )
        elif token_type == TokenType.RESET_PASSWORD:
            expire = datetime.now(timezone.utc) + timedelta(hours=1)
        elif token_type == TokenType.EMAIL_VERIFICATION:
            expire = datetime.now(timezone.utc) + timedelta(days=7)
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": token_type.value,
        "jti": secrets.token_urlsafe(16)  # JWT ID único
    })
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt


def decode_token(token: str, expected_type: Optional[TokenType] = None) -> Dict[str, Any]:
    """
    Decodifica e valida um token JWT.
    
    Args:
        token: Token JWT
        expected_type: Tipo esperado do token (validação adicional)
        
    Returns:
        dict: Payload do token
        
    Raises:
        JWTError: Se o token for inválido
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        
        # Valida tipo do token se especificado
        if expected_type and payload.get("type") != expected_type.value:
            raise JWTError(f"Token inválido: esperado tipo {expected_type.value}")
        
        return payload
        
    except JWTError:
        raise


def create_access_token(user_id: int, company_id: int, role: str) -> str:
    """
    Cria token de acesso para um usuário.
    
    Args:
        user_id: ID do usuário
        company_id: ID da empresa (tenant)
        role: Role do usuário
        
    Returns:
        str: Access token JWT
    """
    data = {
        "sub": str(user_id),  # Subject (user ID)
        "company_id": company_id,
        "role": role,
        "permissions": get_permissions_for_role(role)
    }
    
    return create_token(data, TokenType.ACCESS)


def create_refresh_token(user_id: int, company_id: int) -> str:
    """
    Cria refresh token para um usuário.
    
    Args:
        user_id: ID do usuário
        company_id: ID da empresa
        
    Returns:
        str: Refresh token JWT
    """
    data = {
        "sub": str(user_id),
        "company_id": company_id
    }
    
    return create_token(data, TokenType.REFRESH)


# ==================== ROLE-BASED ACCESS CONTROL (RBAC) ====================

# Mapeamento de roles para permissões
ROLE_PERMISSIONS: Dict[str, List[Permission]] = {
    UserRole.SUPER_ADMIN: [p for p in Permission],  # Todas as permissões
    
    UserRole.COMPANY_ADMIN: [
        Permission.COMPANY_READ, Permission.COMPANY_WRITE,
        Permission.USER_READ, Permission.USER_WRITE, Permission.USER_DELETE,
        Permission.SALES_READ, Permission.SALES_WRITE, Permission.SALES_DELETE,
        Permission.WEATHER_READ, Permission.WEATHER_WRITE,
        Permission.ML_READ, Permission.ML_WRITE, Permission.ML_TRAIN,
        Permission.ALERT_READ, Permission.ALERT_WRITE, Permission.ALERT_DELETE,
        Permission.REPORT_READ, Permission.REPORT_GENERATE, Permission.REPORT_EXPORT,
        Permission.CHAT_USE, Permission.CHAT_HISTORY,
        Permission.BILLING_READ
    ],
    
    UserRole.MANAGER: [
        Permission.COMPANY_READ,
        Permission.USER_READ, Permission.USER_WRITE,
        Permission.SALES_READ, Permission.SALES_WRITE,
        Permission.WEATHER_READ,
        Permission.ML_READ,
        Permission.ALERT_READ, Permission.ALERT_WRITE,
        Permission.REPORT_READ, Permission.REPORT_GENERATE, Permission.REPORT_EXPORT,
        Permission.CHAT_USE, Permission.CHAT_HISTORY
    ],
    
    UserRole.USER: [
        Permission.COMPANY_READ,
        Permission.USER_READ,
        Permission.SALES_READ,
        Permission.WEATHER_READ,
        Permission.ML_READ,
        Permission.ALERT_READ,
        Permission.REPORT_READ, Permission.REPORT_EXPORT,
        Permission.CHAT_USE
    ],
    
    UserRole.VIEWER: [
        Permission.COMPANY_READ,
        Permission.SALES_READ,
        Permission.WEATHER_READ,
        Permission.REPORT_READ
    ]
}


def get_permissions_for_role(role: str) -> List[str]:
    """
    Obtém lista de permissões para um role.
    
    Args:
        role: Nome do role
        
    Returns:
        list: Lista de permissões
    """
    return [p.value for p in ROLE_PERMISSIONS.get(role, [])]


def has_permission(user_permissions: List[str], required_permission: Permission) -> bool:
    """
    Verifica se usuário tem uma permissão específica.
    
    Args:
        user_permissions: Lista de permissões do usuário
        required_permission: Permissão requerida
        
    Returns:
        bool: True se tem a permissão
    """
    return required_permission.value in user_permissions


# ==================== API KEY MANAGEMENT ====================

def generate_api_key() -> str:
    """
    Gera uma API key segura.
    
    Returns:
        str: API key
    """
    return f"wbz_{secrets.token_urlsafe(32)}"


def hash_api_key(api_key: str) -> str:
    """
    Gera hash de uma API key para armazenamento.
    
    Args:
        api_key: API key em texto plano
        
    Returns:
        str: Hash da API key
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_api_key(api_key: str, hashed_key: str) -> bool:
    """
    Verifica se uma API key está correta.
    
    Args:
        api_key: API key fornecida
        hashed_key: Hash armazenado
        
    Returns:
        bool: True se a key está correta
    """
    return hmac.compare_digest(
        hash_api_key(api_key),
        hashed_key
    )


# ==================== TOKEN SCHEMAS ====================

class Token(BaseModel):
    """Schema para resposta de token."""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int  # Segundos até expirar


class TokenData(BaseModel):
    """Schema para dados decodificados do token."""
    user_id: int
    company_id: int
    role: str
    permissions: List[str]
    exp: datetime
    

class PasswordReset(BaseModel):
    """Schema para reset de senha."""
    token: str
    new_password: str
    

class PasswordChange(BaseModel):
    """Schema para mudança de senha."""
    current_password: str
    new_password: str


# ==================== SECURITY HEADERS ====================

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'self'",
    "Referrer-Policy": "strict-origin-when-cross-origin"
}


# ==================== RATE LIMITING ====================

class RateLimitConfig:
    """Configuração para rate limiting."""
    
    # Limites por endpoint
    LIMITS = {
        "default": "100/minute",
        "auth": "5/minute",
        "api": "1000/hour",
        "export": "10/hour",
        "ml_train": "1/day"
    }
    
    # IPs na whitelist (sem limite)
    WHITELIST = []
    
    # IPs na blacklist (bloqueados)
    BLACKLIST = []


# Export
__all__ = [
    # Enums
    "TokenType",
    "UserRole",
    "Permission",
    
    # Password
    "verify_password",
    "get_password_hash",
    "validate_password_strength",
    
    # JWT
    "create_token",
    "decode_token",
    "create_access_token",
    "create_refresh_token",
    
    # RBAC
    "ROLE_PERMISSIONS",
    "get_permissions_for_role",
    "has_permission",
    
    # API Keys
    "generate_api_key",
    "hash_api_key",
    "verify_api_key",
    
    # Schemas
    "Token",
    "TokenData",
    "PasswordReset",
    "PasswordChange",
    
    # Config
    "SECURITY_HEADERS",
    "RateLimitConfig"
]
