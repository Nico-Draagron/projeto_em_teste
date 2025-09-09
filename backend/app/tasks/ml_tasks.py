# ===========================
# backend/app/tasks/ml_tasks.py
# ===========================

from celery import Task
from celery.utils.log import get_task_logger
from datetime import datetime, timedelta
import pickle
import joblib
from pathlib import Path

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.database import Company, MLModel, SalesData, WeatherData
from app.services.ml_service import MLService

logger = get_task_logger(__name__)


@celery_app.task(name="train_ml_model")
def train_ml_model(
    company_id: str,
    model_type: str = "sales_prediction",
    force_retrain: bool = False
) -> Dict:
    """
    Treina ou retreina modelo ML para uma empresa
    """
    logger.info(f"Training ML model for company {company_id}, type: {model_type}")
    
    db = SessionLocal()
    
    try:
        ml_service = MLService(db, company_id)
        
        # Verificar se precisa treinar
        existing_model = db.query(MLModel).filter(
            MLModel.company_id == company_id,
            MLModel.model_type == model_type,
            MLModel.is_active == True
        ).first()
        
        if existing_model and not force_retrain:
            # Verificar se o modelo é recente (menos de 7 dias)
            if existing_model.trained_at > datetime.utcnow() - timedelta(days=7):
                logger.info("Model is recent, skipping training")
                return {
                    "status": "skipped",
                    "reason": "Model is recent",
                    "model_id": existing_model.id
                }
        
        # Treinar novo modelo
        result = ml_service.train_sales_model(
            start_date=datetime.utcnow() - timedelta(days=365),  # 1 ano de dados
            end_date=datetime.utcnow()
        )
        
        logger.info(f"Model trained successfully: {result}")
        return {
            "status": "success",
            "model_id": result["model_id"],
            "metrics": result["metrics"]
        }
        
    except Exception as e:
        logger.error(f"Error training model: {str(e)}")
        raise
    finally:
        db.close()


@celery_app.task(name="retrain_all_models")
def retrain_all_models() -> Dict:
    """
    Retreina modelos para todas as empresas ativas
    """
    logger.info("Starting model retraining for all companies")
    
    db = SessionLocal()
    results = []
    
    try:
        companies = db.query(Company).filter(
            Company.is_active == True,
            Company.subscription_plan.in_(["professional", "enterprise"])
        ).all()
        
        for company in companies:
            # Verificar se tem dados suficientes
            sales_count = db.query(SalesData).filter(
                SalesData.company_id == company.id
            ).count()
            
            if sales_count >= 100:  # Mínimo de 100 registros
                task = train_ml_model.apply_async(
                    args=[company.id, "sales_prediction", False],
                    queue="ml"
                )
                results.append({
                    "company_id": company.id,
                    "task_id": task.id
                })
        
        return {
            "status": "success",
            "models_scheduled": len(results)
        }
        
    except Exception as e:
        logger.error(f"Error scheduling model training: {str(e)}")
        raise
    finally:
        db.close()