# Sistema de alertas/notificações
# backend/app/services/alert_service.py

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import json
import asyncio
from enum import Enum
from ..models.database import Alert, AlertRule, AlertHistory, Company, WeatherData, SalesData
from ..models.schemas import AlertConfig, AlertTrigger, AlertResponse
from ..core.exceptions import AlertError, ValidationError
from ..services.notification_service import NotificationService
import logging
from dataclasses import dataclass
import re

logger = logging.getLogger(__name__)

class AlertType(Enum):
    WEATHER_EXTREME = "weather_extreme"
    SALES_ANOMALY = "sales_anomaly"
    IMPACT_PREDICTION = "impact_prediction"
    OPERATIONAL = "operational"
    CUSTOM = "custom"

class AlertPriority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AlertChannel(Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    INTERNAL = "internal"
    SMS = "sms"
    SLACK = "slack"

@dataclass
class AlertCondition:
    """Representa uma condição para disparo de alerta"""
    field: str
    operator: str  # >, <, ==, !=, contains, between
    value: Any
    value2: Optional[Any] = None  # Para operador 'between'

class AlertService:
    """Service para gerenciamento de alertas automáticos"""
    
    def __init__(self, db: Session, company_id: str):
        self.db = db
        self.company_id = company_id
        self.notification_service = NotificationService(db, company_id)
        self.cooldown_cache = {}  # Cache para cooldown de alertas
        
    async def create_alert_rule(
        self,
        name: str,
        alert_type: AlertType,
        conditions: List[Dict],
        channels: List[AlertChannel],
        priority: AlertPriority = AlertPriority.MEDIUM,
        message_template: Optional[str] = None,
        cooldown_minutes: int = 60,
        is_active: bool = True,
        metadata: Optional[Dict] = None
    ) -> AlertRule:
        """
        Cria nova regra de alerta
        """
        try:
            # Validar condições
            validated_conditions = self._validate_conditions(conditions)
            
            # Validar template de mensagem
            if message_template:
                self._validate_message_template(message_template)
            
            # Criar regra
            rule = AlertRule(
                company_id=self.company_id,
                name=name,
                alert_type=alert_type.value,
                conditions=json.dumps(validated_conditions),
                channels=json.dumps([c.value for c in channels]),
                priority=priority.value,
                message_template=message_template or self._get_default_template(alert_type),
                cooldown_minutes=cooldown_minutes,
                is_active=is_active,
                metadata=json.dumps(metadata) if metadata else None,
                created_at=datetime.utcnow()
            )
            
            self.db.add(rule)
            self.db.commit()
            
            logger.info(f"Alert rule created: {name} for company {self.company_id}")
            
            return rule
            
        except Exception as e:
            logger.error(f"Error creating alert rule: {str(e)}")
            self.db.rollback()
            raise AlertError(f"Failed to create alert rule: {str(e)}")
    
    async def check_and_trigger_alerts(self) -> List[AlertResponse]:
        """
        Verifica todas as regras ativas e dispara alertas necessários
        """
        try:
            triggered_alerts = []
            
            # Buscar regras ativas
            rules = self.db.query(AlertRule).filter(
                and_(
                    AlertRule.company_id == self.company_id,
                    AlertRule.is_active == True
                )
            ).all()
            
            for rule in rules:
                # Verificar cooldown
                if self._is_in_cooldown(rule.id):
                    logger.debug(f"Rule {rule.name} in cooldown, skipping")
                    continue
                
                # Verificar condições
                should_trigger, context = await self._evaluate_rule(rule)
                
                if should_trigger:
                    # Disparar alerta
                    alert_response = await self._trigger_alert(rule, context)
                    triggered_alerts.append(alert_response)
                    
                    # Atualizar cooldown
                    self._set_cooldown(rule.id, rule.cooldown_minutes)
            
            return triggered_alerts
            
        except Exception as e:
            logger.error(f"Error checking alerts: {str(e)}")
            raise AlertError(f"Failed to check alerts: {str(e)}")
    
    async def trigger_manual_alert(
        self,
        title: str,
        message: str,
        channels: List[AlertChannel],
        priority: AlertPriority = AlertPriority.MEDIUM,
        data: Optional[Dict] = None
    ) -> AlertResponse:
        """
        Dispara alerta manual imediato
        """
        try:
            # Criar alerta
            alert = Alert(
                company_id=self.company_id,
                alert_type=AlertType.CUSTOM.value,
                title=title,
                message=message,
                priority=priority.value,
                data=json.dumps(data) if data else None,
                triggered_at=datetime.utcnow(),
                is_manual=True
            )
            
            self.db.add(alert)
            self.db.commit()
            
            # Enviar para canais especificados
            delivery_status = {}
            for channel in channels:
                success = await self._send_to_channel(
                    channel,
                    alert,
                    {"title": title, "message": message}
                )
                delivery_status[channel.value] = success
            
            # Registrar no histórico
            history = AlertHistory(
                company_id=self.company_id,
                alert_id=alert.id,
                rule_id=None,
                channels_notified=json.dumps([c.value for c in channels]),
                delivery_status=json.dumps(delivery_status),
                created_at=datetime.utcnow()
            )
            
            self.db.add(history)
            self.db.commit()
            
            return AlertResponse(
                alert_id=alert.id,
                title=title,
                message=message,
                priority=priority.value,
                channels_notified=[c.value for c in channels],
                delivery_status=delivery_status,
                triggered_at=alert.triggered_at.isoformat()
            )
            
        except Exception as e:
            logger.error(f"Error triggering manual alert: {str(e)}")
            self.db.rollback()
            raise AlertError(f"Failed to trigger manual alert: {str(e)}")
    
    async def get_alert_history(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        alert_type: Optional[AlertType] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Obtém histórico de alertas disparados
        """
        try:
            query = self.db.query(AlertHistory).filter(
                AlertHistory.company_id == self.company_id
            )
            
            if start_date:
                query = query.filter(AlertHistory.created_at >= start_date)
            if end_date:
                query = query.filter(AlertHistory.created_at <= end_date)
            
            if alert_type:
                # Join com Alert para filtrar por tipo
                query = query.join(Alert).filter(Alert.alert_type == alert_type.value)
            
            history = query.order_by(
                AlertHistory.created_at.desc()
            ).limit(limit).all()
            
            # Formatar resposta
            formatted_history = []
            for h in history:
                alert = self.db.query(Alert).filter(Alert.id == h.alert_id).first()
                rule = None
                if h.rule_id:
                    rule = self.db.query(AlertRule).filter(AlertRule.id == h.rule_id).first()
                
                formatted_history.append({
                    'id': h.id,
                    'alert': {
                        'id': alert.id,
                        'type': alert.alert_type,
                        'title': alert.title,
                        'message': alert.message,
                        'priority': alert.priority
                    },
                    'rule': {
                        'id': rule.id,
                        'name': rule.name
                    } if rule else None,
                    'channels_notified': json.loads(h.channels_notified),
                    'delivery_status': json.loads(h.delivery_status),
                    'created_at': h.created_at.isoformat()
                })
            
            return formatted_history
            
        except Exception as e:
            logger.error(f"Error getting alert history: {str(e)}")
            raise AlertError(f"Failed to get alert history: {str(e)}")
    
    async def update_alert_rule(
        self,
        rule_id: str,
        **updates
    ) -> AlertRule:
        """
        Atualiza regra de alerta existente
        """
        try:
            rule = self.db.query(AlertRule).filter(
                and_(
                    AlertRule.id == rule_id,
                    AlertRule.company_id == self.company_id
                )
            ).first()
            
            if not rule:
                raise ValidationError(f"Alert rule {rule_id} not found")
            
            # Atualizar campos permitidos
            allowed_fields = [
                'name', 'conditions', 'channels', 'priority',
                'message_template', 'cooldown_minutes', 'is_active'
            ]
            
            for field, value in updates.items():
                if field in allowed_fields:
                    if field == 'conditions':
                        value = json.dumps(self._validate_conditions(value))
                    elif field == 'channels':
                        value = json.dumps([c.value if isinstance(c, AlertChannel) else c for c in value])
                    elif field == 'priority' and isinstance(value, AlertPriority):
                        value = value.value
                    
                    setattr(rule, field, value)
            
            rule.updated_at = datetime.utcnow()
            self.db.commit()
            
            logger.info(f"Alert rule {rule_id} updated")
            
            return rule
            
        except Exception as e:
            logger.error(f"Error updating alert rule: {str(e)}")
            self.db.rollback()
            raise AlertError(f"Failed to update alert rule: {str(e)}")
    
    async def delete_alert_rule(self, rule_id: str) -> bool:
        """
        Deleta regra de alerta (soft delete)
        """
        try:
            rule = self.db.query(AlertRule).filter(
                and_(
                    AlertRule.id == rule_id,
                    AlertRule.company_id == self.company_id
                )
            ).first()
            
            if not rule:
                raise ValidationError(f"Alert rule {rule_id} not found")
            
            # Soft delete - apenas desativa
            rule.is_active = False
            rule.deleted_at = datetime.utcnow()
            self.db.commit()
            
            logger.info(f"Alert rule {rule_id} deleted")
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting alert rule: {str(e)}")
            self.db.rollback()
            raise AlertError(f"Failed to delete alert rule: {str(e)}")
    
    async def get_active_alerts(self) -> List[Dict]:
        """
        Obtém alertas ativos (não resolvidos)
        """
        try:
            # Alertas das últimas 24 horas que ainda estão ativos
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
            
            alerts = self.db.query(Alert).filter(
                and_(
                    Alert.company_id == self.company_id,
                    Alert.triggered_at >= cutoff_time,
                    or_(
                        Alert.resolved_at.is_(None),
                        Alert.resolved_at > datetime.utcnow()
                    )
                )
            ).order_by(Alert.priority.desc(), Alert.triggered_at.desc()).all()
            
            return [
                {
                    'id': a.id,
                    'type': a.alert_type,
                    'title': a.title,
                    'message': a.message,
                    'priority': a.priority,
                    'triggered_at': a.triggered_at.isoformat(),
                    'data': json.loads(a.data) if a.data else None
                }
                for a in alerts
            ]
            
        except Exception as e:
            logger.error(f"Error getting active alerts: {str(e)}")
            raise AlertError(f"Failed to get active alerts: {str(e)}")
    
    async def resolve_alert(
        self,
        alert_id: str,
        resolution_note: Optional[str] = None
    ) -> bool:
        """
        Marca alerta como resolvido
        """
        try:
            alert = self.db.query(Alert).filter(
                and_(
                    Alert.id == alert_id,
                    Alert.company_id == self.company_id
                )
            ).first()
            
            if not alert:
                raise ValidationError(f"Alert {alert_id} not found")
            
            alert.resolved_at = datetime.utcnow()
            if resolution_note:
                current_data = json.loads(alert.data) if alert.data else {}
                current_data['resolution_note'] = resolution_note
                alert.data = json.dumps(current_data)
            
            self.db.commit()
            
            logger.info(f"Alert {alert_id} resolved")
            
            return True
            
        except Exception as e:
            logger.error(f"Error resolving alert: {str(e)}")
            self.db.rollback()
            raise AlertError(f"Failed to resolve alert: {str(e)}")
    
    async def test_alert_rule(
        self,
        rule_id: str,
        test_data: Optional[Dict] = None
    ) -> Dict:
        """
        Testa regra de alerta sem disparar notificações reais
        """
        try:
            rule = self.db.query(AlertRule).filter(
                and_(
                    AlertRule.id == rule_id,
                    AlertRule.company_id == self.company_id
                )
            ).first()
            
            if not rule:
                raise ValidationError(f"Alert rule {rule_id} not found")
            
            # Avaliar regra com dados de teste
            if test_data:
                # Usar dados de teste fornecidos
                should_trigger = self._evaluate_conditions_with_data(
                    json.loads(rule.conditions),
                    test_data
                )
                context = test_data
            else:
                # Usar dados reais atuais
                should_trigger, context = await self._evaluate_rule(rule)
            
            # Gerar mensagem de teste
            message = self._format_message(rule.message_template, context)
            
            return {
                'rule_name': rule.name,
                'would_trigger': should_trigger,
                'test_message': message,
                'channels': json.loads(rule.channels),
                'priority': rule.priority,
                'context_data': context
            }
            
        except Exception as e:
            logger.error(f"Error testing alert rule: {str(e)}")
            raise AlertError(f"Failed to test alert rule: {str(e)}")
    
    # Métodos auxiliares privados
    
    def _validate_conditions(self, conditions: List[Dict]) -> List[Dict]:
        """Valida estrutura das condições"""
        validated = []
        
        for condition in conditions:
            if not all(k in condition for k in ['field', 'operator', 'value']):
                raise ValidationError("Invalid condition structure")
            
            # Validar operador
            valid_operators = ['>', '<', '>=', '<=', '==', '!=', 'contains', 'between', 'in', 'not_in']
            if condition['operator'] not in valid_operators:
                raise ValidationError(f"Invalid operator: {condition['operator']}")
            
            # Validar value2 para operador between
            if condition['operator'] == 'between' and 'value2' not in condition:
                raise ValidationError("Operator 'between' requires 'value2'")
            
            validated.append(condition)
        
        return validated
    
    def _validate_message_template(self, template: str) -> bool:
        """Valida template de mensagem"""
        # Verificar placeholders válidos
        valid_placeholders = [
            '{alert_type}', '{priority}', '{value}', '{threshold}',
            '{company_name}', '{timestamp}', '{location}', '{product}'
        ]
        
        # Extrair placeholders do template
        placeholders = re.findall(r'\{(\w+)\}', template)
        
        # Verificar se todos são válidos
        for placeholder in placeholders:
            if f"{{{placeholder}}}" not in valid_placeholders:
                logger.warning(f"Unknown placeholder in template: {{{placeholder}}}")
        
        return True
    
    def _get_default_template(self, alert_type: AlertType) -> str:
        """Retorna template padrão para tipo de alerta"""
        templates = {
            AlertType.WEATHER_EXTREME: "⚠️ Alerta Climático: {alert_type}\nCondições extremas detectadas.\nValor: {value}\nLocal: {location}",
            AlertType.SALES_ANOMALY: "📊 Anomalia nas Vendas\nDesvio significativo detectado.\nValor: {value}\nVariação: {threshold}%",
            AlertType.IMPACT_PREDICTION: "🔮 Previsão de Impacto\nImpacto previsto: {value}%\nPeríodo: {timestamp}",
            AlertType.OPERATIONAL: "⚙️ Alerta Operacional\n{alert_type}\nAção requerida: {value}",
            AlertType.CUSTOM: "📢 Alerta: {alert_type}\n{value}"
        }
        
        return templates.get(alert_type, "Alerta: {alert_type}")
    
    def _is_in_cooldown(self, rule_id: str) -> bool:
        """Verifica se regra está em período de cooldown"""
        if rule_id not in self.cooldown_cache:
            return False
        
        cooldown_until = self.cooldown_cache[rule_id]
        if datetime.utcnow() < cooldown_until:
            return True
        
        # Limpar cache expirado
        del self.cooldown_cache[rule_id]
        return False
    
    def _set_cooldown(self, rule_id: str, minutes: int):
        """Define período de cooldown para regra"""
        self.cooldown_cache[rule_id] = datetime.utcnow() + timedelta(minutes=minutes)
    
    async def _evaluate_rule(self, rule: AlertRule) -> tuple[bool, Dict]:
        """Avalia se regra deve ser disparada"""
        conditions = json.loads(rule.conditions)
        alert_type = AlertType(rule.alert_type)
        
        # Buscar dados relevantes baseado no tipo de alerta
        context = {}
        
        if alert_type == AlertType.WEATHER_EXTREME:
            # Buscar dados climáticos atuais
            weather = self.db.query(WeatherData).filter(
                and_(
                    WeatherData.company_id == self.company_id,
                    WeatherData.date == datetime.utcnow().date()
                )
            ).first()
            
            if weather:
                context = {
                    'temperature': weather.temperature,
                    'precipitation': weather.precipitation,
                    'humidity': weather.humidity,
                    'wind_speed': weather.wind_speed
                }
        
        elif alert_type == AlertType.SALES_ANOMALY:
            # Buscar dados de vendas recentes
            recent_sales = self.db.query(SalesData).filter(
                and_(
                    SalesData.company_id == self.company_id,
                    SalesData.date >= (datetime.utcnow() - timedelta(days=1)).date()
                )
            ).order_by(SalesData.date.desc()).first()
            
            if recent_sales:
                # Calcular média histórica
                avg_sales = self.db.query(
                    func.avg(SalesData.revenue)
                ).filter(
                    and_(
                        SalesData.company_id == self.company_id,
                        SalesData.date >= (datetime.utcnow() - timedelta(days=30)).date()
                    )
                ).scalar()
                
                context = {
                    'current_sales': recent_sales.revenue,
                    'average_sales': avg_sales or 0,
                    'deviation': abs(recent_sales.revenue - (avg_sales or 0)) / (avg_sales or 1) * 100
                }
        
        # Avaliar condições
        should_trigger = self._evaluate_conditions_with_data(conditions, context)
        
        return should_trigger, context
    
    def _evaluate_conditions_with_data(
        self,
        conditions: List[Dict],
        data: Dict
    ) -> bool:
        """Avalia condições com dados fornecidos"""
        
        for condition in conditions:
            field = condition['field']
            operator = condition['operator']
            value = condition['value']
            value2 = condition.get('value2')
            
            # Obter valor do campo nos dados
            field_value = data.get(field)
            
            if field_value is None:
                logger.warning(f"Field {field} not found in data")
                return False
            
            # Avaliar condição
            try:
                if operator == '>':
                    if not (field_value > value):
                        return False
                elif operator == '<':
                    if not (field_value < value):
                        return False
                elif operator == '>=':
                    if not (field_value >= value):
                        return False
                elif operator == '<=':
                    if not (field_value <= value):
                        return False
                elif operator == '==':
                    if not (field_value == value):
                        return False
                elif operator == '!=':
                    if not (field_value != value):
                        return False
                elif operator == 'contains':
                    if value not in str(field_value):
                        return False
                elif operator == 'between':
                    if not (value <= field_value <= value2):
                        return False
                elif operator == 'in':
                    if field_value not in value:
                        return False
                elif operator == 'not_in':
                    if field_value in value:
                        return False
            except Exception as e:
                logger.error(f"Error evaluating condition: {str(e)}")
                return False
        
        # Todas as condições foram atendidas
        return True
    
    async def _trigger_alert(
        self,
        rule: AlertRule,
        context: Dict
    ) -> AlertResponse:
        """Dispara alerta baseado em regra"""
        try:
            # Formatar mensagem
            message = self._format_message(rule.message_template, context)
            
            # Criar alerta
            alert = Alert(
                company_id=self.company_id,
                alert_type=rule.alert_type,
                title=rule.name,
                message=message,
                priority=rule.priority,
                data=json.dumps(context),
                triggered_at=datetime.utcnow(),
                rule_id=rule.id
            )
            
            self.db.add(alert)
            self.db.commit()
            
            # Enviar para canais configurados
            channels = json.loads(rule.channels)
            delivery_status = {}
            
            for channel_str in channels:
                channel = AlertChannel(channel_str)
                success = await self._send_to_channel(channel, alert, context)
                delivery_status[channel_str] = success
            
            # Registrar no histórico
            history = AlertHistory(
                company_id=self.company_id,
                alert_id=alert.id,
                rule_id=rule.id,
                channels_notified=rule.channels,
                delivery_status=json.dumps(delivery_status),
                created_at=datetime.utcnow()
            )
            
            self.db.add(history)
            self.db.commit()
            
            logger.info(f"Alert triggered: {rule.name} for company {self.company_id}")
            
            return AlertResponse(
                alert_id=alert.id,
                title=rule.name,
                message=message,
                priority=rule.priority,
                channels_notified=channels,
                delivery_status=delivery_status,
                triggered_at=alert.triggered_at.isoformat()
            )
            
        except Exception as e:
            logger.error(f"Error triggering alert: {str(e)}")
            self.db.rollback()
            raise AlertError(f"Failed to trigger alert: {str(e)}")
    
    def _format_message(self, template: str, context: Dict) -> str:
        """Formata mensagem com dados do contexto"""
        message = template
        
        # Adicionar contexto padrão
        context['timestamp'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M')
        context['company_name'] = self._get_company_name()
        
        # Substituir placeholders
        for key, value in context.items():
            placeholder = f"{{{key}}}"
            if placeholder in message:
                message = message.replace(placeholder, str(value))
        
        # Limpar placeholders não utilizados
        message = re.sub(r'\{[^}]+\}', '', message)
        
        return message
    
    def _get_company_name(self) -> str:
        """Obtém nome da empresa"""
        company = self.db.query(Company).filter(
            Company.id == self.company_id
        ).first()
        
        return company.name if company else "Company"
    
    async def _send_to_channel(
        self,
        channel: AlertChannel,
        alert: Alert,
        context: Dict
    ) -> bool:
        """Envia alerta para canal específico"""
        try:
            if channel == AlertChannel.EMAIL:
                # Enviar por email
                return await self.notification_service.send_email(
                    subject=alert.title,
                    body=alert.message,
                    priority=alert.priority
                )
            
            elif channel == AlertChannel.WHATSAPP:
                # Enviar por WhatsApp
                return await self.notification_service.send_whatsapp(
                    message=alert.message,
                    priority=alert.priority
                )
            
            elif channel == AlertChannel.INTERNAL:
                # Criar notificação interna
                return await self.notification_service.create_internal_notification(
                    title=alert.title,
                    message=alert.message,
                    type="alert",
                    priority=alert.priority,
                    data=context
                )
            
            elif channel == AlertChannel.SMS:
                # Enviar SMS (implementar conforme provider)
                logger.info(f"SMS alert would be sent: {alert.title}")
                return True
            
            elif channel == AlertChannel.SLACK:
                # Enviar para Slack (implementar conforme necessidade)
                logger.info(f"Slack alert would be sent: {alert.title}")
                return True
            
            else:
                logger.warning(f"Unknown channel: {channel}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending to channel {channel}: {str(e)}")
            return False