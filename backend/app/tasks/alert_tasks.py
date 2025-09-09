# ===========================
# backend/app/tasks/alert_tasks.py
# ===========================

from celery.utils.log import get_task_logger
from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.database import Alert, AlertRule, Company
from app.services.alert_service import AlertService

logger = get_task_logger(__name__)


@celery_app.task(name="check_alert_conditions")
def check_alert_conditions(company_id: str, alert_rule_id: str) -> Dict:
    """
    Verifica condições de um alerta específico
    """
    logger.info(f"Checking alert conditions for rule {alert_rule_id}")
    
    db = SessionLocal()
    
    try:
        alert_service = AlertService(db, company_id)
        
        # Verificar condições
        triggered = alert_service.check_alert_rule(alert_rule_id)
        
        if triggered:
            # Criar alerta
            alert = alert_service.create_alert(
                rule_id=alert_rule_id,
                triggered_value=triggered["value"],
                message=triggered["message"]
            )
            
            # Enviar notificações
            alert_service.send_alert_notifications(alert.id)
            
            return {
                "status": "triggered",
                "alert_id": alert.id,
                "message": triggered["message"]
            }
        
        return {
            "status": "not_triggered",
            "rule_id": alert_rule_id
        }
        
    finally:
        db.close()


@celery_app.task(name="check_all_alerts")
def check_all_alerts() -> Dict:
    """
    Verifica todos os alertas ativos
    """
    logger.info("Checking all active alerts")
    
    db = SessionLocal()
    results = []
    
    try:
        # Buscar todas as regras ativas
        alert_rules = db.query(AlertRule).join(Company).filter(
            AlertRule.is_active == True,
            Company.is_active == True
        ).all()
        
        for rule in alert_rules:
            task = check_alert_conditions.apply_async(
                args=[rule.company_id, rule.id],
                queue="alerts"
            )
            results.append({
                "rule_id": rule.id,
                "task_id": task.id
            })
        
        return {
            "status": "success",
            "alerts_checked": len(results)
        }
        
    finally:
        db.close()