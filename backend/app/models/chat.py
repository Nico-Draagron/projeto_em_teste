"""
Modelo de chat/conversação para o agente AI (Gemini).
Armazena histórico de conversas e contexto.
"""

from typing import Optional, TYPE_CHECKING
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime,
    ForeignKey, Text, JSON, Index, Float
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.config.database import Base, TimestampMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.user import User


class ChatMessageRole(str):
    """Roles das mensagens no chat."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    ERROR = "error"


class ChatMessageType(str):
    """Tipos de mensagem."""
    TEXT = "text"
    CHART = "chart"
    TABLE = "table"
    PREDICTION = "prediction"
    INSIGHT = "insight"
    RECOMMENDATION = "recommendation"
    ERROR = "error"


class ChatContext(Base, TimestampMixin, TenantMixin):
    """
    Contexto de conversação (sessão de chat).
    """
    
    __tablename__ = "chat_contexts"
    
    # ==================== PRIMARY KEY ====================
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # ==================== SESSION INFO ====================
    session_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
        doc="ID único da sessão"
    )
    
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
        doc="ID do usuário"
    )
    
    # ==================== SESSION STATUS ====================
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Se a sessão está ativa"
    )
    
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False,
        doc="Início da sessão"
    )
    
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Fim da sessão"
    )
    
    last_activity: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False,
        doc="Última atividade"
    )
    
    # ==================== CONTEXT DATA ====================
    title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Título da conversa (gerado automaticamente)"
    )
    
    summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Resumo da conversa"
    )
    
    context_data: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        doc="Dados de contexto (produtos, período, etc)"
    )
    
    # ==================== STATISTICS ====================
    message_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Número de mensagens"
    )
    
    user_message_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Mensagens do usuário"
    )
    
    assistant_message_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Mensagens do assistente"
    )
    
    total_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Total de tokens usados"
    )
    
    # ==================== AI SETTINGS ====================
    model_name: Mapped[str] = mapped_column(
        String(50),
        default="gemini-pro",
        nullable=False,
        doc="Modelo AI usado"
    )
    
    temperature: Mapped[Float] = mapped_column(
        Float,
        default=0.7,
        nullable=False,
        doc="Temperatura do modelo"
    )
    
    max_tokens: Mapped[int] = mapped_column(
        Integer,
        default=2048,
        nullable=False,
        doc="Máximo de tokens por resposta"
    )
    
    # ==================== PREFERENCES ====================
    language: Mapped[str] = mapped_column(
        String(10),
        default="pt-BR",
        nullable=False,
        doc="Idioma da conversa"
    )
    
    preferences: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Preferências do usuário para a sessão"
    )
    
    # ==================== FEEDBACK ====================
    rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Avaliação da conversa (1-5)"
    )
    
    feedback: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Feedback do usuário"
    )
    
    # ==================== METADATA ====================
    tags: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        doc="Tags da conversa"
    )
    
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Metadados adicionais"
    )
    
    # ==================== RELATIONSHIPS ====================
    messages: Mapped[list["ChatHistory"]] = relationship(
        "ChatHistory",
        back_populates="context",
        cascade="all, delete-orphan",
        order_by="ChatHistory.created_at"
    )
    
    # ==================== INDEXES ====================
    __table_args__ = (
        Index("idx_chat_context_user", "user_id"),
        Index("idx_chat_context_company_user", "company_id", "user_id"),
        Index("idx_chat_context_active", "is_active"),
        Index("idx_chat_context_last_activity", "last_activity"),
    )
    
    # ==================== METHODS ====================
    def end_session(self) -> None:
        """Encerra a sessão de chat."""
        self.is_active = False
        self.ended_at = datetime.now(timezone.utc)
    
    def update_activity(self) -> None:
        """Atualiza última atividade."""
        self.last_activity = datetime.now(timezone.utc)
    
    def increment_message_count(self, role: str) -> None:
        """
        Incrementa contador de mensagens.
        
        Args:
            role: Role da mensagem
        """
        self.message_count += 1
        if role == ChatMessageRole.USER:
            self.user_message_count += 1
        elif role == ChatMessageRole.ASSISTANT:
            self.assistant_message_count += 1
    
    # ==================== STRING REPRESENTATION ====================
    def __repr__(self) -> str:
        return f"<ChatContext(id={self.id}, session_id={self.session_id})>"
    
    def __str__(self) -> str:
        return self.title or f"Chat Session {self.session_id[:8]}"


class ChatHistory(Base, TimestampMixin, TenantMixin):
    """
    Histórico de mensagens do chat.
    """
    
    __tablename__ = "chat_history"
    
    # ==================== PRIMARY KEY ====================
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # ==================== CONTEXT REFERENCE ====================
    context_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("chat_contexts.id"),
        nullable=False,
        index=True,
        doc="ID do contexto/sessão"
    )
    
    # ==================== USER REFERENCE ====================
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
        doc="ID do usuário"
    )
    
    # ==================== MESSAGE INFO ====================
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Role da mensagem (user/assistant/system)"
    )
    
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Conteúdo da mensagem"
    )
    
    message_type: Mapped[str] = mapped_column(
        String(50),
        default=ChatMessageType.TEXT,
        nullable=False,
        doc="Tipo da mensagem"
    )
    
    # ==================== RESPONSE DATA ====================
    response_data: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="""Dados estruturados da resposta. Exemplos:
        - chart: {type, data, config}
        - table: {headers, rows}
        - prediction: {value, confidence, period}
        """
    )
    
    # ==================== INTENT & ENTITIES ====================
    intent: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="Intenção detectada (question/analysis/prediction/etc)"
    )
    
    entities: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Entidades extraídas (produtos, datas, métricas)"
    )
    
    # ==================== CONTEXT USED ====================
    context_used: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Contexto usado para gerar resposta"
    )
    
    data_sources: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        doc="Fontes de dados consultadas"
    )
    
    # ==================== AI METRICS ====================
    tokens_used: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Tokens usados na mensagem"
    )
    
    processing_time_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Tempo de processamento (ms)"
    )
    
    confidence_score: Mapped[Optional[Float]] = mapped_column(
        Float,
        nullable=True,
        doc="Score de confiança da resposta"
    )
    
    # ==================== ERROR HANDLING ====================
    is_error: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Se é mensagem de erro"
    )
    
    error_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        doc="Código do erro"
    )
    
    error_details: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Detalhes do erro"
    )
    
    # ==================== FEEDBACK ====================
    helpful: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
        doc="Se foi útil (feedback do usuário)"
    )
    
    feedback: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Feedback específico da mensagem"
    )
    
    # ==================== ACTIONS ====================
    actions_suggested: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        doc="Ações sugeridas ao usuário"
    )
    
    actions_taken: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        doc="Ações tomadas pelo usuário"
    )
    
    # ==================== METADATA ====================
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Metadados adicionais"
    )
    
    # ==================== RELATIONSHIPS ====================
    user: Mapped["User"] = relationship(
        "User",
        back_populates="chat_messages"
    )
    
    context: Mapped["ChatContext"] = relationship(
        "ChatContext",
        back_populates="messages"
    )
    
    # ==================== INDEXES ====================
    __table_args__ = (
        Index("idx_chat_history_context", "context_id"),
        Index("idx_chat_history_user", "user_id"),
        Index("idx_chat_history_company_user", "company_id", "user_id"),
        Index("idx_chat_history_created", "created_at"),
        Index("idx_chat_history_role", "role"),
    )
    
    # ==================== METHODS ====================
    def mark_as_helpful(self, helpful: bool, feedback: Optional[str] = None) -> None:
        """
        Marca mensagem como útil ou não.
        
        Args:
            helpful: Se foi útil
            feedback: Feedback opcional
        """
        self.helpful = helpful
        if feedback:
            self.feedback = feedback
    
    def to_dict(self) -> dict:
        """
        Converte mensagem para dicionário.
        
        Returns:
            dict: Dados da mensagem
        """
        return {
            "id": self.id,
            "role": self.role,
            "message": self.message,
            "message_type": self.message_type,
            "response_data": self.response_data,
            "intent": self.intent,
            "entities": self.entities,
            "confidence_score": self.confidence_score,
            "is_error": self.is_error,
            "helpful": self.helpful,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    # ==================== STRING REPRESENTATION ====================
    def __repr__(self) -> str:
        return f"<ChatHistory(id={self.id}, role={self.role})>"
    
    def __str__(self) -> str:
        return f"{self.role}: {self.message[:50]}..."