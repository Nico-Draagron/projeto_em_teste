# ===========================
# backend/app/schemas/chat.py
# ===========================

from pydantic import Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

from app.schemas.base import BaseSchema, TenantSchema


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(BaseSchema):
    """Mensagem do chat"""
    message: str = Field(..., min_length=1, max_length=4000)
    context: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None


class ChatResponse(BaseSchema):
    """Resposta do chat"""
    message: str
    role: MessageRole = MessageRole.ASSISTANT
    data: Optional[Dict[str, Any]] = None
    suggestions: Optional[List[str]] = None
    confidence: Optional[float] = Field(None, ge=0, le=1)
    sources: Optional[List[str]] = None
    session_id: str
    timestamp: datetime


class ChatHistory(BaseSchema):
    """Histórico do chat"""
    session_id: str
    messages: List[Dict[str, Any]]
    started_at: datetime
    last_message_at: datetime
    total_messages: int
    context: Dict[str, Any]


class AIInsight(BaseSchema):
    """Insight gerado por AI"""
    type: str = Field(..., regex="^(correlation|anomaly|trend|recommendation|prediction)$")
    title: str
    description: str
    confidence: float = Field(..., ge=0, le=1)
    data: Dict[str, Any]
    recommendations: List[str]
    created_at: datetime


class ConversationContext(BaseSchema):
    """Contexto da conversa"""
    user_id: int
    company_id: str
    session_id: str
    current_topic: Optional[str] = None
    entities: Dict[str, List[str]]
    preferences: Dict[str, Any]
    history_summary: Optional[str] = None