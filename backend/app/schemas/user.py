# ===========================
# backend/app/schemas/user.py
# ===========================

from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

from app.schemas.base import BaseSchema, TimestampSchema


class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"


class UserBase(BaseSchema):
    """Base user schema"""
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    phone: Optional[str] = Field(None, regex=r"^\+?[1-9]\d{1,14}$")
    role: UserRole = UserRole.USER
    department: Optional[str] = None
    position: Optional[str] = None


class UserCreate(UserBase):
    """Schema para criação de usuário"""
    password: str = Field(..., min_length=8, max_length=100)
    company_id: Optional[str] = None
    
    @validator("password")
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain digit")
        return v


class UserUpdate(BaseSchema):
    """Schema para atualização de usuário"""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    phone: Optional[str] = None
    role: Optional[UserRole] = None
    department: Optional[str] = None
    position: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase, TimestampSchema):
    """Schema de resposta do usuário"""
    id: int
    company_id: str
    is_active: bool
    is_verified: bool
    last_login: Optional[datetime] = None
    avatar_url: Optional[str] = None


class UserLogin(BaseSchema):
    """Schema para login"""
    email: EmailStr
    password: str


class UserRegister(UserCreate):
    """Schema para registro"""
    company_name: Optional[str] = Field(None, description="For new company registration")
    accept_terms: bool = Field(..., description="Must accept terms")
    
    @validator("accept_terms")
    def must_accept_terms(cls, v):
        if not v:
            raise ValueError("You must accept the terms and conditions")
        return v


class PasswordReset(BaseSchema):
    """Schema para reset de senha"""
    token: str
    new_password: str = Field(..., min_length=8, max_length=100)
    confirm_password: str
    
    @validator("confirm_password")
    def passwords_match(cls, v, values):
        if "new_password" in values and v != values["new_password"]:
            raise ValueError("Passwords do not match")
        return v
