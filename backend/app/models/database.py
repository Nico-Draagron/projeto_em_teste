"""
Database models for WeatherBiz Analytics.
Implements multi-tenant architecture with SQLAlchemy.
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Date, Boolean, Text,
    ForeignKey, UniqueConstraint, Index, JSON, Enum, DECIMAL, 
    CheckConstraint, Table
)
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql import func
import enum

from app.core.database import Base


# ==================== ENUMS ====================

class UserRole(str, enum.Enum):
    """User roles in the system"""
    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"
    VIEWER = "viewer"


class AlertType(str, enum.Enum):
    """Types of alerts"""
    WEATHER = "weather"
    SALES = "sales"
    SYSTEM = "system"
    CUSTOM = "custom"


class AlertSeverity(str, enum.Enum):
    """Alert severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationChannel(str, enum.Enum):
    """Notification delivery channels"""
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    IN_APP = "in_app"
    PUSH = "push"


class SubscriptionPlan(str, enum.Enum):
    """Company subscription plans"""
    TRIAL = "trial"
    BASIC = "basic"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


# ==================== MIXINS ====================

class TimestampMixin:
    """Mixin for created_at and updated_at timestamps"""
    
    @declared_attr
    def created_at(cls):
        return Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    @declared_attr
    def updated_at(cls):
        return Column(DateTime(timezone=True), onupdate=func.now())


class TenantMixin:
    """Mixin for multi-tenant support"""
    
    @declared_attr
    def company_id(cls):
        return Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)


class SoftDeleteMixin:
    """Mixin for soft delete functionality"""
    
    @declared_attr
    def deleted_at(cls):
        return Column(DateTime(timezone=True), nullable=True)
    
    @declared_attr
    def is_deleted(cls):
        return Column(Boolean, default=False, nullable=False)
    
    def soft_delete(self):
        """Soft delete the record"""
        self.deleted_at = datetime.now()
        self.is_deleted = True


# ==================== ASSOCIATION TABLES ====================

# User permissions association table
user_permissions = Table(
    'user_permissions',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE')),
    Column('permission_id', Integer, ForeignKey('permissions.id', ondelete='CASCADE')),
    UniqueConstraint('user_id', 'permission_id', name='unique_user_permission')
)

# Alert recipients association table
alert_recipients = Table(
    'alert_recipients',
    Base.metadata,
    Column('alert_id', Integer, ForeignKey('alerts.id', ondelete='CASCADE')),
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE')),
    UniqueConstraint('alert_id', 'user_id', name='unique_alert_recipient')
)


# ==================== MAIN MODELS ====================

class Company(Base, TimestampMixin, SoftDeleteMixin):
    """Company model (main tenant)"""
    
    __tablename__ = "companies"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=False)
    phone = Column(String(50))
    website = Column(String(255))
    
    # Subscription
    plan = Column(Enum(SubscriptionPlan), default=SubscriptionPlan.TRIAL)
    plan_expires_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    
    # Settings (JSON field for flexible configuration)
    settings = Column(JSON, default={})
    
    # Address
    address = Column(Text)
    city = Column(String(100))
    state = Column(String(100))
    country = Column(String(100))
    postal_code = Column(String(20))
    latitude = Column(Float)
    longitude = Column(Float)
    
    # Branding
    logo_url = Column(String(500))
    primary_color = Column(String(7))  # HEX color
    secondary_color = Column(String(7))
    
    # Limits based on plan
    max_users = Column(Integer, default=5)
    max_locations = Column(Integer, default=1)
    max_alerts = Column(Integer, default=10)
    storage_limit_gb = Column(Float, default=1.0)
    
    # Relationships
    users = relationship("User", back_populates="company", cascade="all, delete-orphan")
    locations = relationship("Location", back_populates="company", cascade="all, delete-orphan")
    weather_data = relationship("WeatherData", back_populates="company", cascade="all, delete-orphan")
    sales_data = relationship("SalesData", back_populates="company", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="company", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('ix_companies_plan_active', 'plan', 'is_active'),
    )
    
    def __repr__(self):
        return f"<Company {self.name}>"


class User(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """User model with multi-tenant support"""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False)
    username = Column(String(100), nullable=False)
    full_name = Column(String(255))
    hashed_password = Column(String(255), nullable=False)
    
    # Role and permissions
    role = Column(Enum(UserRole), default=UserRole.USER)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    # Contact
    phone = Column(String(50))
    department = Column(String(100))
    job_title = Column(String(100))
    
    # Authentication
    last_login = Column(DateTime(timezone=True))
    password_changed_at = Column(DateTime(timezone=True))
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime(timezone=True))
    
    # Tokens
    email_verification_token = Column(String(255))
    password_reset_token = Column(String(255))
    password_reset_expires = Column(DateTime(timezone=True))
    
    # Preferences (JSON)
    preferences = Column(JSON, default={})
    notification_settings = Column(JSON, default={
        "email": True,
        "sms": False,
        "whatsapp": False,
        "in_app": True
    })
    
    # Profile
    avatar_url = Column(String(500))
    timezone = Column(String(50), default="UTC")
    language = Column(String(10), default="en")
    
    # Relationships
    company = relationship("Company", back_populates="users")
    permissions = relationship("Permission", secondary=user_permissions, back_populates="users")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    
    # Unique constraint
    __table_args__ = (
        UniqueConstraint('email', 'company_id', name='unique_email_per_company'),
        UniqueConstraint('username', 'company_id', name='unique_username_per_company'),
        Index('ix_users_company_role', 'company_id', 'role'),
        Index('ix_users_email', 'email'),
    )
    
    @hybrid_property
    def is_admin(self):
        return self.role == UserRole.ADMIN
    
    @hybrid_property
    def is_manager(self):
        return self.role in [UserRole.ADMIN, UserRole.MANAGER]
    
    def __repr__(self):
        return f"<User {self.email}>"


class Permission(Base, TimestampMixin):
    """Permission model for fine-grained access control"""
    
    __tablename__ = "permissions"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    resource = Column(String(100))  # e.g., "sales", "weather", "users"
    action = Column(String(50))  # e.g., "read", "write", "delete"
    
    # Relationships
    users = relationship("User", secondary=user_permissions, back_populates="permissions")
    
    __table_args__ = (
        UniqueConstraint('resource', 'action', name='unique_resource_action'),
    )
    
    def __repr__(self):
        return f"<Permission {self.name}>"


class Location(Base, TimestampMixin, TenantMixin):
    """Company locations for weather and sales data"""
    
    __tablename__ = "locations"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    code = Column(String(50))  # Internal code
    
    # Address
    address = Column(Text)
    city = Column(String(100), nullable=False)
    state = Column(String(100))
    country = Column(String(100), nullable=False)
    postal_code = Column(String(20))
    
    # Coordinates
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    
    # Weather station info
    weather_station_id = Column(String(100))
    timezone = Column(String(50), default="UTC")
    
    # Store info
    store_type = Column(String(100))
    size_sqm = Column(Float)
    opened_date = Column(Date)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    company = relationship("Company", back_populates="locations")
    weather_data = relationship("WeatherData", back_populates="location", cascade="all, delete-orphan")
    sales_data = relationship("SalesData", back_populates="location", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('code', 'company_id', name='unique_location_code_per_company'),
        Index('ix_locations_company_active', 'company_id', 'is_active'),
        Index('ix_locations_coordinates', 'latitude', 'longitude'),
    )
    
    def __repr__(self):
        return f"<Location {self.name}>"


class WeatherData(Base, TimestampMixin, TenantMixin):
    """Weather data for analysis"""
    
    __tablename__ = "weather_data"
    
    id = Column(Integer, primary_key=True, index=True)
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    hour = Column(Integer)  # 0-23 for hourly data, NULL for daily
    
    # Temperature
    temperature_avg = Column(Float)
    temperature_min = Column(Float)
    temperature_max = Column(Float)
    feels_like = Column(Float)
    
    # Precipitation
    precipitation = Column(Float)  # mm
    rain = Column(Float)  # mm
    snow = Column(Float)  # mm
    
    # Wind
    wind_speed = Column(Float)  # km/h
    wind_direction = Column(Integer)  # degrees
    wind_gust = Column(Float)
    
    # Other conditions
    humidity = Column(Float)  # percentage
    pressure = Column(Float)  # hPa
    visibility = Column(Float)  # km
    uv_index = Column(Float)
    cloud_cover = Column(Float)  # percentage
    
    # Weather condition
    condition = Column(String(100))  # e.g., "Clear", "Rainy", "Cloudy"
    condition_code = Column(String(20))
    
    # Source
    source = Column(String(50))  # e.g., "NOMADS", "OpenWeather"
    is_forecast = Column(Boolean, default=False)
    
    # Relationships
    company = relationship("Company", back_populates="weather_data")
    location = relationship("Location", back_populates="weather_data")
    
    __table_args__ = (
        UniqueConstraint('location_id', 'date', 'hour', name='unique_weather_per_location_time'),
        Index('ix_weather_location_date', 'location_id', 'date'),
        Index('ix_weather_company_date', 'company_id', 'date'),
    )
    
    def __repr__(self):
        return f"<WeatherData {self.date} @ Location {self.location_id}>"


class Product(Base, TimestampMixin, TenantMixin):
    """Products for sales tracking"""
    
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    sku = Column(String(100))
    category = Column(String(100))
    subcategory = Column(String(100))
    
    # Pricing
    price = Column(DECIMAL(10, 2))
    cost = Column(DECIMAL(10, 2))
    
    # Weather sensitivity
    weather_sensitive = Column(Boolean, default=False)
    optimal_temp_min = Column(Float)
    optimal_temp_max = Column(Float)
    rain_impact = Column(Float)  # Impact factor (-1 to 1)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Relationships
    sales_data = relationship("SalesData", back_populates="product", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('sku', 'company_id', name='unique_sku_per_company'),
        Index('ix_products_company_category', 'company_id', 'category'),
    )
    
    def __repr__(self):
        return f"<Product {self.name}>"


class SalesData(Base, TimestampMixin, TenantMixin):
    """Sales data for analysis"""
    
    __tablename__ = "sales_data"
    
    id = Column(Integer, primary_key=True, index=True)
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"))
    date = Column(Date, nullable=False)
    hour = Column(Integer)  # For hourly data
    
    # Sales metrics
    quantity = Column(Integer, nullable=False)
    revenue = Column(DECIMAL(12, 2), nullable=False)
    cost = Column(DECIMAL(12, 2))
    profit = Column(DECIMAL(12, 2))
    
    # Additional metrics
    transactions = Column(Integer)
    average_ticket = Column(DECIMAL(10, 2))
    discount_amount = Column(DECIMAL(10, 2))
    
    # Customer metrics
    customers = Column(Integer)
    new_customers = Column(Integer)
    
    # External factors
    is_holiday = Column(Boolean, default=False)
    is_weekend = Column(Boolean, default=False)
    event_name = Column(String(255))
    
    # Relationships
    company = relationship("Company", back_populates="sales_data")
    location = relationship("Location", back_populates="sales_data")
    product = relationship("Product", back_populates="sales_data")
    
    __table_args__ = (
        UniqueConstraint('location_id', 'product_id', 'date', 'hour', 
                        name='unique_sales_per_location_product_time'),
        Index('ix_sales_location_date', 'location_id', 'date'),
        Index('ix_sales_company_date', 'company_id', 'date'),
        Index('ix_sales_product_date', 'product_id', 'date'),
    )
    
    def __repr__(self):
        return f"<SalesData {self.date} @ Location {self.location_id}>"


class Alert(Base, TimestampMixin, TenantMixin):
    """Alert configurations"""
    
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Alert configuration
    alert_type = Column(Enum(AlertType), nullable=False)
    severity = Column(Enum(AlertSeverity), default=AlertSeverity.MEDIUM)
    is_active = Column(Boolean, default=True)
    
    # Conditions (JSON)
    conditions = Column(JSON, nullable=False)
    # Example: {
    #   "metric": "temperature",
    #   "operator": "greater_than",
    #   "value": 35,
    #   "duration_minutes": 60
    # }
    
    # Notification settings
    channels = Column(JSON, default=["in_app"])
    email_template = Column(Text)
    sms_template = Column(Text)
    whatsapp_template = Column(Text)
    
    # Schedule
    check_frequency_minutes = Column(Integer, default=60)
    active_hours_start = Column(Integer, default=0)  # 0-23
    active_hours_end = Column(Integer, default=23)
    active_days = Column(JSON, default=[0,1,2,3,4,5,6])  # 0=Monday
    
    # Last execution
    last_checked = Column(DateTime(timezone=True))
    last_triggered = Column(DateTime(timezone=True))
    trigger_count = Column(Integer, default=0)
    
    # Relationships
    company = relationship("Company", back_populates="alerts")
    recipients = relationship("User", secondary=alert_recipients)
    notifications = relationship("Notification", back_populates="alert", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('ix_alerts_company_active', 'company_id', 'is_active'),
        Index('ix_alerts_type_severity', 'alert_type', 'severity'),
    )
    
    def __repr__(self):
        return f"<Alert {self.name}>"


class Notification(Base, TimestampMixin, TenantMixin):
    """User notifications"""
    
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    alert_id = Column(Integer, ForeignKey("alerts.id", ondelete="SET NULL"))
    
    # Notification details
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    data = Column(JSON)  # Additional data
    
    # Type and channel
    notification_type = Column(String(50))  # "alert", "report", "system"
    channel = Column(Enum(NotificationChannel), default=NotificationChannel.IN_APP)
    
    # Status
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime(timezone=True))
    is_sent = Column(Boolean, default=False)
    sent_at = Column(DateTime(timezone=True))
    
    # Priority
    priority = Column(Enum(AlertSeverity), default=AlertSeverity.LOW)
    expires_at = Column(DateTime(timezone=True))
    
    # Relationships
    user = relationship("User", back_populates="notifications")
    alert = relationship("Alert", back_populates="notifications")
    
    __table_args__ = (
        Index('ix_notifications_user_read', 'user_id', 'is_read'),
        Index('ix_notifications_company_created', 'company_id', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Notification {self.title}>"


class ChatHistory(Base, TimestampMixin, TenantMixin):
    """AI chat history"""
    
    __tablename__ = "chat_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_id = Column(String(100), nullable=False)
    
    # Message
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    message = Column(Text, nullable=False)
    
    # Context
    context = Column(JSON)  # Additional context sent to AI
    metadata = Column(JSON)  # Response metadata
    
    # Feedback
    rating = Column(Integer)  # 1-5 stars
    feedback = Column(Text)
    
    __table_args__ = (
        Index('ix_chat_user_session', 'user_id', 'session_id'),
        Index('ix_chat_company_created', 'company_id', 'created_at'),
    )
    
    def __repr__(self):
        return f"<ChatHistory {self.session_id}>"


class AuditLog(Base, TimestampMixin, TenantMixin):
    """Audit trail for all actions"""
    
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    
    # Action details
    action = Column(String(100), nullable=False)  # e.g., "user.login", "data.export"
    resource = Column(String(100))  # e.g., "users", "sales_data"
    resource_id = Column(Integer)
    
    # Request info
    method = Column(String(10))  # HTTP method
    endpoint = Column(String(255))
    ip_address = Column(String(45))
    user_agent = Column(Text)
    
    # Data
    old_values = Column(JSON)
    new_values = Column(JSON)
    
    # Status
    status_code = Column(Integer)
    success = Column(Boolean, default=True)
    error_message = Column(Text)
    
    # Performance
    duration_ms = Column(Integer)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    
    __table_args__ = (
        Index('ix_audit_company_created', 'company_id', 'created_at'),
        Index('ix_audit_user_action', 'user_id', 'action'),
        Index('ix_audit_resource', 'resource', 'resource_id'),
    )
    
    def __repr__(self):
        return f"<AuditLog {self.action} by User {self.user_id}>"


class APIKey(Base, TimestampMixin, TenantMixin):
    """API keys for external integrations"""
    
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Key details
    name = Column(String(255), nullable=False)
    key_hash = Column(String(255), nullable=False, unique=True)
    prefix = Column(String(20))  # Visible prefix for identification
    
    # Permissions
    scopes = Column(JSON, default=[])  # ["read:weather", "write:sales"]
    
    # Usage
    last_used = Column(DateTime(timezone=True))
    usage_count = Column(Integer, default=0)
    
    # Validity
    expires_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    
    # Rate limiting
    rate_limit_per_hour = Column(Integer, default=1000)
    
    # Relationships
    user = relationship("User", back_populates="api_keys")
    
    __table_args__ = (
        Index('ix_apikeys_company_active', 'company_id', 'is_active'),
        Index('ix_apikeys_hash', 'key_hash'),
    )
    
    def __repr__(self):
        return f"<APIKey {self.name}>"


class UserSession(Base, TimestampMixin, TenantMixin):
    """User sessions for tracking and security"""
    
    __tablename__ = "user_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Session details
    session_token = Column(String(255), nullable=False, unique=True, index=True)
    refresh_token = Column(String(255), unique=True, index=True)
    
    # Device info
    ip_address = Column(String(45))
    user_agent = Column(Text)
    device_type = Column(String(50))  # "desktop", "mobile", "tablet"
    browser = Column(String(50))
    os = Column(String(50))
    
    # Location
    country = Column(String(100))
    city = Column(String(100))
    
    # Validity
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True)
    revoked_at = Column(DateTime(timezone=True))
    
    # Activity
    last_activity = Column(DateTime(timezone=True))
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    
    __table_args__ = (
        Index('ix_sessions_user_active', 'user_id', 'is_active'),
        Index('ix_sessions_expires', 'expires_at'),
    )
    
    def __repr__(self):
        return f"<UserSession {self.session_token[:8]}...>"


class MLModel(Base, TimestampMixin, TenantMixin):
    """Machine learning models per company"""
    
    __tablename__ = "ml_models"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    model_type = Column(String(100))  # "sales_forecast", "weather_impact"
    version = Column(String(50))
    
    # Model file
    file_path = Column(String(500))
    file_size_mb = Column(Float)
    
    # Performance metrics
    accuracy = Column(Float)
    mse = Column(Float)
    mae = Column(Float)
    r2_score = Column(Float)
    
    # Training info
    trained_at = Column(DateTime(timezone=True))
    training_data_from = Column(Date)
    training_data_to = Column(Date)
    training_rows = Column(Integer)
    features = Column(JSON)  # List of features used
    parameters = Column(JSON)  # Model parameters
    
    # Status
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    
    __table_args__ = (
        UniqueConstraint('company_id', 'model_type', 'is_default', 
                        name='unique_default_model_per_type'),
        Index('ix_mlmodels_company_type', 'company_id', 'model_type'),
    )
    
    def __repr__(self):
        return f"<MLModel {self.name}>"


# ==================== DATABASE INITIALIZATION ====================

def create_all_tables(engine):
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)


def drop_all_tables(engine):
    """Drop all database tables (use with caution!)"""
    Base.metadata.drop_all(bind=engine)


# Export all models
__all__ = [
    # Enums
    "UserRole",
    "AlertType",
    "AlertSeverity",
    "NotificationChannel",
    "SubscriptionPlan",
    
    # Mixins
    "TimestampMixin",
    "TenantMixin",
    "SoftDeleteMixin",
    
    # Models
    "Company",
    "User",
    "Permission",
    "Location",
    "WeatherData",
    "Product",
    "SalesData",
    "Alert",
    "Notification",
    "ChatHistory",
    "AuditLog",
    "APIKey",
    "UserSession",
    "MLModel",
    
    # Functions
    "create_all_tables",
    "drop_all_tables",
]