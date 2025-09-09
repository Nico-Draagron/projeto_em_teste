# ===========================
# backend/app/schemas/base.py
# ===========================

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class BaseSchema(BaseModel):
    """Base schema com configurações padrão"""
    
    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        use_enum_values=True,
        validate_assignment=True,
        arbitrary_types_allowed=True
    )


class TimestampSchema(BaseSchema):
    """Schema com timestamps"""
    created_at: datetime
    updated_at: Optional[datetime] = None


class TenantSchema(BaseSchema):
    """Schema com multi-tenant"""
    company_id: str = Field(..., description="Company UUID")


class PaginationParams(BaseModel):
    """Parâmetros de paginação"""
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")
    sort_by: Optional[str] = Field(None, description="Sort field")
    sort_order: Optional[str] = Field("asc", regex="^(asc|desc)$")


class PaginatedResponse(BaseModel):
    """Resposta paginada"""
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int