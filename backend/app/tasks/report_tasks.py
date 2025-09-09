# ===========================
# backend/app/tasks/report_tasks.py
# ===========================

from celery.utils.log import get_task_logger
from datetime import datetime, timedelta

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.database import Company, ExportJob
from app.services.export_service import ExportService, ReportType, ExportFormat

logger = get_task_logger(__name__)


@celery_app.task(name="generate_report")
def generate_report(
    company_id: str,
    report_type: str,
    format: str,
    start_date: str,
    end_date: str,
    user_id: str,
    options: Optional[Dict] = None
) -> Dict:
    """
    Gera relatório assíncrono
    """
    logger.info(f"Generating {report_type} report for company {company_id}")
    
    db = SessionLocal()
    
    try:
        export_service = ExportService(db, company_id)
        
        # Converter strings para datetime
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
        
        # Gerar relatório
        result = export_service.generate_report(
            report_type=ReportType(report_type),
            format=ExportFormat(format),
            start_date=start_dt,
            end_date=end_dt,
            options=options or {},
            user_id=user_id
        )
        
        # Atualizar job status
        job = db.query(ExportJob).filter(
            ExportJob.id == result["job_id"]
        ).first()
        
        if job:
            job.status = "completed"
            job.file_path = result["file_path"]
            job.completed_at = datetime.utcnow()
            db.commit()
        
        # Enviar notificação
        send_email.apply_async(
            args=[
                [result["user_email"]],
                f"Relatório {report_type} pronto",
                f"Seu relatório está pronto para download: {result['download_url']}",
                None,
                None,
                company_id
            ],
            queue="notifications"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error generating report: {str(e)}")
        
        # Atualizar status do job
        if "job_id" in locals():
            job = db.query(ExportJob).filter(
                ExportJob.id == job_id
            ).first()
            if job:
                job.status = "failed"
                job.error_message = str(e)
                db.commit()
        
        raise
    finally:
        db.close()


@celery_app.task(name="generate_weekly_reports")
def generate_weekly_reports() -> Dict:
    """
    Gera relatórios semanais para todas as empresas
    """
    logger.info("Generating weekly reports for all companies")
    
    db = SessionLocal()
    results = []
    
    try:
        # Buscar empresas com relatórios agendados
        companies = db.query(Company).filter(
            Company.is_active == True,
            Company.settings["weekly_report_enabled"] == True
        ).all()
        
        for company in companies:
            # Calcular período
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=7)
            
            # Agendar geração do relatório
            task = generate_report.apply_async(
                args=[
                    company.id,
                    "executive_summary",
                    "pdf",
                    start_date.isoformat(),
                    end_date.isoformat(),
                    company.owner_id,
                    {"scheduled": True}
                ],
                queue="reports"
            )
            
            results.append({
                "company_id": company.id,
                "task_id": task.id
            })
        
        return {
            "status": "success",
            "reports_scheduled": len(results)
        }
        
    finally:
        db.close()
