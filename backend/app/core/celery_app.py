# backend/app/core/celery_app.py
"""
Configuração do Celery para tasks assíncronas
"""

from celery import Celery
from celery.schedules import crontab
from kombu import Queue, Exchange
from app.core.config import settings
import os

# Configurar Celery
celery_app = Celery(
    "weatherbiz",
    broker=settings.REDIS_URL or "redis://localhost:6379/0",
    backend=settings.REDIS_URL or "redis://localhost:6379/0",
    include=[
        "app.tasks.weather_tasks",
        "app.tasks.ml_tasks",
        "app.tasks.notification_tasks",
        "app.tasks.report_tasks",
        "app.tasks.alert_tasks"
    ]
)

# Configurações do Celery
celery_app.conf.update(
    # Timezone
    timezone="America/Sao_Paulo",
    enable_utc=True,
    
    # Serialização
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # Performance
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Resultados
    result_expires=3600,  # 1 hora
    result_backend_always_retry=True,
    result_backend_max_retries=10,
    
    # Retry policy
    task_default_retry_delay=60,  # 60 segundos
    task_max_retries=3,
    
    # Rate limits
    task_annotations={
        "app.tasks.weather_tasks.fetch_weather_data": {
            "rate_limit": "10/m"  # 10 por minuto
        },
        "app.tasks.notification_tasks.send_email": {
            "rate_limit": "30/m"  # 30 emails por minuto
        }
    }
)

# Configurar filas
celery_app.conf.task_routes = {
    "app.tasks.weather_tasks.*": {"queue": "weather"},
    "app.tasks.ml_tasks.*": {"queue": "ml", "priority": 5},
    "app.tasks.notification_tasks.*": {"queue": "notifications"},
    "app.tasks.report_tasks.*": {"queue": "reports", "priority": 3},
    "app.tasks.alert_tasks.*": {"queue": "alerts", "priority": 10}
}

# Configurar exchanges e queues
default_exchange = Exchange("default", type="direct")
weather_exchange = Exchange("weather", type="topic")
ml_exchange = Exchange("ml", type="topic")

celery_app.conf.task_queues = (
    Queue("default", default_exchange, routing_key="default"),
    Queue("weather", weather_exchange, routing_key="weather.*"),
    Queue("ml", ml_exchange, routing_key="ml.*", priority=5),
    Queue("notifications", default_exchange, routing_key="notifications"),
    Queue("reports", default_exchange, routing_key="reports", priority=3),
    Queue("alerts", default_exchange, routing_key="alerts", priority=10)
)

# Tarefas agendadas (Celery Beat)
celery_app.conf.beat_schedule = {
    # Buscar dados climáticos a cada hora
    "fetch-weather-hourly": {
        "task": "app.tasks.weather_tasks.fetch_all_companies_weather",
        "schedule": crontab(minute="0"),  # A cada hora
        "options": {"queue": "weather"}
    },
    
    # Processar alertas a cada 5 minutos
    "check-alerts": {
        "task": "app.tasks.alert_tasks.check_all_alerts",
        "schedule": crontab(minute="*/5"),  # A cada 5 minutos
        "options": {"queue": "alerts", "priority": 10}
    },
    
    # Treinar modelos ML diariamente às 3h
    "train-ml-models": {
        "task": "app.tasks.ml_tasks.retrain_all_models",
        "schedule": crontab(hour=3, minute=0),  # Diariamente às 3h
        "options": {"queue": "ml"}
    },
    
    # Gerar relatórios semanais (segunda às 8h)
    "weekly-reports": {
        "task": "app.tasks.report_tasks.generate_weekly_reports",
        "schedule": crontab(hour=8, minute=0, day_of_week=1),  # Segunda às 8h
        "options": {"queue": "reports"}
    },
    
    # Limpeza de dados antigos (domingo às 2h)
    "cleanup-old-data": {
        "task": "app.tasks.cleanup_tasks.cleanup_old_data",
        "schedule": crontab(hour=2, minute=0, day_of_week=0),  # Domingo às 2h
        "options": {"queue": "default"}
    }
}

# Health check
@celery_app.task(bind=True)
def health_check(self):
    """Task para verificar se o Celery está funcionando"""
    return {
        "status": "healthy",
        "worker": self.request.hostname,
        "task_id": self.request.id
    }