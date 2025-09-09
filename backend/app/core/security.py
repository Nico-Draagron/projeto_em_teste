# JWT, hashing, permissions
"""
Security module for WeatherBiz Analytics.
Handles JWT authentication, password hashing, and security utilities.
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import re
import logging

from .config import settings
from .exceptions import AuthenticationError, AuthorizationError

logger = logging.getLogger(__name__)

# Password context for hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login"
)

# JWT Configuration
JWT_ALGORITHM = settings.ALGORITHM
JWT_SECRET_KEY = settings.SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS

# Security headers
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'self'",
    "Referrer-Policy": "strict-origin-when-cross-origin"
}


# ==================== PASSWORD UTILITIES ====================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password.
    
    Args:
        plain_password: Plain text password
        hashed_password: Hashed password from database
        
    Returns:
        bool: True if password matches
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Password verification error: {str(e)}")
        return False


def get_password_hash(password: str) -> str:
    """
    Generate password hash.
    
    Args:
        password: Plain text password
        
    Returns:
        str: Hashed password
    """
    return pwd_context.hash(password)


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate password strength.
    
    Args:
        password: Password to validate
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        return False, f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters long"
    
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit"
    
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character"
    
    return True, ""


# ==================== JWT TOKEN UTILITIES ====================

def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create JWT access token.
    
    Args:
        data: Data to encode in token
        expires_delta: Optional expiration time
        
    Returns:
        str: Encoded JWT token
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access"
    })
    
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create JWT refresh token.
    
    Args:
        data: Data to encode in token
        expires_delta: Optional expiration time
        
    Returns:
        str: Encoded JWT refresh token
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            days=REFRESH_TOKEN_EXPIRE_DAYS
        )
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
        "jti": secrets.token_urlsafe(32)  # JWT ID for refresh token tracking
    })
    
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
    """
    Verify and decode JWT token.
    
    Args:
        token: JWT token to verify
        token_type: Expected token type (access or refresh)
        
    Returns:
        dict: Token payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM]
        )
        
        # Verify token type
        if payload.get("type") != token_type:
            logger.warning(f"Invalid token type: expected {token_type}, got {payload.get('type')}")
            return None
        
        # Check expiration
        exp = payload.get("exp")
        if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
            logger.warning("Token has expired")
            return None
        
        return payload
        
    except JWTError as e:
        logger.error(f"JWT verification error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during token verification: {str(e)}")
        return None


def get_token_payload(token: str) -> Optional[Dict[str, Any]]:
    """
    Extract payload from token without verification.
    Use only for non-security critical operations.
    
    Args:
        token: JWT token
        
    Returns:
        dict: Token payload or None
    """
    try:
        # Decode without verification
        payload = jwt.decode(
            token,
            options={"verify_signature": False}
        )
        return payload
    except Exception as e:
        logger.error(f"Error extracting token payload: {str(e)}")
        return None


# ==================== TOKEN DEPENDENCIES ====================

async def get_current_token(token: str = Depends(oauth2_scheme)) -> str:
    """
    Dependency to get current token.
    
    Args:
        token: Bearer token from request
        
    Returns:
        str: Valid token
        
    Raises:
        HTTPException: If token is invalid
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


async def get_current_user_id(token: str = Depends(get_current_token)) -> int:
    """
    Get current user ID from token.
    
    Args:
        token: JWT token
        
    Returns:
        int: User ID
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    payload = verify_token(token, token_type="access")
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return int(user_id)


async def get_current_company_id(token: str = Depends(get_current_token)) -> int:
    """
    Get current company ID from token.
    
    Args:
        token: JWT token
        
    Returns:
        int: Company ID
        
    Raises:
        HTTPException: If token is invalid or company not found
    """
    payload = verify_token(token, token_type="access")
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    company_id = payload.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No company associated with this user",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return int(company_id)


# ==================== PERMISSIONS & ROLES ====================

class RoleChecker:
    """
    Dependency class to check user roles.
    """
    
    def __init__(self, allowed_roles: list[str]):
        """
        Initialize role checker.
        
        Args:
            allowed_roles: List of allowed roles
        """
        self.allowed_roles = allowed_roles
    
    async def __call__(self, token: str = Depends(get_current_token)) -> bool:
        """
        Check if user has required role.
        
        Args:
            token: JWT token
            
        Returns:
            bool: True if user has required role
            
        Raises:
            HTTPException: If user doesn't have required role
        """
        payload = verify_token(token, token_type="access")
        
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user_role = payload.get("role")
        if user_role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        
        return True


# Pre-configured role checkers
require_admin = RoleChecker(["admin"])
require_manager = RoleChecker(["admin", "manager"])
require_user = RoleChecker(["admin", "manager", "user"])


# ==================== API KEY MANAGEMENT ====================

def generate_api_key() -> str:
    """
    Generate a secure API key.
    
    Returns:
        str: API key
    """
    return f"wbz_{secrets.token_urlsafe(32)}"


def hash_api_key(api_key: str) -> str:
    """
    Hash API key for storage.
    
    Args:
        api_key: Plain API key
        
    Returns:
        str: Hashed API key
    """
    import hashlib
    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_api_key(api_key: str, hashed_key: str) -> bool:
    """
    Verify API key against hash.
    
    Args:
        api_key: Plain API key
        hashed_key: Hashed API key
        
    Returns:
        bool: True if API key matches
    """
    return hash_api_key(api_key) == hashed_key


# ==================== SECURITY UTILITIES ====================

def generate_csrf_token() -> str:
    """
    Generate CSRF token.
    
    Returns:
        str: CSRF token
    """
    return secrets.token_urlsafe(32)


def verify_csrf_token(token: str, stored_token: str) -> bool:
    """
    Verify CSRF token.
    
    Args:
        token: Provided CSRF token
        stored_token: Stored CSRF token
        
    Returns:
        bool: True if tokens match
    """
    return secrets.compare_digest(token, stored_token)


def sanitize_input(input_string: str) -> str:
    """
    Sanitize user input to prevent injection attacks.
    
    Args:
        input_string: User input
        
    Returns:
        str: Sanitized input
    """
    # Remove potential SQL injection patterns
    dangerous_patterns = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE)\b)",
        r"(--|#|\/\*|\*\/)",
        r"(\bOR\b.*=.*)",
        r"(\bAND\b.*=.*)",
        r"(;)",
        r"(')",
        r"(\")",
    ]
    
    sanitized = input_string
    for pattern in dangerous_patterns:
        sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE)
    
    return sanitized.strip()


def is_safe_redirect_url(url: str, allowed_hosts: list[str]) -> bool:
    """
    Check if redirect URL is safe.
    
    Args:
        url: Redirect URL
        allowed_hosts: List of allowed hosts
        
    Returns:
        bool: True if URL is safe
    """
    from urllib.parse import urlparse
    
    if not url:
        return False
    
    parsed = urlparse(url)
    
    # Check if URL is relative
    if not parsed.netloc:
        return True
    
    # Check if host is allowed
    return parsed.netloc in allowed_hosts


# Export all utilities
__all__ = [
    # Password utilities
    "verify_password",
    "get_password_hash",
    "validate_password_strength",
    
    # JWT utilities
    "create_access_token",
    "create_refresh_token",
    "verify_token",
    "get_token_payload",
    
    # Dependencies
    "get_current_token",
    "get_current_user_id",
    "get_current_company_id",
    "oauth2_scheme",
    
    # Role checkers
    "RoleChecker",
    "require_admin",
    "require_manager",
    "require_user",
    
    # API key management
    "generate_api_key",
    "hash_api_key",
    "verify_api_key",
    
    # Security utilities
    "generate_csrf_token",
    "verify_csrf_token",
    "sanitize_input",
    "is_safe_redirect_url",
    
    # Constants
    "SECURITY_HEADERS",
    "JWT_ALGORITHM",
    "pwd_context"
]