"""
Modelo de exportação de dados e relatórios.
Gerencia jobs de exportação e templates.
"""

from typing import Optional, TYPE_CHECKING
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime,
    ForeignKey, Text, JSON, Index, BigInteger
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.config.database import Base, TimestampMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.company import Company


class ExportFormat(str):
    """Formatos de exportação suportados."""
    CSV = "csv"
    EXCEL = "excel"
    PDF = "pdf"
    JSON = "json"
    HTML = "html"
    POWERPOINT = "powerpoint"


class ExportStatus(str):
    """Status do job de exportação."""
    PENDING = "pending"  # Aguardando processamento
    PROCESSING = "processing"  # Processando
    COMPLETED = "completed"  # Concluído
    FAILED = "failed"  # Falhou
    CANCELLED = "cancelled"  # Cancelado
    EXPIRED = "expired"  # Expirado


class ExportType(str):
    """Tipos de exportação."""
    SALES_REPORT = "sales_report"
    WEATHER_REPORT = "weather_report"
    CORRELATION_ANALYSIS = "correlation_analysis"
    PREDICTION_REPORT = "prediction_report"
    EXECUTIVE_SUMMARY = "executive_summary"
    CUSTOM_REPORT = "custom_report"
    DATA_EXPORT = "data_export"
    DASHBOARD_SNAPSHOT = "dashboard_snapshot"


class ExportTemplate(Base, TimestampMixin, TenantMixin):
    """
    Templates de exportação/relatórios.
    """
    
    __tablename__ = "export_templates"
    
    # ==================== PRIMARY KEY ====================
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # ==================== TEMPLATE INFO ====================
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Nome do template"
    )
    
    slug: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Slug do template"
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Descrição do template"
    )
    
    type: Mapped[str] = mapped_column(
        String(50),
        default=ExportType.CUSTOM_REPORT,
        nullable=False,
        doc="Tipo de exportação"
    )
    
    # ==================== CONFIGURATION ====================
    format: Mapped[str] = mapped_column(
        String(20),
        default=ExportFormat.PDF,
        nullable=False,
        doc="Formato padrão"
    )
    
    supported_formats: Mapped[list] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        doc="Formatos suportados"
    )
    
    # ==================== TEMPLATE CONTENT ====================
    template_config: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        doc="""Configuração do template:
        {
            "sections": [...],
            "data_sources": [...],
            "filters": {...},
            "layout": {...}
        }"""
    )
    
    # ==================== DATA CONFIGURATION ====================
    data_sources: Mapped[list] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        doc="Fontes de dados necessárias"
    )
    
    default_filters: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        doc="Filtros padrão"
    )
    
    aggregations: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Agregações de dados"
    )
    
    # ==================== STYLING ====================
    style_config: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Configuração de estilo (cores, fontes, etc)"
    )
    
    include_branding: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Se inclui branding da empresa"
    )
    
    # ==================== SCHEDULING ====================
    is_schedulable: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Se pode ser agendado"
    )
    
    default_schedule: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="Agendamento padrão (cron)"
    )
    
    # ==================== PERMISSIONS ====================
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Se é template público"
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Se está ativo"
    )
    
    required_role: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        doc="Role mínimo necessário"
    )
    
    # ==================== USAGE ====================
    usage_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Número de vezes usado"
    )
    
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Última vez usado"
    )
    
    # ==================== METADATA ====================
    tags: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        doc="Tags do template"
    )
    
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Metadados adicionais"
    )
    
    # ==================== RELATIONSHIPS ====================
    export_jobs: Mapped[list["ExportJob"]] = relationship(
        "ExportJob",
        back_populates="template",
        cascade="all, delete-orphan"
    )
    
    # ==================== INDEXES ====================
    __table_args__ = (
        Index("idx_export_template_company_slug", "company_id", "slug", unique=True),
        Index("idx_export_template_type", "type"),
        Index("idx_export_template_active", "is_active"),
    )
    
    # ==================== METHODS ====================
    def increment_usage(self) -> None:
        """Incrementa contador de uso."""
        self.usage_count += 1
        self.last_used_at = datetime.now(timezone.utc)
    
    # ==================== STRING REPRESENTATION ====================
    def __repr__(self) -> str:
        return f"<ExportTemplate(id={self.id}, name={self.name})>"
    
    def __str__(self) -> str:
        return self.name


class ExportJob(Base, TimestampMixin, TenantMixin):
    """
    Jobs de exportação de dados/relatórios.
    """
    
    __tablename__ = "export_jobs"
    
    # ==================== PRIMARY KEY ====================
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # ==================== JOB INFO ====================
    job_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
        doc="ID único do job"
    )
    
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Nome do job/exportação"
    )
    
    type: Mapped[str] = mapped_column(
        String(50),
        default=ExportType.DATA_EXPORT,
        nullable=False,
        doc="Tipo de exportação"
    )
    
    format: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Formato de exportação"
    )
    
    # ==================== STATUS ====================
    status: Mapped[str] = mapped_column(
        String(20),
        default=ExportStatus.PENDING,
        nullable=False,
        index=True,
        doc="Status do job"
    )
    
    progress: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Progresso (0-100)"
    )
    
    # ==================== USER & TEMPLATE ====================
    requested_by_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        doc="ID do usuário que solicitou"
    )
    
    template_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("export_templates.id"),
        nullable=True,
        doc="ID do template usado"
    )
    
    # ==================== CONFIGURATION ====================
    config: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        doc="""Configuração do job:
        {
            "filters": {...},
            "date_range": {...},
            "columns": [...],
            "options": {...}
        }"""
    )
    
    # ==================== DATA SELECTION ====================
    data_sources: Mapped[list] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        doc="Fontes de dados"
    )
    
    filters: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        doc="Filtros aplicados"
    )
    
    date_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Data inicial dos dados"
    )
    
    date_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Data final dos dados"
    )
    
    # ==================== PROCESSING ====================
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Quando começou processamento"
    )
    
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Quando completou"
    )
    
    processing_time_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Tempo de processamento (ms)"
    )
    
    # ==================== OUTPUT ====================
    file_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        doc="Caminho do arquivo gerado"
    )
    
    file_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        doc="URL para download"
    )
    
    file_size_bytes: Mapped[Optional[BigInteger]] = mapped_column(
        BigInteger,
        nullable=True,
        doc="Tamanho do arquivo em bytes"
    )
    
    row_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Número de linhas exportadas"
    )
    
    # ==================== EXPIRATION ====================
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Quando o arquivo expira"
    )
    
    download_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Número de downloads"
    )
    
    last_downloaded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Último download"
    )
    
    # ==================== ERROR HANDLING ====================
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Mensagem de erro se falhou"
    )
    
    error_details: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Detalhes do erro"
    )
    
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Número de tentativas"
    )
    
    # ==================== SCHEDULING ====================
    is_scheduled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Se é job agendado"
    )
    
    schedule_config: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Configuração de agendamento"
    )
    
    next_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Próxima execução (se agendado)"
    )
    
    # ==================== NOTIFICATION ====================
    notify_on_complete: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Se notifica ao completar"
    )
    
    notification_sent: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Se notificação foi enviada"
    )
    
    # ==================== METADATA ====================
    tags: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        doc="Tags do job"
    )
    
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Metadados adicionais"
    )
    
    # ==================== RELATIONSHIPS ====================
    requested_by_user: Mapped["User"] = relationship(
        "User",
        back_populates="export_jobs"
    )
    
    template: Mapped[Optional["ExportTemplate"]] = relationship(
        "ExportTemplate",
        back_populates="export_jobs"
    )
    
    # ==================== INDEXES ====================
    __table_args__ = (
        Index("idx_export_job_company_status", "company_id", "status"),
        Index("idx_export_job_user", "requested_by_id"),
        Index("idx_export_job_created", "created_at"),
        Index("idx_export_job_expires", "expires_at"),
    )
    
    # ==================== PROPERTIES ====================
    @property
    def is_expired(self) -> bool:
        """Verifica se o arquivo expirou."""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    @property
    def is_ready(self) -> bool:
        """Verifica se está pronto para download."""
        return self.status == ExportStatus.COMPLETED and self.file_url is not None
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Duração do processamento em segundos."""
        if not self.started_at or not self.completed_at:
            return None
        delta = self.completed_at - self.started_at
        return delta.total_seconds()
    
    # ==================== METHODS ====================
    def start_processing(self) -> None:
        """Marca início do processamento."""
        self.status = ExportStatus.PROCESSING
        self.started_at = datetime.now(timezone.utc)
        self.progress = 0
    
    def complete_processing(
        self,
        file_path: str,
        file_url: str,
        file_size: int,
        row_count: Optional[int] = None
    ) -> None:
        """
        Marca fim do processamento.
        
        Args:
            file_path: Caminho do arquivo
            file_url: URL para download
            file_size: Tamanho em bytes
            row_count: Número de linhas
        """
        self.status = ExportStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
        self.progress = 100
        self.file_path = file_path
        self.file_url = file_url
        self.file_size_bytes = file_size
        self.row_count = row_count
        
        if self.started_at:
            delta = self.completed_at - self.started_at
            self.processing_time_ms = int(delta.total_seconds() * 1000)
    
    def fail_processing(self, error: str, details: Optional[dict] = None) -> None:
        """
        Marca falha no processamento.
        
        Args:
            error: Mensagem de erro
            details: Detalhes do erro
        """
        self.status = ExportStatus.FAILED
        self.error_message = error
        self.error_details = details
        self.retry_count += 1
    
    def update_progress(self, progress: int) -> None:
        """
        Atualiza progresso.
        
        Args:
            progress: Progresso (0-100)
        """
        self.progress = min(100, max(0, progress))
    
    def increment_download(self) -> None:
        """Incrementa contador de downloads."""
        self.download_count += 1
        self.last_downloaded_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> dict:
        """
        Converte job para dicionário.
        
        Returns:
            dict: Dados do job
        """
        return {
            "id": self.id,
            "job_id": self.job_id,
            "name": self.name,
            "type": self.type,
            "format": self.format,
            "status": self.status,
            "progress": self.progress,
            "file_url": self.file_url,
            "file_size_bytes": self.file_size_bytes,
            "row_count": self.row_count,
            "is_ready": self.is_ready,
            "is_expired": self.is_expired,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None
        }
    
    # ==================== STRING REPRESENTATION ====================
    def __repr__(self) -> str:
        return f"<ExportJob(id={self.id}, job_id={self.job_id}, status={self.status})>"
    
    def __str__(self) -> str:
        return f"{self.name} ({self.format.upper()})"