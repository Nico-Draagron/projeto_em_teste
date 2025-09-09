# Model para notificações internas
"""
Modelo de notificações para o sistema Asterion.
Gerencia notificações internas e preferências de comunicação.
"""

from typing import Optional, TYPE_CHECKING
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, 
    ForeignKey, Text, JSON, Index,
    Enum as SQLEnum
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.config.database import Base, TimestampMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.company import Company


class NotificationType(str):
    """Tipos de notificação."""
    SYSTEM = "system"  # Notificações do sistema
    ALERT = "alert"  # Alertas climáticos
    INSIGHT = "insight"  # Insights da IA
    REPORT = "report"  # Relatórios prontos
    USER = "user"  # Ações de usuários
    BILLING = "billing"  # Cobrança e assinatura
    WARNING = "warning"  # Avisos importantes
    INFO = "info"  # Informações gerais


class NotificationPriority(str):
    """Prioridade da notificação."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationChannel(str):
    """Canais de notificação."""
    INTERNAL = "internal"  # Apenas no sistema
    EMAIL = "email"  # Email
    WHATSAPP = "whatsapp"  # WhatsApp
    SMS = "sms"  # SMS (futuro)
    PUSH = "push"  # Push browser (futuro)


class NotificationStatus(str):
    """Status da notificação."""
    PENDING = "pending"  # Aguardando envio
    SENT = "sent"  # Enviada
    DELIVERED = "delivered"  # Entregue
    READ = "read"  # Lida
    FAILED = "failed"  # Falha no envio
    CANCELLED = "cancelled"  # Cancelada


class Notification(Base, TimestampMixin, TenantMixin):
    """
    Modelo de notificações do sistema.
    """
    
    __tablename__ = "notifications"
    
    # ==================== PRIMARY KEY ====================
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # ==================== NOTIFICATION INFO ====================
    type: Mapped[str] = mapped_column(
        String(50),
        default=NotificationType.INFO,
        nullable=False,
        index=True,
        doc="Tipo da notificação"
    )
    
    priority: Mapped[str] = mapped_column(
        String(20),
        default=NotificationPriority.MEDIUM,
        nullable=False,
        index=True,
        doc="Prioridade da notificação"
    )
    
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Título da notificação"
    )
    
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Mensagem da notificação"
    )
    
    # ==================== RECIPIENT ====================
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
        doc="ID do usuário destinatário"
    )
    
    # ==================== STATUS ====================
    status: Mapped[str] = mapped_column(
        String(20),
        default=NotificationStatus.PENDING,
        nullable=False,
        index=True,
        doc="Status da notificação"
    )
    
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        doc="Se foi lida"
    )
    
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Quando foi lida"
    )
    
    # ==================== CHANNELS ====================
    channels: Mapped[list] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        doc="Canais onde foi/será enviada"
    )
    
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Quando foi enviada"
    )
    
    delivered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Quando foi entregue"
    )
    
    # ==================== CONTENT ====================
    data: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Dados adicionais da notificação"
    )
    
    action_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        doc="URL de ação (botão/link)"
    )
    
    action_text: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="Texto do botão de ação"
    )
    
    icon: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="Ícone da notificação"
    )
    
    image_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        doc="URL de imagem (opcional)"
    )
    
    # ==================== SOURCE ====================
    source_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        doc="Tipo da fonte (alert, report, etc)"
    )
    
    source_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="ID da fonte"
    )
    
    # ==================== DELIVERY ====================
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Número de tentativas de envio"
    )
    
    last_retry_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Última tentativa de envio"
    )
    
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Mensagem de erro se falhou"
    )
    
    # ==================== SCHEDULING ====================
    scheduled_for: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        doc="Agendada para envio futuro"
    )
    
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Quando a notificação expira"
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
        back_populates="notifications"
    )
    
    # ==================== INDEXES ====================
    __table_args__ = (
        # Índices para queries comuns
        Index("idx_notification_user_unread", "user_id", "is_read"),
        Index("idx_notification_user_type", "user_id", "type"),
        Index("idx_notification_company_type", "company_id", "type"),
        Index("idx_notification_scheduled", "scheduled_for"),
        Index("idx_notification_created", "created_at"),
    )
    
    # ==================== METHODS ====================
    def mark_as_read(self) -> None:
        """Marca notificação como lida."""
        self.is_read = True
        self.read_at = datetime.now(timezone.utc)
        self.status = NotificationStatus.READ
    
    def mark_as_sent(self) -> None:
        """Marca notificação como enviada."""
        self.status = NotificationStatus.SENT
        self.sent_at = datetime.now(timezone.utc)
    
    def mark_as_delivered(self) -> None:
        """Marca notificação como entregue."""
        self.status = NotificationStatus.DELIVERED
        self.delivered_at = datetime.now(timezone.utc)
    
    def mark_as_failed(self, error: str) -> None:
        """
        Marca notificação como falhada.
        
        Args:
            error: Mensagem de erro
        """
        self.status = NotificationStatus.FAILED
        self.error_message = error
        self.retry_count += 1
        self.last_retry_at = datetime.now(timezone.utc)
    
    def is_expired(self) -> bool:
        """Verifica se a notificação expirou."""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    def to_dict(self) -> dict:
        """
        Converte notificação para dicionário.
        
        Returns:
            dict: Dados da notificação
        """
        return {
            "id": self.id,
            "type": self.type,
            "priority": self.priority,
            "title": self.title,
            "message": self.message,
            "status": self.status,
            "is_read": self.is_read,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "action_url": self.action_url,
            "action_text": self.action_text,
            "icon": self.icon,
            "image_url": self.image_url,
            "data": self.data,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    # ==================== STRING REPRESENTATION ====================
    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, type={self.type}, user_id={self.user_id})>"
    
    def __str__(self) -> str:
        return f"{self.type}: {self.title}"


class NotificationPreference(Base, TimestampMixin, TenantMixin):
    """
    Preferências de notificação por usuário.
    """
    
    __tablename__ = "notification_preferences"
    
    # ==================== PRIMARY KEY ====================
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # ==================== USER ====================
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
        doc="ID do usuário"
    )
    
    # ==================== CHANNEL PREFERENCES ====================
    email_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Receber por email"
    )
    
    whatsapp_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Receber por WhatsApp"
    )
    
    sms_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Receber por SMS"
    )
    
    push_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Receber push notifications"
    )
    
    # ==================== TYPE PREFERENCES ====================
    system_notifications: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Notificações do sistema"
    )
    
    alert_notifications: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Alertas climáticos"
    )
    
    insight_notifications: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Insights da IA"
    )
    
    report_notifications: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Relatórios prontos"
    )
    
    user_notifications: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Ações de usuários"
    )
    
    billing_notifications: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Notificações de cobrança"
    )
    
    # ==================== FREQUENCY ====================
    daily_digest: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Receber resumo diário"
    )
    
    weekly_digest: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Receber resumo semanal"
    )
    
    digest_time: Mapped[str] = mapped_column(
        String(5),
        default="09:00",
        nullable=False,
        doc="Horário do digest (HH:MM)"
    )
    
    # ==================== PRIORITY FILTERS ====================
    min_priority: Mapped[str] = mapped_column(
        String(20),
        default=NotificationPriority.LOW,
        nullable=False,
        doc="Prioridade mínima para notificar"
    )
    
    critical_only_quiet_hours: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Apenas críticas em horário silencioso"
    )
    
    # ==================== QUIET HOURS ====================
    quiet_hours_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Horário silencioso ativo"
    )
    
    quiet_hours_start: Mapped[str] = mapped_column(
        String(5),
        default="22:00",
        nullable=False,
        doc="Início do horário silencioso (HH:MM)"
    )
    
    quiet_hours_end: Mapped[str] = mapped_column(
        String(5),
        default="08:00",
        nullable=False,
        doc="Fim do horário silencioso (HH:MM)"
    )
    
    # ==================== CONTACT INFO ====================
    email_address: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Email alternativo para notificações"
    )
    
    whatsapp_number: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        doc="Número WhatsApp"
    )
    
    sms_number: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        doc="Número SMS"
    )
    
    # ==================== CUSTOM RULES ====================
    custom_rules: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Regras customizadas de notificação"
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
        back_populates="notification_preferences"
    )
    
    # ==================== INDEXES ====================
    __table_args__ = (
        # Índice único para user_id + company_id
        Index("idx_notification_pref_user_company", "user_id", "company_id", unique=True),
    )
    
    # ==================== METHODS ====================
    def should_send_notification(
        self,
        notification_type: str,
        priority: str,
        current_time: Optional[datetime] = None
    ) -> bool:
        """
        Verifica se deve enviar notificação baseado nas preferências.
        
        Args:
            notification_type: Tipo da notificação
            priority: Prioridade da notificação
            current_time: Hora atual (para verificar quiet hours)
            
        Returns:
            bool: True se deve enviar
        """
        # Verifica se o tipo está habilitado
        type_enabled = {
            NotificationType.SYSTEM: self.system_notifications,
            NotificationType.ALERT: self.alert_notifications,
            NotificationType.INSIGHT: self.insight_notifications,
            NotificationType.REPORT: self.report_notifications,
            NotificationType.USER: self.user_notifications,
            NotificationType.BILLING: self.billing_notifications,
        }.get(notification_type, True)
        
        if not type_enabled:
            return False
        
        # Verifica prioridade mínima
        priority_levels = {
            NotificationPriority.LOW: 0,
            NotificationPriority.MEDIUM: 1,
            NotificationPriority.HIGH: 2,
            NotificationPriority.CRITICAL: 3
        }
        
        if priority_levels.get(priority, 0) < priority_levels.get(self.min_priority, 0):
            return False
        
        # Verifica quiet hours
        if self.quiet_hours_enabled and current_time:
            # TODO: Implementar lógica de quiet hours
            pass
        
        return True
    
    def get_enabled_channels(self) -> list:
        """
        Retorna lista de canais habilitados.
        
        Returns:
            list: Canais habilitados
        """
        channels = []
        
        if self.email_enabled:
            channels.append(NotificationChannel.EMAIL)
        if self.whatsapp_enabled:
            channels.append(NotificationChannel.WHATSAPP)
        if self.sms_enabled:
            channels.append(NotificationChannel.SMS)
        if self.push_enabled:
            channels.append(NotificationChannel.PUSH)
        
        # Sempre inclui interno
        channels.append(NotificationChannel.INTERNAL)
        
        return channels
    
    def to_dict(self) -> dict:
        """
        Converte preferências para dicionário.
        
        Returns:
            dict: Dados das preferências
        """
        return {
            "email_enabled": self.email_enabled,
            "whatsapp_enabled": self.whatsapp_enabled,
            "sms_enabled": self.sms_enabled,
            "push_enabled": self.push_enabled,
            "system_notifications": self.system_notifications,
            "alert_notifications": self.alert_notifications,
            "insight_notifications": self.insight_notifications,
            "report_notifications": self.report_notifications,
            "user_notifications": self.user_notifications,
            "billing_notifications": self.billing_notifications,
            "daily_digest": self.daily_digest,
            "weekly_digest": self.weekly_digest,
            "digest_time": self.digest_time,
            "min_priority": self.min_priority,
            "quiet_hours_enabled": self.quiet_hours_enabled,
            "quiet_hours_start": self.quiet_hours_start,
            "quiet_hours_end": self.quiet_hours_end
        }
    
    # ==================== STRING REPRESENTATION ====================
    def __repr__(self) -> str:
        return f"<NotificationPreference(user_id={self.user_id})>"