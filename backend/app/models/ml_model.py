"""
Modelo para gerenciamento de modelos de Machine Learning.
Armazena informações sobre modelos treinados, performance e jobs de treinamento.
"""

from typing import Optional, TYPE_CHECKING
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime,
    ForeignKey, Text, JSON, Index, Float, BigInteger
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.config.database import Base, TimestampMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.company import Company


class ModelType(str):
    """Tipos de modelos ML."""
    SALES_PREDICTION = "sales_prediction"
    WEATHER_IMPACT = "weather_impact"
    ANOMALY_DETECTION = "anomaly_detection"
    DEMAND_FORECAST = "demand_forecast"
    CORRELATION_ANALYSIS = "correlation_analysis"
    CUSTOMER_SEGMENTATION = "customer_segmentation"
    CUSTOM = "custom"


class ModelStatus(str):
    """Status do modelo."""
    DRAFT = "draft"  # Em desenvolvimento
    TRAINING = "training"  # Treinando
    VALIDATING = "validating"  # Validando
    ACTIVE = "active"  # Ativo/em produção
    INACTIVE = "inactive"  # Inativo
    DEPRECATED = "deprecated"  # Deprecado
    FAILED = "failed"  # Falhou no treinamento


class TrainingStatus(str):
    """Status do job de treinamento."""
    PENDING = "pending"
    PREPARING_DATA = "preparing_data"
    TRAINING = "training"
    VALIDATING = "validating"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MLModel(Base, TimestampMixin, TenantMixin):
    """
    Modelos de Machine Learning por empresa.
    """
    
    __tablename__ = "ml_models"
    
    # ==================== PRIMARY KEY ====================
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # ==================== MODEL INFO ====================
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Nome do modelo"
    )
    
    version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Versão do modelo"
    )
    
    type: Mapped[str] = mapped_column(
        String(50),
        default=ModelType.CUSTOM,
        nullable=False,
        index=True,
        doc="Tipo do modelo"
    )
    
    algorithm: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Algoritmo usado (random_forest, xgboost, lstm, etc)"
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Descrição do modelo"
    )
    
    # ==================== STATUS ====================
    status: Mapped[str] = mapped_column(
        String(20),
        default=ModelStatus.DRAFT,
        nullable=False,
        index=True,
        doc="Status do modelo"
    )
    
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Se é o modelo principal para o tipo"
    )
    
    is_auto_retrain: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Se tem retreino automático"
    )
    
    # ==================== FILE STORAGE ====================
    model_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        doc="Caminho do arquivo .pkl do modelo"
    )
    
    model_size_bytes: Mapped[Optional[BigInteger]] = mapped_column(
        BigInteger,
        nullable=True,
        doc="Tamanho do modelo em bytes"
    )
    
    # ==================== FEATURES ====================
    features: Mapped[list] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        doc="Lista de features usadas"
    )
    
    feature_importance: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Importância de cada feature"
    )
    
    target_variable: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Variável alvo"
    )
    
    # ==================== TRAINING CONFIG ====================
    training_config: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        doc="""Configuração de treinamento:
        {
            "hyperparameters": {...},
            "preprocessing": {...},
            "validation": {...}
        }"""
    )
    
    hyperparameters: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        doc="Hiperparâmetros do modelo"
    )
    
    # ==================== DATA INFO ====================
    training_data_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Início dos dados de treino"
    )
    
    training_data_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Fim dos dados de treino"
    )
    
    training_samples: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Número de amostras de treino"
    )
    
    validation_samples: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Número de amostras de validação"
    )
    
    test_samples: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Número de amostras de teste"
    )
    
    # ==================== PERFORMANCE METRICS ====================
    metrics: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        doc="""Métricas de performance:
        {
            "train": {"rmse": ..., "mae": ..., "r2": ...},
            "validation": {...},
            "test": {...}
        }"""
    )
    
    accuracy: Mapped[Optional[Float]] = mapped_column(
        Float,
        nullable=True,
        doc="Acurácia (para classificação)"
    )
    
    rmse: Mapped[Optional[Float]] = mapped_column(
        Float,
        nullable=True,
        doc="RMSE (para regressão)"
    )
    
    mae: Mapped[Optional[Float]] = mapped_column(
        Float,
        nullable=True,
        doc="MAE (para regressão)"
    )
    
    r2_score: Mapped[Optional[Float]] = mapped_column(
        Float,
        nullable=True,
        doc="R² Score"
    )
    
    # ==================== TRAINING HISTORY ====================
    trained_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Quando foi treinado"
    )
    
    training_duration_seconds: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Duração do treinamento (segundos)"
    )
    
    last_retrained_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Último retreino"
    )
    
    retrain_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Número de retreinos"
    )
    
    next_retrain_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Próximo retreino agendado"
    )
    
    # ==================== DEPLOYMENT ====================
    deployed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Quando foi colocado em produção"
    )
    
    deployment_endpoint: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Endpoint de deployment"
    )
    
    # ==================== USAGE STATS ====================
    prediction_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Número de predições feitas"
    )
    
    last_prediction_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Última predição"
    )
    
    average_prediction_time_ms: Mapped[Optional[Float]] = mapped_column(
        Float,
        nullable=True,
        doc="Tempo médio de predição (ms)"
    )
    
    # ==================== MONITORING ====================
    drift_detected: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Se foi detectado drift"
    )
    
    drift_score: Mapped[Optional[Float]] = mapped_column(
        Float,
        nullable=True,
        doc="Score de drift (0-1)"
    )
    
    last_monitored_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Última verificação de monitoring"
    )
    
    alerts_config: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Configuração de alertas do modelo"
    )
    
    # ==================== METADATA ====================
    tags: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        doc="Tags do modelo"
    )
    
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Metadados adicionais"
    )
    
    # ==================== RELATIONSHIPS ====================
    company: Mapped["Company"] = relationship(
        "Company",
        back_populates="ml_models"
    )
    
    training_jobs: Mapped[list["ModelTrainingJob"]] = relationship(
        "ModelTrainingJob",
        back_populates="model",
        cascade="all, delete-orphan"
    )
    
    performance_history: Mapped[list["ModelPerformance"]] = relationship(
        "ModelPerformance",
        back_populates="model",
        cascade="all, delete-orphan"
    )
    
    # ==================== INDEXES ====================
    __table_args__ = (
        Index("idx_ml_model_company_type", "company_id", "type"),
        Index("idx_ml_model_company_status", "company_id", "status"),
        Index("idx_ml_model_primary", "company_id", "type", "is_primary"),
    )
    
    # ==================== METHODS ====================
    def activate(self) -> None:
        """Ativa o modelo."""
        self.status = ModelStatus.ACTIVE
        self.deployed_at = datetime.now(timezone.utc)
    
    def deactivate(self) -> None:
        """Desativa o modelo."""
        self.status = ModelStatus.INACTIVE
    
    def deprecate(self) -> None:
        """Marca modelo como deprecado."""
        self.status = ModelStatus.DEPRECATED
    
    def increment_prediction_count(self) -> None:
        """Incrementa contador de predições."""
        self.prediction_count += 1
        self.last_prediction_at = datetime.now(timezone.utc)
    
    def should_retrain(self) -> bool:
        """Verifica se deve retreinar."""
        if not self.is_auto_retrain:
            return False
        
        if self.drift_detected:
            return True
        
        if self.next_retrain_at:
            return datetime.now(timezone.utc) >= self.next_retrain_at
        
        return False
    
    # ==================== STRING REPRESENTATION ====================
    def __repr__(self) -> str:
        return f"<MLModel(id={self.id}, name={self.name}, type={self.type})>"
    
    def __str__(self) -> str:
        return f"{self.name} v{self.version}"


class ModelTrainingJob(Base, TimestampMixin, TenantMixin):
    """
    Jobs de treinamento de modelos.
    """
    
    __tablename__ = "model_training_jobs"
    
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
    
    model_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ml_models.id"),
        nullable=False,
        index=True,
        doc="ID do modelo"
    )
    
    # ==================== STATUS ====================
    status: Mapped[str] = mapped_column(
        String(20),
        default=TrainingStatus.PENDING,
        nullable=False,
        index=True,
        doc="Status do treinamento"
    )
    
    progress: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Progresso (0-100)"
    )
    
    current_epoch: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Época atual (para deep learning)"
    )
    
    total_epochs: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Total de épocas"
    )
    
    # ==================== TIMING ====================
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Início do treinamento"
    )
    
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Fim do treinamento"
    )
    
    estimated_completion: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Estimativa de conclusão"
    )
    
    # ==================== CONFIGURATION ====================
    config: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        doc="Configuração do treinamento"
    )
    
    hyperparameters: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        doc="Hiperparâmetros usados"
    )
    
    # ==================== DATA ====================
    data_config: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        doc="Configuração dos dados"
    )
    
    samples_processed: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Amostras processadas"
    )
    
    # ==================== RESULTS ====================
    final_metrics: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Métricas finais"
    )
    
    best_score: Mapped[Optional[Float]] = mapped_column(
        Float,
        nullable=True,
        doc="Melhor score obtido"
    )
    
    model_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        doc="Caminho do modelo treinado"
    )
    
    # ==================== LOGS ====================
    logs: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        doc="Logs do treinamento"
    )
    
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Mensagem de erro se falhou"
    )
    
    # ==================== RESOURCES ====================
    cpu_usage_percent: Mapped[Optional[Float]] = mapped_column(
        Float,
        nullable=True,
        doc="Uso de CPU (%)"
    )
    
    memory_usage_mb: Mapped[Optional[Float]] = mapped_column(
        Float,
        nullable=True,
        doc="Uso de memória (MB)"
    )
    
    gpu_usage_percent: Mapped[Optional[Float]] = mapped_column(
        Float,
        nullable=True,
        doc="Uso de GPU (%)"
    )
    
    # ==================== METADATA ====================
    triggered_by: Mapped[str] = mapped_column(
        String(50),
        default="manual",
        nullable=False,
        doc="Como foi disparado (manual/auto/scheduled)"
    )
    
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Metadados adicionais"
    )
    
    # ==================== RELATIONSHIPS ====================
    model: Mapped["MLModel"] = relationship(
        "MLModel",
        back_populates="training_jobs"
    )
    
    # ==================== INDEXES ====================
    __table_args__ = (
        Index("idx_training_job_model", "model_id"),
        Index("idx_training_job_status", "status"),
        Index("idx_training_job_started", "started_at"),
    )
    
    # ==================== STRING REPRESENTATION ====================
    def __repr__(self) -> str:
        return f"<ModelTrainingJob(id={self.id}, job_id={self.job_id}, status={self.status})>"


class ModelPerformance(Base, TimestampMixin, TenantMixin):
    """
    Histórico de performance dos modelos.
    """
    
    __tablename__ = "model_performance"
    
    # ==================== PRIMARY KEY ====================
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # ==================== MODEL REFERENCE ====================
    model_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ml_models.id"),
        nullable=False,
        index=True,
        doc="ID do modelo"
    )
    
    # ==================== EVALUATION INFO ====================
    evaluation_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False,
        doc="Data da avaliação"
    )
    
    evaluation_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Tipo de avaliação (daily/weekly/monthly/manual)"
    )
    
    # ==================== METRICS ====================
    accuracy: Mapped[Optional[Float]] = mapped_column(
        Float,
        nullable=True,
        doc="Acurácia"
    )
    
    precision: Mapped[Optional[Float]] = mapped_column(
        Float,
        nullable=True,
        doc="Precisão"
    )
    
    recall: Mapped[Optional[Float]] = mapped_column(
        Float,
        nullable=True,
        doc="Recall"
    )
    
    f1_score: Mapped[Optional[Float]] = mapped_column(
        Float,
        nullable=True,
        doc="F1 Score"
    )
    
    rmse: Mapped[Optional[Float]] = mapped_column(
        Float,
        nullable=True,
        doc="RMSE"
    )
    
    mae: Mapped[Optional[Float]] = mapped_column(
        Float,
        nullable=True,
        doc="MAE"
    )
    
    mape: Mapped[Optional[Float]] = mapped_column(
        Float,
        nullable=True,
        doc="MAPE (%)"
    )
    
    r2_score: Mapped[Optional[Float]] = mapped_column(
        Float,
        nullable=True,
        doc="R² Score"
    )
    
    # ==================== ADDITIONAL METRICS ====================
    custom_metrics: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Métricas customizadas"
    )
    
    confusion_matrix: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        doc="Matriz de confusão"
    )
    
    # ==================== DATA INFO ====================
    samples_evaluated: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Amostras avaliadas"
    )
    
    data_period_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Início do período dos dados"
    )
    
    data_period_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Fim do período dos dados"
    )
    
    # ==================== DRIFT DETECTION ====================
    drift_detected: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Se foi detectado drift"
    )
    
    drift_score: Mapped[Optional[Float]] = mapped_column(
        Float,
        nullable=True,
        doc="Score de drift"
    )
    
    feature_drift: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Drift por feature"
    )
    
    # ==================== RELATIONSHIPS ====================
    model: Mapped["MLModel"] = relationship(
        "MLModel",
        back_populates="performance_history"
    )
    
    # ==================== INDEXES ====================
    __table_args__ = (
        Index("idx_model_performance_model", "model_id"),
        Index("idx_model_performance_date", "evaluation_date"),
    )
    
    # ==================== STRING REPRESENTATION ====================
    def __repr__(self) -> str:
        return f"<ModelPerformance(model_id={self.model_id}, date={self.evaluation_date})>"