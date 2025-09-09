# Model Company (tenant)
"""
Modelo de empresa (tenant) para o sistema Asterion.
Implementa isolamento multi-tenant e planos de assinatura.
"""

from typing import Optional, List, TYPE_CHECKING
from datetime import datetime, date, timezone
from decimal import Decimal
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, 
    Text, JSON, Index, Numeric, Date,
    Enum as SQLEnum, CheckConstraint
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.ext.hybrid import hybrid_property

from app.config.database import Base, TimestampMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.notification import Notification
    from app.models.weather import WeatherStation
    from app.models.sales import SalesData, Product
    from app.models.alert import Alert, AlertRule
    from app.models.ml_model import MLModel


class CompanyPlan(str):
    """Enum para planos de assinatura."""
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class CompanyStatus(str):
    """Enum para status da empresa."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    TRIAL = "trial"
    EXPIRED = "expired"


class BusinessType(str):
    """Enum para tipos de negócio."""
    RETAIL = "retail"
    RESTAURANT = "restaurant"
    ECOMMERCE = "ecommerce"
    SERVICE = "service"
    MANUFACTURING = "manufacturing"
    AGRICULTURE = "agriculture"
    OTHER = "other"


class Company(Base, TimestampMixin, SoftDeleteMixin):
    """
    Modelo de empresa (tenant principal).
    Cada empresa tem seus próprios dados isolados.
    """
    
    __tablename__ = "companies"
    
    # ==================== PRIMARY KEY ====================
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # ==================== BASIC INFO ====================
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        doc="Nome da empresa"
    )
    
    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
        doc="Slug único para URL (ex: empresa-xyz)"
    )
    
    legal_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Razão social da empresa"
    )
    
    cnpj: Mapped[Optional[str]] = mapped_column(
        String(20),
        unique=True,
        nullable=True,
        doc="CNPJ da empresa (único)"
    )
    
    business_type: Mapped[str] = mapped_column(
        String(50),
        default=BusinessType.OTHER,
        nullable=False,
        doc="Tipo de negócio"
    )
    
    industry: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="Indústria/setor de atuação"
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Descrição da empresa"
    )
    
    # ==================== CONTACT INFO ====================
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Email principal da empresa"
    )
    
    phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        doc="Telefone principal"
    )
    
    website: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Website da empresa"
    )
    
    # ==================== ADDRESS ====================
    address_street: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Endereço - Rua"
    )
    
    address_number: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        doc="Endereço - Número"
    )
    
    address_complement: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="Endereço - Complemento"
    )
    
    address_neighborhood: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="Endereço - Bairro"
    )
    
    address_city: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="Endereço - Cidade"
    )
    
    address_state: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        doc="Endereço - Estado"
    )
    
    address_zip: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        doc="Endereço - CEP"
    )
    
    address_country: Mapped[str] = mapped_column(
        String(2),
        default="BR",
        nullable=False,
        doc="Endereço - País (ISO 2)"
    )
    
    # ==================== GEOLOCATION ====================
    latitude: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 7),
        nullable=True,
        doc="Latitude da localização principal"
    )
    
    longitude: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 7),
        nullable=True,
        doc="Longitude da localização principal"
    )
    
    # ==================== SUBSCRIPTION & BILLING ====================
    plan: Mapped[str] = mapped_column(
        String(50),
        default=CompanyPlan.FREE,
        nullable=False,
        doc="Plano de assinatura atual"
    )
    
    status: Mapped[str] = mapped_column(
        String(50),
        default=CompanyStatus.TRIAL,
        nullable=False,
        index=True,
        doc="Status da empresa"
    )
    
    trial_ends_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Data de fim do período trial"
    )
    
    subscription_starts_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Início da assinatura paga"
    )
    
    subscription_ends_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Fim da assinatura atual"
    )
    
    billing_email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Email para cobrança"
    )
    
    # ==================== USAGE LIMITS ====================
    max_users: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False,
        doc="Limite de usuários do plano"
    )
    
    max_alerts: Mapped[int] = mapped_column(
        Integer,
        default=10,
        nullable=False,
        doc="Limite de alertas do plano"
    )
    
    max_api_calls_daily: Mapped[int] = mapped_column(
        Integer,
        default=1000,
        nullable=False,
        doc="Limite diário de chamadas API"
    )
    
    data_retention_days: Mapped[int] = mapped_column(
        Integer,
        default=30,
        nullable=False,
        doc="Dias de retenção de dados"
    )
    
    # ==================== USAGE TRACKING ====================
    current_users_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Número atual de usuários"
    )
    
    current_alerts_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Número atual de alertas ativos"
    )
    
    api_calls_today: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Chamadas API feitas hoje"
    )
    
    api_calls_month: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Chamadas API no mês"
    )
    
    storage_used_mb: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=0,
        nullable=False,
        doc="Armazenamento usado em MB"
    )
    
    # ==================== BRANDING ====================
    logo_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        doc="URL do logo da empresa"
    )
    
    primary_color: Mapped[str] = mapped_column(
        String(7),
        default="#4F46E5",
        nullable=False,
        doc="Cor primária (hex)"
    )
    
    secondary_color: Mapped[str] = mapped_column(
        String(7),
        default="#10B981",
        nullable=False,
        doc="Cor secundária (hex)"
    )
    
    # ==================== SETTINGS ====================
    settings: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        doc="Configurações gerais da empresa"
    )
    
    timezone: Mapped[str] = mapped_column(
        String(50),
        default="America/Sao_Paulo",
        nullable=False,
        doc="Timezone padrão da empresa"
    )
    
    currency: Mapped[str] = mapped_column(
        String(3),
        default="BRL",
        nullable=False,
        doc="Moeda padrão (ISO)"
    )
    
    language: Mapped[str] = mapped_column(
        String(10),
        default="pt-BR",
        nullable=False,
        doc="Idioma padrão"
    )
    
    # ==================== FEATURES FLAGS ====================
    features: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        doc="Features habilitadas/desabilitadas"
    )
    
    # ==================== ML SETTINGS ====================
    ml_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Se ML está habilitado"
    )
    
    ml_auto_retrain: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Se retreino automático está ativo"
    )
    
    ml_last_training: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Último treinamento de modelo"
    )
    
    # ==================== INTEGRATIONS ====================
    integrations: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        doc="Integrações configuradas (APIs externas)"
    )
    
    # ==================== METADATA ====================
    metadata: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        doc="Metadados adicionais"
    )
    
    onboarding_completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Se completou onboarding"
    )
    
    onboarding_step: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Passo atual do onboarding"
    )
    
    # ==================== RELATIONSHIPS ====================
    # Users
    users: Mapped[List["User"]] = relationship(
        "User",
        back_populates="company",
        cascade="all, delete-orphan"
    )
    
    # Weather stations
    weather_stations: Mapped[List["WeatherStation"]] = relationship(
        "WeatherStation",
        back_populates="company",
        cascade="all, delete-orphan"
    )
    
    # Sales data
    sales_data: Mapped[List["SalesData"]] = relationship(
        "SalesData",
        back_populates="company",
        cascade="all, delete-orphan"
    )
    
    # Products
    products: Mapped[List["Product"]] = relationship(
        "Product",
        back_populates="company",
        cascade="all, delete-orphan"
    )
    
    # Alerts
    alerts: Mapped[List["Alert"]] = relationship(
        "Alert",
        back_populates="company",
        cascade="all, delete-orphan"
    )
    
    # Alert rules
    alert_rules: Mapped[List["AlertRule"]] = relationship(
        "AlertRule",
        back_populates="company",
        cascade="all, delete-orphan"
    )
    
    # ML Models
    ml_models: Mapped[List["MLModel"]] = relationship(
        "MLModel",
        back_populates="company",
        cascade="all, delete-orphan"
    )
    
    # ==================== INDEXES ====================
    __table_args__ = (
        # Constraints
        CheckConstraint("max_users >= 0", name="check_max_users_positive"),
        CheckConstraint("max_alerts >= 0", name="check_max_alerts_positive"),
        CheckConstraint("current_users_count >= 0", name="check_current_users_positive"),
        CheckConstraint("current_alerts_count >= 0", name="check_current_alerts_positive"),
        
        # Indexes
        Index("idx_company_status", "status"),
        Index("idx_company_plan", "plan"),
        Index("idx_company_created", "created_at"),
        Index("idx_company_cnpj", "cnpj"),
    )
    
    # ==================== PROPERTIES ====================
    @hybrid_property
    def is_active(self) -> bool:
        """Verifica se a empresa está ativa."""
        return self.status == CompanyStatus.ACTIVE
    
    @hybrid_property
    def is_trial(self) -> bool:
        """Verifica se está em período trial."""
        return self.status == CompanyStatus.TRIAL
    
    @hybrid_property
    def trial_days_left(self) -> Optional[int]:
        """Dias restantes do trial."""
        if not self.trial_ends_at:
            return None
        
        delta = self.trial_ends_at - datetime.now(timezone.utc)
        return max(0, delta.days)
    
    @hybrid_property
    def can_add_user(self) -> bool:
        """Verifica se pode adicionar mais usuários."""
        if self.max_users == -1:  # Ilimitado
            return True
        return self.current_users_count < self.max_users
    
    @hybrid_property
    def can_add_alert(self) -> bool:
        """Verifica se pode adicionar mais alertas."""
        if self.max_alerts == -1:  # Ilimitado
            return True
        return self.current_alerts_count < self.max_alerts
    
    @hybrid_property
    def usage_percentage(self) -> dict:
        """Calcula porcentagem de uso dos recursos."""
        return {
            "users": (self.current_users_count / self.max_users * 100) if self.max_users > 0 else 0,
            "alerts": (self.current_alerts_count / self.max_alerts * 100) if self.max_alerts > 0 else 0,
            "api_calls": (self.api_calls_today / self.max_api_calls_daily * 100) if self.max_api_calls_daily > 0 else 0
        }
    
    @property
    def full_address(self) -> str:
        """Endereço completo formatado."""
        parts = [
            self.address_street,
            self.address_number,
            self.address_complement,
            self.address_neighborhood,
            self.address_city,
            self.address_state,
            self.address_zip
        ]
        return ", ".join(filter(None, parts))
    
    # ==================== METHODS ====================
    def increment_api_calls(self) -> None:
        """Incrementa contador de chamadas API."""
        self.api_calls_today += 1
        self.api_calls_month += 1
    
    def reset_daily_counters(self) -> None:
        """Reseta contadores diários."""
        self.api_calls_today = 0
    
    def reset_monthly_counters(self) -> None:
        """Reseta contadores mensais."""
        self.api_calls_month = 0
    
    def check_limits(self) -> dict:
        """
        Verifica se algum limite foi excedido.
        
        Returns:
            dict: Status dos limites
        """
        return {
            "users_exceeded": self.current_users_count > self.max_users if self.max_users != -1 else False,
            "alerts_exceeded": self.current_alerts_count > self.max_alerts if self.max_alerts != -1 else False,
            "api_calls_exceeded": self.api_calls_today > self.max_api_calls_daily if self.max_api_calls_daily != -1 else False
        }
    
    def upgrade_plan(self, new_plan: str) -> None:
        """
        Faz upgrade do plano.
        
        Args:
            new_plan: Novo plano
        """
        from app.config.settings import settings
        
        self.plan = new_plan
        plan_limits = settings.PLAN_LIMITS.get(new_plan, {})
        
        self.max_users = plan_limits.get("max_users", 3)
        self.max_alerts = plan_limits.get("max_alerts", 10)
        self.max_api_calls_daily = plan_limits.get("max_api_calls_daily", 1000)
        self.data_retention_days = plan_limits.get("data_retention_days", 30)
        
        self.subscription_starts_at = datetime.now(timezone.utc)
        self.status = CompanyStatus.ACTIVE
    
    def to_dict(self) -> dict:
        """
        Converte empresa para dicionário.
        
        Returns:
            dict: Dados da empresa
        """
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "cnpj": self.cnpj,
            "business_type": self.business_type,
            "email": self.email,
            "phone": self.phone,
            "website": self.website,
            "plan": self.plan,
            "status": self.status,
            "logo_url": self.logo_url,
            "address": self.full_address,
            "timezone": self.timezone,
            "currency": self.currency,
            "language": self.language,
            "usage": self.usage_percentage,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    # ==================== STRING REPRESENTATION ====================
    def __repr__(self) -> str:
        return f"<Company(id={self.id}, name={self.name}, plan={self.plan})>"
    
    def __str__(self) -> str:
        return self.name