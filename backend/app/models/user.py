# Model User + Company relationship
"""
Modelo de usuário para o sistema Asterion.
Implementa autenticação, roles e multi-tenancy.
"""

from typing import Optional, List, TYPE_CHECKING
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, 
    ForeignKey, Text, JSON, Index, UniqueConstraint,
    Enum as SQLEnum
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql import func

from app.config.database import Base, TimestampMixin, TenantMixin, SoftDeleteMixin
from app.config.security import UserRole, get_password_hash, verify_password

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.notification import NotificationPreference, Notification
    from app.models.chat import ChatHistory
    from app.models.alert import Alert
    from app.models.export import ExportJob


class User(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """
    Modelo de usuário com suporte multi-tenant.
    """
    
    __tablename__ = "users"
    
    # ==================== PRIMARY KEY ====================
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # ==================== BASIC INFO ====================
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        doc="Email único do usuário"
    )
    
    username: Mapped[Optional[str]] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=True,
        doc="Username opcional único"
    )
    
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Nome completo do usuário"
    )
    
    phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        doc="Telefone do usuário"
    )
    
    # ==================== AUTHENTICATION ====================
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Hash bcrypt da senha"
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Se o usuário está ativo"
    )
    
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Se o email foi verificado"
    )
    
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Super admin do sistema (acesso total)"
    )
    
    # ==================== ROLE & PERMISSIONS ====================
    role: Mapped[str] = mapped_column(
        SQLEnum(UserRole, name="user_role_enum"),
        default=UserRole.USER,
        nullable=False,
        doc="Role do usuário na empresa"
    )
    
    custom_permissions: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Permissões customizadas além do role"
    )
    
    # ==================== PROFILE ====================
    avatar_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        doc="URL do avatar do usuário"
    )
    
    bio: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Biografia/descrição do usuário"
    )
    
    timezone: Mapped[str] = mapped_column(
        String(50),
        default="America/Sao_Paulo",
        nullable=False,
        doc="Timezone do usuário"
    )
    
    language: Mapped[str] = mapped_column(
        String(10),
        default="pt-BR",
        nullable=False,
        doc="Idioma preferido"
    )
    
    # ==================== SECURITY ====================
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Último login bem-sucedido"
    )
    
    last_login_ip: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        doc="IP do último login"
    )
    
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Tentativas de login falhadas"
    )
    
    locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Conta bloqueada até esta data/hora"
    )
    
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Última mudança de senha"
    )
    
    # ==================== TOKENS ====================
    refresh_token: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        doc="Refresh token atual"
    )
    
    api_key_hash: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Hash da API key do usuário"
    )
    
    reset_password_token: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Token para reset de senha"
    )
    
    reset_password_expires: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Expiração do token de reset"
    )
    
    email_verification_token: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Token para verificação de email"
    )
    
    # ==================== PREFERENCES ====================
    preferences: Mapped[Optional[dict]] = mapped_column(
        JSON,
        default=dict,
        nullable=True,
        doc="Preferências gerais do usuário"
    )
    
    dashboard_layout: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Layout customizado do dashboard"
    )
    
    # ==================== METADATA ====================
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Metadados adicionais do usuário"
    )
    
    invited_by_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        doc="ID do usuário que convidou"
    )
    
    # ==================== RELATIONSHIPS ====================
    # Company relationship
    company: Mapped["Company"] = relationship(
        "Company",
        back_populates="users",
        lazy="joined"
    )
    
    # Self-referential relationship para convites
    invited_by: Mapped[Optional["User"]] = relationship(
        "User",
        remote_side=[id],
        backref="invited_users"
    )
    
    # Notification preferences
    notification_preferences: Mapped[List["NotificationPreference"]] = relationship(
        "NotificationPreference",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    # Notifications
    notifications: Mapped[List["Notification"]] = relationship(
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    # Chat history
    chat_messages: Mapped[List["ChatHistory"]] = relationship(
        "ChatHistory",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    # Alerts created
    created_alerts: Mapped[List["Alert"]] = relationship(
        "Alert",
        back_populates="created_by_user",
        foreign_keys="Alert.created_by_id"
    )
    
    # Export jobs
    export_jobs: Mapped[List["ExportJob"]] = relationship(
        "ExportJob",
        back_populates="requested_by_user"
    )
    
    # ==================== INDEXES ====================
    __table_args__ = (
        # Índice único para email + company_id (multi-tenant)
        UniqueConstraint("email", "company_id", name="uq_user_email_company"),
        
        # Índices para queries comuns
        Index("idx_user_company_role", "company_id", "role"),
        Index("idx_user_company_active", "company_id", "is_active"),
        Index("idx_user_last_login", "last_login_at"),
        Index("idx_user_created", "created_at"),
    )
    
    # ==================== PROPERTIES ====================
    @hybrid_property
    def is_locked(self) -> bool:
        """Verifica se a conta está bloqueada."""
        if not self.locked_until:
            return False
        return datetime.now(timezone.utc) < self.locked_until
    
    @hybrid_property
    def is_admin(self) -> bool:
        """Verifica se é admin da empresa."""
        return self.role in [UserRole.COMPANY_ADMIN, UserRole.SUPER_ADMIN]
    
    @property
    def display_name(self) -> str:
        """Nome de exibição do usuário."""
        return self.full_name or self.username or self.email.split("@")[0]
    
    # ==================== METHODS ====================
    def set_password(self, password: str) -> None:
        """
        Define nova senha para o usuário.
        
        Args:
            password: Senha em texto plano
        """
        self.hashed_password = get_password_hash(password)
        self.password_changed_at = datetime.now(timezone.utc)
        self.reset_password_token = None
        self.reset_password_expires = None
    
    def verify_password(self, password: str) -> bool:
        """
        Verifica se a senha está correta.
        
        Args:
            password: Senha em texto plano
            
        Returns:
            bool: True se a senha está correta
        """
        return verify_password(password, self.hashed_password)
    
    def update_last_login(self, ip_address: Optional[str] = None) -> None:
        """
        Atualiza informações do último login.
        
        Args:
            ip_address: IP do cliente
        """
        self.last_login_at = datetime.now(timezone.utc)
        self.last_login_ip = ip_address
        self.failed_login_attempts = 0
    
    def increment_failed_login(self) -> None:
        """Incrementa contador de tentativas falhadas."""
        self.failed_login_attempts += 1
        
        # Bloqueia após 5 tentativas
        if self.failed_login_attempts >= 5:
            self.locked_until = datetime.now(timezone.utc).replace(
                minute=datetime.now(timezone.utc).minute + 30
            )
    
    def unlock_account(self) -> None:
        """Desbloqueia a conta do usuário."""
        self.locked_until = None
        self.failed_login_attempts = 0
    
    def has_permission(self, permission: str) -> bool:
        """
        Verifica se usuário tem uma permissão específica.
        
        Args:
            permission: Nome da permissão
            
        Returns:
            bool: True se tem a permissão
        """
        from app.config.security import get_permissions_for_role
        
        # Super admin tem todas as permissões
        if self.is_superuser:
            return True
        
        # Verifica permissões do role
        role_permissions = get_permissions_for_role(self.role)
        if permission in role_permissions:
            return True
        
        # Verifica permissões customizadas
        if self.custom_permissions:
            return permission in self.custom_permissions.get("permissions", [])
        
        return False
    
    def to_dict(self) -> dict:
        """
        Converte o usuário para dicionário.
        
        Returns:
            dict: Dados do usuário (sem informações sensíveis)
        """
        return {
            "id": self.id,
            "email": self.email,
            "username": self.username,
            "full_name": self.full_name,
            "phone": self.phone,
            "role": self.role,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "avatar_url": self.avatar_url,
            "timezone": self.timezone,
            "language": self.language,
            "company_id": self.company_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None
        }
    
    # ==================== STRING REPRESENTATION ====================
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, company_id={self.company_id})>"
    
    def __str__(self) -> str:
        return self.display_name