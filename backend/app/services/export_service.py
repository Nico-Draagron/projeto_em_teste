# Geração de relatórios
# backend/app/services/export_service.py

import os
import json
import asyncio
from typing import Dict, Any, List, Optional, BinaryIO
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
import pandas as pd
import numpy as np
from io import BytesIO
import xlsxwriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, Image, PageBreak, KeepTogether
)
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import hashlib
import logging
from ..models.database import (
    ExportJob, ExportTemplate, Company, User,
    SalesData, WeatherData, Alert
)
from ..models.schemas import ExportRequest, ExportResponse
from ..core.exceptions import ExportError, ValidationError
from ..core.config import settings
from ..services.sales_service import SalesService
from ..services.ml_service import MLService

logger = logging.getLogger(__name__)

class ExportFormat(Enum):
    PDF = "pdf"
    EXCEL = "excel"
    CSV = "csv"
    JSON = "json"
    POWERPOINT = "powerpoint"

class ReportType(Enum):
    EXECUTIVE_SUMMARY = "executive_summary"
    SALES_ANALYSIS = "sales_analysis"
    WEATHER_IMPACT = "weather_impact"
    PREDICTIONS = "predictions"
    ALERTS_SUMMARY = "alerts_summary"
    CUSTOM = "custom"

class ExportService:
    """Service para geração e exportação de relatórios"""
    
    def __init__(self, db: Session, company_id: str):
        self.db = db
        self.company_id = company_id
        self.export_path = Path("exports") / company_id
        self.export_path.mkdir(parents=True, exist_ok=True)
        self.sales_service = SalesService(db, company_id)
        self.ml_service = MLService(db, company_id)
        
    async def generate_report(
        self,
        report_type: ReportType,
        format: ExportFormat,
        start_date: datetime,
        end_date: datetime,
        filters: Optional[Dict] = None,
        template_id: Optional[str] = None,
        include_charts: bool = True,
        async_generation: bool = True
    ) -> ExportResponse:
        """
        Gera relatório com formato especificado
        """
        try:
            # Criar job de exportação
            job = ExportJob(
                company_id=self.company_id,
                report_type=report_type.value,
                format=format.value,
                status="processing",
                parameters=json.dumps({
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "filters": filters,
                    "include_charts": include_charts
                }),
                created_at=datetime.utcnow()
            )
            
            self.db.add(job)
            self.db.commit()
            
            if async_generation:
                # Processar em background
                asyncio.create_task(self._process_report_async(job))
                
                return ExportResponse(
                    job_id=job.id,
                    status="processing",
                    message="Report generation started",
                    estimated_time=self._estimate_generation_time(report_type)
                )
            else:
                # Processar sincrono
                result = await self._generate_report_content(
                    job,
                    report_type,
                    format,
                    start_date,
                    end_date,
                    filters,
                    template_id,
                    include_charts
                )
                
                return ExportResponse(
                    job_id=job.id,
                    status="completed",
                    file_path=result["file_path"],
                    file_url=result["file_url"],
                    file_size=result["file_size"]
                )
                
        except Exception as e:
            logger.error(f"Error generating report: {str(e)}")
            if 'job' in locals():
                job.status = "failed"
                job.error_message = str(e)
                self.db.commit()
            raise ExportError(f"Failed to generate report: {str(e)}")
    
    async def generate_pdf(
        self,
        data: Dict[str, Any],
        template: Optional[ExportTemplate] = None
    ) -> bytes:
        """
        Gera relatório em PDF
        """
        try:
            buffer = BytesIO()
            
            # Configurar documento
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=18
            )
            
            # Container de elementos
            story = []
            
            # Estilos
            styles = self._get_pdf_styles()
            
            # Adicionar logo e cabeçalho
            story.extend(self._create_pdf_header(styles, data))
            
            # Adicionar sumário executivo
            if "executive_summary" in data:
                story.extend(self._create_executive_summary(styles, data["executive_summary"]))
            
            # Adicionar análise de vendas
            if "sales_analysis" in data:
                story.extend(self._create_sales_section(styles, data["sales_analysis"]))
            
            # Adicionar análise climática
            if "weather_analysis" in data:
                story.extend(self._create_weather_section(styles, data["weather_analysis"]))
            
            # Adicionar previsões
            if "predictions" in data:
                story.extend(self._create_predictions_section(styles, data["predictions"]))
            
            # Adicionar gráficos
            if "charts" in data:
                story.extend(self._create_charts_section(data["charts"]))
            
            # Adicionar conclusões e recomendações
            if "recommendations" in data:
                story.extend(self._create_recommendations_section(styles, data["recommendations"]))
            
            # Construir PDF
            doc.build(story, onFirstPage=self._add_page_number, onLaterPages=self._add_page_number)
            
            # Retornar bytes
            buffer.seek(0)
            return buffer.read()
            
        except Exception as e:
            logger.error(f"Error generating PDF: {str(e)}")
            raise ExportError(f"Failed to generate PDF: {str(e)}")
    
    async def generate_excel(
        self,
        data: Dict[str, Any],
        include_charts: bool = True
    ) -> bytes:
        """
        Gera relatório em Excel com múltiplas abas
        """
        try:
            buffer = BytesIO()
            
            # Criar workbook
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                workbook = writer.book
                
                # Formatos customizados
                header_format = workbook.add_format({
                    'bold': True,
                    'text_wrap': True,
                    'valign': 'top',
                    'fg_color': '#4472C4',
                    'font_color': 'white',
                    'border': 1
                })
                
                currency_format = workbook.add_format({'num_format': 'R$ #,##0.00'})
                percent_format = workbook.add_format({'num_format': '0.00%'})
                date_format = workbook.add_format({'num_format': 'dd/mm/yyyy'})
                
                # Aba: Resumo Executivo
                if "executive_summary" in data:
                    df_summary = pd.DataFrame([data["executive_summary"]])
                    df_summary.to_excel(writer, sheet_name='Resumo', index=False)
                    
                    worksheet = writer.sheets['Resumo']
                    worksheet.set_column('A:Z', 15)
                
                # Aba: Dados de Vendas
                if "sales_data" in data:
                    df_sales = pd.DataFrame(data["sales_data"])
                    df_sales.to_excel(writer, sheet_name='Vendas', index=False)
                    
                    worksheet = writer.sheets['Vendas']
                    
                    # Aplicar formatos
                    for col_num, col_name in enumerate(df_sales.columns):
                        worksheet.write(0, col_num, col_name, header_format)
                        
                        if 'revenue' in col_name.lower() or 'valor' in col_name.lower():
                            worksheet.set_column(col_num, col_num, 15, currency_format)
                        elif 'date' in col_name.lower() or 'data' in col_name.lower():
                            worksheet.set_column(col_num, col_num, 12, date_format)
                
                # Aba: Dados Climáticos
                if "weather_data" in data:
                    df_weather = pd.DataFrame(data["weather_data"])
                    df_weather.to_excel(writer, sheet_name='Clima', index=False)
                    
                    worksheet = writer.sheets['Clima']
                    for col_num, col_name in enumerate(df_weather.columns):
                        worksheet.write(0, col_num, col_name, header_format)
                
                # Aba: Correlações
                if "correlations" in data:
                    df_corr = pd.DataFrame(data["correlations"])
                    df_corr.to_excel(writer, sheet_name='Correlações', index=True)
                    
                    worksheet = writer.sheets['Correlações']
                    
                    # Aplicar formatação condicional para heatmap
                    worksheet.conditional_format('B2:Z100', {
                        'type': '3_color_scale',
                        'min_color': '#FF0000',
                        'mid_color': '#FFFF00',
                        'max_color': '#00FF00'
                    })
                
                # Aba: Previsões
                if "predictions" in data:
                    df_pred = pd.DataFrame(data["predictions"])
                    df_pred.to_excel(writer, sheet_name='Previsões', index=False)
                    
                    worksheet = writer.sheets['Previsões']
                    for col_num, col_name in enumerate(df_pred.columns):
                        worksheet.write(0, col_num, col_name, header_format)
                
                # Adicionar gráficos se solicitado
                if include_charts and "charts_data" in data:
                    self._add_excel_charts(workbook, writer, data["charts_data"])
                
                # Aba: Metadados
                metadata = {
                    'Gerado em': datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
                    'Empresa': await self._get_company_name(),
                    'Período': f"{data.get('start_date', 'N/A')} até {data.get('end_date', 'N/A')}",
                    'Versão': '1.0'
                }
                df_meta = pd.DataFrame([metadata])
                df_meta.to_excel(writer, sheet_name='Info', index=False)
            
            buffer.seek(0)
            return buffer.read()
            
        except Exception as e:
            logger.error(f"Error generating Excel: {str(e)}")
            raise ExportError(f"Failed to generate Excel: {str(e)}")
    
    async def generate_csv(
        self,
        data: Dict[str, Any],
        dataset: str = "all"
    ) -> bytes:
        """
        Gera exportação em CSV
        """
        try:
            buffer = BytesIO()
            
            # Selecionar dataset
            if dataset == "sales" and "sales_data" in data:
                df = pd.DataFrame(data["sales_data"])
            elif dataset == "weather" and "weather_data" in data:
                df = pd.DataFrame(data["weather_data"])
            elif dataset == "combined":
                # Combinar vendas e clima
                df_sales = pd.DataFrame(data.get("sales_data", []))
                df_weather = pd.DataFrame(data.get("weather_data", []))
                
                if not df_sales.empty and not df_weather.empty:
                    df = pd.merge(df_sales, df_weather, on='date', how='inner')
                else:
                    df = df_sales if not df_sales.empty else df_weather
            else:
                # Todos os dados em formato flat
                df = self._flatten_data_for_csv(data)
            
            # Exportar para CSV
            csv_string = df.to_csv(index=False, encoding='utf-8')
            buffer.write(csv_string.encode('utf-8'))
            
            buffer.seek(0)
            return buffer.read()
            
        except Exception as e:
            logger.error(f"Error generating CSV: {str(e)}")
            raise ExportError(f"Failed to generate CSV: {str(e)}")
    
    async def schedule_report(
        self,
        report_config: Dict[str, Any],
        schedule: str,  # daily, weekly, monthly
        recipients: List[str],
        start_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Agenda geração automática de relatórios
        """
        try:
            # Criar template se não existir
            template = ExportTemplate(
                company_id=self.company_id,
                name=report_config.get("name", f"Scheduled Report {schedule}"),
                report_type=report_config["report_type"],
                format=report_config.get("format", "pdf"),
                parameters=json.dumps(report_config),
                schedule=schedule,
                recipients=json.dumps(recipients),
                is_active=True,
                next_run=start_time or self._calculate_next_run(schedule),
                created_at=datetime.utcnow()
            )
            
            self.db.add(template)
            self.db.commit()
            
            logger.info(f"Report scheduled: {template.name}")
            
            return {
                "template_id": template.id,
                "name": template.name,
                "schedule": schedule,
                "next_run": template.next_run.isoformat(),
                "recipients": recipients
            }
            
        except Exception as e:
            logger.error(f"Error scheduling report: {str(e)}")
            self.db.rollback()
            raise ExportError(f"Failed to schedule report: {str(e)}")
    
    async def process_scheduled_reports(self) -> Dict[str, int]:
        """
        Processa relatórios agendados
        """
        try:
            processed = 0
            failed = 0
            
            # Buscar relatórios para processar
            templates = self.db.query(ExportTemplate).filter(
                and_(
                    ExportTemplate.company_id == self.company_id,
                    ExportTemplate.is_active == True,
                    ExportTemplate.next_run <= datetime.utcnow()
                )
            ).all()
            
            for template in templates:
                try:
                    # Gerar relatório
                    params = json.loads(template.parameters)
                    
                    # Calcular período baseado no schedule
                    end_date = datetime.utcnow()
                    if template.schedule == "daily":
                        start_date = end_date - timedelta(days=1)
                    elif template.schedule == "weekly":
                        start_date = end_date - timedelta(days=7)
                    elif template.schedule == "monthly":
                        start_date = end_date - timedelta(days=30)
                    else:
                        start_date = end_date - timedelta(days=1)
                    
                    # Gerar relatório
                    result = await self.generate_report(
                        report_type=ReportType(template.report_type),
                        format=ExportFormat(template.format),
                        start_date=start_date,
                        end_date=end_date,
                        filters=params.get("filters"),
                        async_generation=False
                    )
                    
                    # Enviar para recipients
                    recipients = json.loads(template.recipients)
                    await self._send_report_to_recipients(result, recipients, template.name)
                    
                    # Atualizar próxima execução
                    template.next_run = self._calculate_next_run(template.schedule)
                    template.last_run = datetime.utcnow()
                    processed += 1
                    
                except Exception as e:
                    logger.error(f"Error processing scheduled report {template.id}: {str(e)}")
                    failed += 1
            
            self.db.commit()
            
            return {
                "processed": processed,
                "failed": failed,
                "total": len(templates)
            }
            
        except Exception as e:
            logger.error(f"Error processing scheduled reports: {str(e)}")
            raise ExportError(f"Failed to process scheduled reports: {str(e)}")
    
    async def get_export_history(
        self,
        limit: int = 50,
        include_failed: bool = False
    ) -> List[Dict]:
        """
        Obtém histórico de exportações
        """
        try:
            query = self.db.query(ExportJob).filter(
                ExportJob.company_id == self.company_id
            )
            
            if not include_failed:
                query = query.filter(ExportJob.status != "failed")
            
            jobs = query.order_by(
                ExportJob.created_at.desc()
            ).limit(limit).all()
            
            return [
                {
                    "id": job.id,
                    "report_type": job.report_type,
                    "format": job.format,
                    "status": job.status,
                    "file_path": job.file_path,
                    "file_size": job.file_size,
                    "created_at": job.created_at.isoformat(),
                    "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                    "parameters": json.loads(job.parameters) if job.parameters else None
                }
                for job in jobs
            ]
            
        except Exception as e:
            logger.error(f"Error getting export history: {str(e)}")
            raise ExportError(f"Failed to get export history: {str(e)}")
    
    # Métodos auxiliares privados
    
    async def _process_report_async(self, job: ExportJob):
        """Processa geração de relatório em background"""
        try:
            params = json.loads(job.parameters)
            
            result = await self._generate_report_content(
                job,
                ReportType(job.report_type),
                ExportFormat(job.format),
                datetime.fromisoformat(params["start_date"]),
                datetime.fromisoformat(params["end_date"]),
                params.get("filters"),
                params.get("template_id"),
                params.get("include_charts", True)
            )
            
            job.status = "completed"
            job.file_path = result["file_path"]
            job.file_size = result["file_size"]
            job.completed_at = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Error in async report generation: {str(e)}")
            job.status = "failed"
            job.error_message = str(e)
        
        finally:
            self.db.commit()
    
    async def _generate_report_content(
        self,
        job: ExportJob,
        report_type: ReportType,
        format: ExportFormat,
        start_date: datetime,
        end_date: datetime,
        filters: Optional[Dict],
        template_id: Optional[str],
        include_charts: bool
    ) -> Dict[str, Any]:
        """Gera conteúdo do relatório"""
        
        # Coletar dados baseado no tipo de relatório
        data = await self._collect_report_data(
            report_type,
            start_date,
            end_date,
            filters
        )
        
        # Adicionar metadados
        data["start_date"] = start_date.isoformat()
        data["end_date"] = end_date.isoformat()
        data["generated_at"] = datetime.utcnow().isoformat()
        
        # Gerar charts se necessário
        if include_charts:
            data["charts"] = await self._generate_charts(data)
            data["charts_data"] = await self._prepare_charts_data(data)
        
        # Gerar arquivo no formato especificado
        if format == ExportFormat.PDF:
            content = await self.generate_pdf(data)
            extension = "pdf"
            mime_type = "application/pdf"
        elif format == ExportFormat.EXCEL:
            content = await self.generate_excel(data, include_charts)
            extension = "xlsx"
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif format == ExportFormat.CSV:
            content = await self.generate_csv(data)
            extension = "csv"
            mime_type = "text/csv"
        elif format == ExportFormat.JSON:
            content = json.dumps(data, indent=2, default=str).encode('utf-8')
            extension = "json"
            mime_type = "application/json"
        else:
            raise ValidationError(f"Unsupported format: {format}")
        
        # Salvar arquivo
        filename = f"{report_type.value}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.{extension}"
        file_path = self.export_path / filename
        
        with open(file_path, 'wb') as f:
            f.write(content)
        
        # Gerar URL de download
        file_url = f"/api/v1/exports/download/{job.id}"
        
        return {
            "file_path": str(file_path),
            "file_url": file_url,
            "file_size": len(content),
            "mime_type": mime_type
        }
    
    async def _collect_report_data(
        self,
        report_type: ReportType,
        start_date: datetime,
        end_date: datetime,
        filters: Optional[Dict]
    ) -> Dict[str, Any]:
        """Coleta dados para o relatório"""
        
        data = {}
        
        # Dados comuns a todos os relatórios
        company_name = await self._get_company_name()
        data["company_name"] = company_name
        
        if report_type == ReportType.EXECUTIVE_SUMMARY:
            # Resumo executivo com todos os principais indicadores
            
            # KPIs de vendas
            sales_metrics = await self.sales_service.get_sales_metrics(
                start_date, end_date
            )
            
            # Análise de impacto climático
            weather_impact = await self.sales_service.analyze_weather_impact(
                start_date, end_date
            )
            
            # Previsões
            predictions = await self.ml_service.predict_sales(
                datetime.utcnow(),
                datetime.utcnow() + timedelta(days=7)
            )
            
            data["executive_summary"] = {
                "total_revenue": sales_metrics.total_revenue,
                "average_daily_revenue": sales_metrics.average_daily_revenue,
                "growth_rate": sales_metrics.growth_rate,
                "weather_correlation": weather_impact["correlations"],
                "most_impactful_factor": weather_impact["most_impactful_variable"],
                "next_week_forecast": predictions.summary["total_predicted"],
                "recommendations": weather_impact["recommendations"]
            }
            
            # Dados detalhados
            data["sales_data"] = await self._get_sales_data(start_date, end_date)
            data["weather_data"] = await self._get_weather_data(start_date, end_date)
            data["correlations"] = weather_impact["correlations"]
            data["predictions"] = predictions.predictions
            
        elif report_type == ReportType.SALES_ANALYSIS:
            # Análise detalhada de vendas
            
            sales_metrics = await self.sales_service.get_sales_metrics(
                start_date, end_date
            )
            
            patterns = await self.sales_service.calculate_patterns()
            anomalies = await self.sales_service.detect_anomalies()
            
            data["sales_analysis"] = {
                "metrics": sales_metrics.dict(),
                "patterns": patterns,
                "anomalies": anomalies
            }
            
            data["sales_data"] = await self._get_sales_data(start_date, end_date)
            
        elif report_type == ReportType.WEATHER_IMPACT:
            # Análise de impacto climático
            
            weather_impact = await self.sales_service.analyze_weather_impact(
                start_date, end_date
            )
            
            data["weather_analysis"] = weather_impact
            data["weather_data"] = await self._get_weather_data(start_date, end_date)
            data["correlations"] = weather_impact["correlations"]
            
        elif report_type == ReportType.PREDICTIONS:
            # Relatório de previsões
            
            predictions = await self.ml_service.predict_sales(
                start_date, end_date
            )
            
            model_performance = await self.ml_service.get_model_performance(
                "sales_prediction"
            )
            
            data["predictions"] = predictions.predictions
            data["prediction_summary"] = predictions.summary
            data["model_performance"] = model_performance
            
        elif report_type == ReportType.ALERTS_SUMMARY:
            # Resumo de alertas
            
            alerts = await self._get_alerts_summary(start_date, end_date)
            data["alerts_summary"] = alerts
            
        return data
    
    def _get_pdf_styles(self) -> Dict:
        """Retorna estilos para PDF"""
        styles = getSampleStyleSheet()
        
        # Customizar estilos
        styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2E4057'),
            spaceAfter=30,
            alignment=TA_CENTER
        ))
        
        styles.add(ParagraphStyle(
            name='SectionTitle',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#4472C4'),
            spaceAfter=12,
            spaceBefore=12
        ))
        
        return styles
    
    def _create_pdf_header(self, styles: Dict, data: Dict) -> List:
        """Cria cabeçalho do PDF"""
        elements = []
        
        # Título
        title = Paragraph(
            f"<b>{data.get('company_name', 'Empresa')}</b><br/>Relatório de Análise Climática e Vendas",
            styles['CustomTitle']
        )
        elements.append(title)
        
        # Período
        period = Paragraph(
            f"Período: {data.get('start_date', 'N/A')} até {data.get('end_date', 'N/A')}",
            styles['Normal']
        )
        elements.append(period)
        
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _create_executive_summary(self, styles: Dict, summary: Dict) -> List:
        """Cria seção de sumário executivo"""
        elements = []
        
        elements.append(Paragraph("Sumário Executivo", styles['SectionTitle']))
        
        # Tabela de KPIs
        kpi_data = [
            ['Indicador', 'Valor'],
            ['Receita Total', f"R$ {summary.get('total_revenue', 0):,.2f}"],
            ['Média Diária', f"R$ {summary.get('average_daily_revenue', 0):,.2f}"],
            ['Taxa de Crescimento', f"{summary.get('growth_rate', 0):.1f}%"],
            ['Previsão Próxima Semana', f"R$ {summary.get('next_week_forecast', 0):,.2f}"]
        ]
        
        kpi_table = Table(kpi_data, colWidths=[3*inch, 2*inch])
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(kpi_table)
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _create_sales_section(self, styles: Dict, sales_data: Dict) -> List:
        """Cria seção de análise de vendas"""
        elements = []
        
        elements.append(Paragraph("Análise de Vendas", styles['SectionTitle']))
        
        # Adicionar texto descritivo
        if "patterns" in sales_data:
            patterns_text = "Padrões identificados:<br/>"
            for pattern_type, pattern_data in sales_data["patterns"].items():
                patterns_text += f"- {pattern_type}: {pattern_data}<br/>"
            
            elements.append(Paragraph(patterns_text, styles['Normal']))
        
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _create_weather_section(self, styles: Dict, weather_data: Dict) -> List:
        """Cria seção de análise climática"""
        elements = []
        
        elements.append(Paragraph("Análise de Impacto Climático", styles['SectionTitle']))
        
        # Correlações
        if "correlations" in weather_data:
            corr_data = [['Variável Climática', 'Correlação', 'Impacto']]
            
            for var, corr_info in weather_data["correlations"].items():
                corr_data.append([
                    var.replace('_', ' ').title(),
                    f"{corr_info.get('correlation', 0):.3f}",
                    corr_info.get('strength', 'N/A')
                ])
            
            corr_table = Table(corr_data, colWidths=[2*inch, 1.5*inch, 1.5*inch])
            corr_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            elements.append(corr_table)
        
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _create_predictions_section(self, styles: Dict, predictions: List[Dict]) -> List:
        """Cria seção de previsões"""
        elements = []
        
        elements.append(Paragraph("Previsões", styles['SectionTitle']))
        
        # Tabela de previsões
        pred_data = [['Data', 'Previsão', 'Intervalo de Confiança']]
        
        for pred in predictions[:7]:  # Primeiros 7 dias
            pred_data.append([
                pred["date"][:10],
                f"R$ {pred['predicted_sales']:,.2f}",
                f"R$ {pred['confidence_interval']['lower']:,.0f} - {pred['confidence_interval']['upper']:,.0f}"
            ])
        
        pred_table = Table(pred_data, colWidths=[1.5*inch, 1.5*inch, 2*inch])
        pred_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(pred_table)
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _create_charts_section(self, charts: List[Any]) -> List:
        """Cria seção de gráficos"""
        elements = []
        
        for chart_path in charts:
            if os.path.exists(chart_path):
                img = Image(chart_path, width=6*inch, height=4*inch)
                elements.append(KeepTogether([img, Spacer(1, 12)]))
        
        return elements
    
    def _create_recommendations_section(self, styles: Dict, recommendations: List[str]) -> List:
        """Cria seção de recomendações"""
        elements = []
        
        elements.append(Paragraph("Recomendações", styles['SectionTitle']))
        
        for i, rec in enumerate(recommendations, 1):
            elements.append(Paragraph(f"{i}. {rec}", styles['Normal']))
        
        return elements
    
    def _add_page_number(self, canvas, doc):
        """Adiciona número de página"""
        canvas.saveState()
        canvas.setFont('Helvetica', 9)
        page_num = canvas.getPageNumber()
        text = f"Página {page_num}"
        canvas.drawRightString(200*mm, 10*mm, text)
        canvas.restoreState()
    
    async def _generate_charts(self, data: Dict) -> List[str]:
        """Gera gráficos para o relatório"""
        charts = []
        
        try:
            # Configurar estilo
            plt.style.use('seaborn-v0_8-darkgrid')
            
            # Gráfico 1: Vendas ao longo do tempo
            if "sales_data" in data:
                fig, ax = plt.subplots(figsize=(10, 6))
                
                df_sales = pd.DataFrame(data["sales_data"])
                if not df_sales.empty and 'date' in df_sales.columns and 'revenue' in df_sales.columns:
                    df_sales['date'] = pd.to_datetime(df_sales['date'])
                    df_sales.plot(x='date', y='revenue', ax=ax, kind='line', marker='o')
                    
                    ax.set_title('Evolução das Vendas', fontsize=16)
                    ax.set_xlabel('Data')
                    ax.set_ylabel('Receita (R$)')
                    ax.grid(True, alpha=0.3)
                    
                    chart_path = self.export_path / f"sales_chart_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
                    plt.savefig(chart_path, dpi=300, bbox_inches='tight')
                    charts.append(str(chart_path))
                    plt.close()
            
            # Gráfico 2: Correlação clima vs vendas
            if "correlations" in data:
                fig, ax = plt.subplots(figsize=(10, 6))
                
                corr_data = data["correlations"]
                if corr_data:
                    variables = list(corr_data.keys())
                    correlations = [corr_data[v].get('correlation', 0) for v in variables]
                    
                    bars = ax.bar(variables, correlations)
                    
                    # Colorir barras baseado no valor
                    for bar, corr in zip(bars, correlations):
                        if corr > 0:
                            bar.set_color('green')
                        else:
                            bar.set_color('red')
                    
                    ax.set_title('Correlação entre Variáveis Climáticas e Vendas', fontsize=16)
                    ax.set_xlabel('Variável Climática')
                    ax.set_ylabel('Correlação')
                    ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
                    ax.grid(True, alpha=0.3)
                    
                    chart_path = self.export_path / f"correlation_chart_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
                    plt.savefig(chart_path, dpi=300, bbox_inches='tight')
                    charts.append(str(chart_path))
                    plt.close()
            
            # Gráfico 3: Previsões
            if "predictions" in data:
                fig, ax = plt.subplots(figsize=(10, 6))
                
                pred_data = data["predictions"][:14]  # 2 semanas
                if pred_data:
                    dates = [p['date'][:10] for p in pred_data]
                    values = [p['predicted_sales'] for p in pred_data]
                    lower = [p['confidence_interval']['lower'] for p in pred_data]
                    upper = [p['confidence_interval']['upper'] for p in pred_data]
                    
                    ax.plot(dates, values, 'b-', label='Previsão', linewidth=2)
                    ax.fill_between(range(len(dates)), lower, upper, alpha=0.3, label='Intervalo de Confiança')
                    
                    ax.set_title('Previsão de Vendas - Próximas 2 Semanas', fontsize=16)
                    ax.set_xlabel('Data')
                    ax.set_ylabel('Vendas Previstas (R$)')
                    ax.legend()
                    ax.grid(True, alpha=0.3)
                    
                    # Rotacionar labels do eixo X
                    plt.xticks(rotation=45)
                    
                    chart_path = self.export_path / f"prediction_chart_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
                    plt.savefig(chart_path, dpi=300, bbox_inches='tight')
                    charts.append(str(chart_path))
                    plt.close()
            
        except Exception as e:
            logger.error(f"Error generating charts: {str(e)}")
        
        return charts
    
    async def _prepare_charts_data(self, data: Dict) -> Dict:
        """Prepara dados para gráficos no Excel"""
        charts_data = {}
        
        if "sales_data" in data:
            df_sales = pd.DataFrame(data["sales_data"])
            if not df_sales.empty:
                charts_data["sales_chart"] = {
                    "type": "line",
                    "data": df_sales.to_dict('records'),
                    "x_column": "date",
                    "y_column": "revenue",
                    "title": "Evolução das Vendas"
                }
        
        if "correlations" in data:
            corr_data = data["correlations"]
            if corr_data:
                charts_data["correlation_chart"] = {
                    "type": "bar",
                    "data": [
                        {"variable": k, "correlation": v.get("correlation", 0)}
                        for k, v in corr_data.items()
                    ],
                    "x_column": "variable",
                    "y_column": "correlation",
                    "title": "Correlações Clima vs Vendas"
                }
        
        return charts_data
    
    def _add_excel_charts(self, workbook, writer, charts_data: Dict):
        """Adiciona gráficos ao Excel"""
        
        for chart_name, chart_config in charts_data.items():
            # Criar worksheet para gráfico
            worksheet = workbook.add_worksheet(f'Gráfico_{chart_name[:20]}')
            
            if chart_config["type"] == "line":
                chart = workbook.add_chart({'type': 'line'})
            elif chart_config["type"] == "bar":
                chart = workbook.add_chart({'type': 'column'})
            else:
                continue
            
            # Configurar gráfico
            chart.set_title({'name': chart_config["title"]})
            chart.set_size({'width': 720, 'height': 480})
            
            # Adicionar ao worksheet
            worksheet.insert_chart('B2', chart)
    
    def _flatten_data_for_csv(self, data: Dict) -> pd.DataFrame:
        """Achata dados nested para CSV"""
        
        flat_data = []
        
        # Extrair dados de vendas
        if "sales_data" in data:
            for record in data["sales_data"]:
                flat_record = {"type": "sales"}
                flat_record.update(record)
                flat_data.append(flat_record)
        
        # Extrair dados climáticos
        if "weather_data" in data:
            for record in data["weather_data"]:
                flat_record = {"type": "weather"}
                flat_record.update(record)
                flat_data.append(flat_record)
        
        if not flat_data:
            # Retornar DataFrame vazio se não houver dados
            return pd.DataFrame()
        
        return pd.DataFrame(flat_data)
    
    def _estimate_generation_time(self, report_type: ReportType) -> int:
        """Estima tempo de geração em segundos"""
        estimates = {
            ReportType.EXECUTIVE_SUMMARY: 30,
            ReportType.SALES_ANALYSIS: 20,
            ReportType.WEATHER_IMPACT: 25,
            ReportType.PREDICTIONS: 15,
            ReportType.ALERTS_SUMMARY: 10,
            ReportType.CUSTOM: 40
        }
        
        return estimates.get(report_type, 30)
    
    def _calculate_next_run(self, schedule: str) -> datetime:
        """Calcula próxima execução baseado no schedule"""
        now = datetime.utcnow()
        
        if schedule == "daily":
            # Próximo dia às 8h
            next_run = now.replace(hour=8, minute=0, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
        
        elif schedule == "weekly":
            # Próxima segunda-feira às 8h
            days_until_monday = (7 - now.weekday()) % 7
            if days_until_monday == 0 and now.hour >= 8:
                days_until_monday = 7
            next_run = now + timedelta(days=days_until_monday)
            next_run = next_run.replace(hour=8, minute=0, second=0, microsecond=0)
        
        elif schedule == "monthly":
            # Primeiro dia do próximo mês às 8h
            if now.month == 12:
                next_run = now.replace(year=now.year + 1, month=1, day=1, 
                                      hour=8, minute=0, second=0, microsecond=0)
            else:
                next_run = now.replace(month=now.month + 1, day=1,
                                      hour=8, minute=0, second=0, microsecond=0)
        
        else:
            # Default: amanhã às 8h
            next_run = now + timedelta(days=1)
            next_run = next_run.replace(hour=8, minute=0, second=0, microsecond=0)
        
        return next_run
    
    async def _send_report_to_recipients(
        self,
        report: ExportResponse,
        recipients: List[str],
        report_name: str
    ):
        """Envia relatório para lista de destinatários"""
        
        # Importar NotificationService para evitar circular import
        from .notification_service import NotificationService
        
        notification_service = NotificationService(self.db, self.company_id)
        
        # Ler arquivo do relatório
        with open(report.file_path, 'rb') as f:
            file_content = f.read()
        
        # Enviar email com anexo
        await notification_service.send_email(
            recipients=recipients,
            subject=f"Relatório Agendado: {report_name}",
            body=f"Segue anexo o relatório {report_name} gerado em {datetime.utcnow().strftime('%d/%m/%Y %H:%M')}",
            attachments=[{
                "content": file_content,
                "filename": os.path.basename(report.file_path)
            }]
        )
    
    async def _get_company_name(self) -> str:
        """Obtém nome da empresa"""
        company = self.db.query(Company).filter(
            Company.id == self.company_id
        ).first()
        
        return company.name if company else "Empresa"
    
    async def _get_sales_data(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict]:
        """Obtém dados de vendas"""
        
        sales = self.db.query(SalesData).filter(
            and_(
                SalesData.company_id == self.company_id,
                SalesData.date >= start_date.date(),
                SalesData.date <= end_date.date()
            )
        ).order_by(SalesData.date).all()
        
        return [
            {
                "date": s.date.isoformat(),
                "revenue": float(s.revenue),
                "quantity": int(s.quantity),
                "product": s.product_id
            }
            for s in sales
        ]
    
    async def _get_weather_data(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict]:
        """Obtém dados climáticos"""
        
        weather = self.db.query(WeatherData).filter(
            and_(
                WeatherData.company_id == self.company_id,
                WeatherData.date >= start_date.date(),
                WeatherData.date <= end_date.date()
            )
        ).order_by(WeatherData.date).all()
        
        return [
            {
                "date": w.date.isoformat(),
                "temperature": float(w.temperature),
                "precipitation": float(w.precipitation),
                "humidity": float(w.humidity),
                "wind_speed": float(w.wind_speed)
            }
            for w in weather
        ]
    
    async def _get_alerts_summary(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Obtém resumo de alertas"""
        
        alerts = self.db.query(Alert).filter(
            and_(
                Alert.company_id == self.company_id,
                Alert.triggered_at >= start_date,
                Alert.triggered_at <= end_date
            )
        ).all()
        
        # Agrupar por tipo e prioridade
        summary = {
            "total": len(alerts),
            "by_type": {},
            "by_priority": {},
            "resolved": len([a for a in alerts if a.resolved_at]),
            "pending": len([a for a in alerts if not a.resolved_at])
        }
        
        for alert in alerts:
            # Por tipo
            if alert.alert_type not in summary["by_type"]:
                summary["by_type"][alert.alert_type] = 0
            summary["by_type"][alert.alert_type] += 1
            
            # Por prioridade
            if alert.priority not in summary["by_priority"]:
                summary["by_priority"][alert.priority] = 0
            summary["by_priority"][alert.priority] += 1
        
        return summary