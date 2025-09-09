"""
Modelo de alertas para o sistema WeatherBiz Analytics.
Gerencia alertas automáticos baseados em condições climáticas e vendas.
"""

from typing import Optional, List, TYPE_CHECKING
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime,
    ForeignKey, Text, JSON, Index, Numeric,
    Enum as SQLEnum
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.config.database import Base, TimestampMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.company import Company


class AlertType(str):
    """Tipos de alerta."""
    WEATHER = "weather"  # Alerta climático
    SALES = "sales"  # Alerta de vendas
    INVENTORY = "inventory"  # Alerta de estoque
    PREDICTION = "prediction"  # Alerta de previsão
    ANOMALY = "anomaly"  # Detecção de anomalia
    CUSTOM = "custom"  # Alerta customizado


class AlertSeverity(str):
    """Severidade do alerta."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertStatus(str):
    """Status do alerta."""
    PENDING = "pending"  # Aguardando disparo
    TRIGGERED = "triggered"  # Disparado
    ACKNOWLEDGED = "acknowledged"  # Reconhecido
    RESOLVED = "resolved"  # Resolvido
    EXPIRED = "expired"  # Expirado
    FAILED = "failed"  # Falha no envio


class AlertConditionOperator(str):
    """Operadores para condições de alerta."""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    GREATER_EQUAL = "greater_equal"
    LESS_THAN = "less_than"
    LESS_EQUAL = "less_equal"
    CONTAINS = "contains"
    BETWEEN = "between"
    IN = "in"
    NOT_IN = "not_in"


class AlertRule(Base, TimestampMixin, TenantMixin):
    """
    Regras de alerta configuradas pela empresa.
    """
    
    __tablename__ = "alert_rules"
    
    # ==================== PRIMARY KEY ====================
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # ==================== RULE INFO ====================
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Nome da regra"
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Descrição da regra"
    )
    
    type: Mapped[str] = mapped_column(
        String(50),
        default=AlertType.WEATHER,
        nullable=False,
        index=True,
        doc="Tipo do alerta"
    )
    
    severity: Mapped[str] = mapped_column(
        String(20),
        default=AlertSeverity.WARNING,
        nullable=False,
        doc="Severidade do alerta"
    )
    
    # ==================== CONDITIONS ====================
    conditions: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        doc="""Condições para disparo. Exemplo:
        {
            "temperature": {"operator": "greater_than", "value": 30},
            "precipitation": {"operator": "greater_than", "value": 50}
        }"""
    )
    
    condition_logic: Mapped[str] = mapped_column(
        String(10),
        default="AND",
        nullable=False,
        doc="Lógica das condições (AND/OR)"
    )
    
    # ==================== MONITORING ====================
    monitor_field: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Campo principal a monitorar"
    )
    
    monitor_source: Mapped[str] = mapped_column(
        String(50),
        default="weather",
        nullable=False,
        doc="Fonte dos dados (weather/sales/ml)"
    )
    
    # ==================== THRESHOLDS ====================
    threshold_value: Mapped[Optional[Numeric]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        doc="Valor de threshold principal"
    )
    
    threshold_min: Mapped[Optional[Numeric]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        doc="Threshold mínimo"
    )
    
    threshold_max: Mapped[Optional[Numeric]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        doc="Threshold máximo"
    )
    
    # ==================== SCHEDULING ====================
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        doc="Se a regra está ativa"
    )
    
    check_frequency: Mapped[int] = mapped_column(
        Integer,
        default=3600,
        nullable=False,
        doc="Frequência de verificação (segundos)"
    )
    
    last_checked: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Última verificação"
    )
    
    # ==================== TIME WINDOW ====================
    time_window_minutes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Janela de tempo para análise (minutos)"
    )
    
    cooldown_minutes: Mapped[int] = mapped_column(
        Integer,
        default=60,
        nullable=False,
        doc="Tempo de espera entre alertas (minutos)"
    )
    
    # ==================== NOTIFICATION ====================
    notification_channels: Mapped[list] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        doc="Canais de notificação (email, whatsapp, etc)"
    )
    
    notification_recipients: Mapped[list] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        doc="IDs dos usuários a notificar"
    )
    
    notification_template: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Template customizado de notificação"
    )
    
    # ==================== ACTIONS ====================
    auto_resolve: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Se resolve automaticamente"
    )
    
    auto_resolve_conditions: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Condições para resolver automaticamente"
    )
    
    actions: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Ações automáticas ao disparar"
    )
    
    # ==================== STATISTICS ====================
    trigger_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Número de vezes disparado"
    )
    
    last_triggered: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Último disparo"
    )
    
    false_positive_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Número de falsos positivos"
    )
    
    # ==================== METADATA ====================
    tags: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        doc="Tags da regra"
    )
    
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Metadados adicionais"
    )
    
    # ==================== RELATIONSHIPS ====================
    company: Mapped["Company"] = relationship(
        "Company",
        back_populates="alert_rules"
    )
    
    alerts: Mapped[List["Alert"]] = relationship(
        "Alert",
        back_populates="rule",
        cascade="all, delete-orphan"
    )
    
    # ==================== INDEXES ====================
    __table_args__ = (
        Index("idx_alert_rule_company_active", "company_id", "is_active"),
        Index("idx_alert_rule_type", "type"),
        Index("idx_alert_rule_last_checked", "last_checked"),
    )
    
    # ==================== METHODS ====================
    def should_check(self) -> bool:
        """Verifica se deve checar a regra agora."""
        if not self.is_active:
            return False
        
        if not self.last_checked:
            return True
        
        elapsed = datetime.now(timezone.utc) - self.last_checked
        return elapsed.total_seconds() >= self.check_frequency
    
    def increment_trigger_count(self) -> None:
        """Incrementa contador de disparos."""
        self.trigger_count += 1
        self.last_triggered = datetime.now(timezone.utc)
    
    # ==================== STRING REPRESENTATION ====================
    def __repr__(self) -> str:
        return f"<AlertRule(id={self.id}, name={self.name}, type={self.type})>"
    
    def __str__(self) -> str:
        return f"{self.name} ({self.type})"


class Alert(Base, TimestampMixin, TenantMixin):
    """
    Alertas disparados.
    """
    
    __tablename__ = "alerts"
    
    # ==================== PRIMARY KEY ====================
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # ==================== RULE REFERENCE ====================
    rule_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("alert_rules.id"),
        nullable=True,
        index=True,
        doc="ID da regra que gerou o alerta"
    )
    
    # ==================== ALERT INFO ====================
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Título do alerta"
    )
    
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Mensagem do alerta"
    )
    
    type: Mapped[str] = mapped_column(
        String(50),
        default=AlertType.WEATHER,
        nullable=False,
        index=True,
        doc="Tipo do alerta"
    )
    
    severity: Mapped[str] = mapped_column(
        String(20),
        default=AlertSeverity.WARNING,
        nullable=False,
        index=True,
        doc="Severidade do alerta"
    )
    
    status: Mapped[str] = mapped_column(
        String(20),
        default=AlertStatus.PENDING,
        nullable=False,
        index=True,
        doc="Status do alerta"
    )
    
    # ==================== TRIGGER INFO ====================
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False,
        doc="Quando foi disparado"
    )
    
    triggered_by: Mapped[str] = mapped_column(
        String(50),
        default="system",
        nullable=False,
        doc="Quem/o que disparou (system/user/api)"
    )
    
    trigger_value: Mapped[Optional[Numeric]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        doc="Valor que disparou o alerta"
    )
    
    trigger_data: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Dados completos do disparo"
    )
    
    # ==================== ACKNOWLEDGMENT ====================
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Quando foi reconhecido"
    )
    
    acknowledged_by_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        doc="ID do usuário que reconheceu"
    )
    
    acknowledgment_note: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Nota de reconhecimento"
    )
    
    # ==================== RESOLUTION ====================
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Quando foi resolvido"
    )
    
    resolved_by_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        doc="ID do usuário que resolveu"
    )
    
    resolution_note: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Nota de resolução"
    )
    
    auto_resolved: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Se foi resolvido automaticamente"
    )
    
    # ==================== EXPIRATION ====================
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Quando o alerta expira"
    )
    
    # ==================== NOTIFICATION ====================
    notified_users: Mapped[list] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        doc="IDs dos usuários notificados"
    )
    
    notification_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Quando as notificações foram enviadas"
    )
    
    notification_channels_used: Mapped[list] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        doc="Canais usados para notificação"
    )
    
    # ==================== SOURCE ====================
    source_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        doc="Tipo da fonte (weather_data, sales_data, etc)"
    )
    
    source_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="ID da fonte"
    )
    
    # ==================== IMPACT ====================
    impact_level: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        doc="Nível de impacto (low/medium/high)"
    )
    
    affected_products: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        doc="IDs dos produtos afetados"
    )
    
    estimated_impact: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Impacto estimado (vendas, receita, etc)"
    )
    
    # ==================== ACTIONS ====================
    actions_taken: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        doc="Ações tomadas"
    )
    
    recommendations: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        doc="Recomendações de ação"
    )
    
    # ==================== USER TRACKING ====================
    created_by_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        doc="ID do usuário que criou (se manual)"
    )
    
    # ==================== METADATA ====================
    tags: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        doc="Tags do alerta"
    )
    
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Metadados adicionais"
    )
    
    # ==================== RELATIONSHIPS ====================
    company: Mapped["Company"] = relationship(
        "Company",
        back_populates="alerts"
    )
    
    rule: Mapped[Optional["AlertRule"]] = relationship(
        "AlertRule",
        back_populates="alerts"
    )
    
    acknowledged_by_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[acknowledged_by_id]
    )
    
    resolved_by_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[resolved_by_id]
    )
    
    created_by_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[created_by_id],
        back_populates="created_alerts"
    )
    
    # ==================== INDEXES ====================
    __table_args__ = (
        Index("idx_alert_company_status", "company_id", "status"),
        Index("idx_alert_company_type", "company_id", "type"),
        Index("idx_alert_triggered_at", "triggered_at"),
        Index("idx_alert_expires_at", "expires_at"),
        Index("idx_alert_rule", "rule_id"),
    )
    
    # ==================== PROPERTIES ====================
    @property
    def is_expired(self) -> bool:
        """Verifica se o alerta expirou."""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    @property
    def duration(self) -> Optional[int]:
        """Duração do alerta em minutos."""
        if not self.resolved_at:
            return None
        delta = self.resolved_at - self.triggered_at
        return int(delta.total_seconds() / 60)
    
    @property
    def response_time(self) -> Optional[int]:
        """Tempo de resposta em minutos."""
        if not self.acknowledged_at:
            return None
        delta = self.acknowledged_at - self.triggered_at
        return int(delta.total_seconds() / 60)
    
    # ==================== METHODS ====================
    def acknowledge(self, user_id: int, note: Optional[str] = None) -> None:
        """
        Reconhece o alerta.
        
        Args:
            user_id: ID do usuário
            note: Nota opcional
        """
        self.status = AlertStatus.ACKNOWLEDGED
        self.acknowledged_at = datetime.now(timezone.utc)
        self.acknowledged_by_id = user_id
        self.acknowledgment_note = note
    
    def resolve(
        self,
        user_id: Optional[int] = None,
        note: Optional[str] = None,
        auto: bool = False
    ) -> None:
        """
        Resolve o alerta.
        
        Args:
            user_id: ID do usuário (se manual)
            note: Nota de resolução
            auto: Se foi resolvido automaticamente
        """
        self.status = AlertStatus.RESOLVED
        self.resolved_at = datetime.now(timezone.utc)
        self.resolved_by_id = user_id
        self.resolution_note = note
        self.auto_resolved = auto
    
    def to_dict(self) -> dict:
        """
        Converte alerta para dicionário.
        
        Returns:
            dict: Dados do alerta
        """
        return {
            "id": self.id,
            "title": self.title,
            "message": self.message,
            "type": self.type,
            "severity": self.severity,
            "status": self.status,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "trigger_value": float(self.trigger_value) if self.trigger_value else None,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "duration": self.duration,
            "response_time": self.response_time,
            "impact_level": self.impact_level,
            "recommendations": self.recommendations,
            "is_expired": self.is_expired
        }
    
    # ==================== STRING REPRESENTATION ====================
    def __repr__(self) -> str:
        return f"<Alert(id={self.id}, type={self.type}, status={self.status})>"
    
    def __str__(self) -> str:
        return f"{self.severity.upper()}: {self.title}"


class AlertHistory(Base, TimestampMixin, TenantMixin):
    """
    Histórico de alertas para análise.
    """
    
    __tablename__ = "alert_history"
    
    # ==================== PRIMARY KEY ====================
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # ==================== ALERT REFERENCE ====================
    alert_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("alerts.id"),
        nullable=False,
        index=True,
        doc="ID do alerta original"
    )
    
    # ==================== EVENT INFO ====================
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Tipo de evento (created/acknowledged/resolved/expired)"
    )
    
    event_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False,
        doc="Quando o evento ocorreu"
    )
    
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        doc="ID do usuário envolvido"
    )
    
    # ==================== EVENT DATA ====================
    old_status: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        doc="Status anterior"
    )
    
    new_status: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        doc="Novo status"
    )
    
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Notas do evento"
    )
    
    event_data: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Dados adicionais do evento"
    )
    
    # ==================== INDEXES ====================
    __table_args__ = (
        Index("idx_alert_history_alert", "alert_id"),
        Index("idx_alert_history_timestamp", "event_timestamp"),
    )
    
    # ==================== STRING REPRESENTATION ====================
    def __repr__(self) -> str:
        return f"<AlertHistory(alert_id={self.alert_id}, event={self.event_type})>"