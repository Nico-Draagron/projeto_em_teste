# backend/app/services/ai_agent_service.py

import os
import json
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import httpx
import re
from dataclasses import dataclass
from enum import Enum
import logging
from ..models.database import (
    ChatHistory, ChatSession, Company, User,
    SalesData, WeatherData, Alert, MLModel
)
from ..models.schemas import ChatMessage, ChatResponse, AIInsight
from ..core.exceptions import AIServiceError, ValidationError
from ..core.config import settings
from ..services.sales_service import SalesService
from ..services.ml_service import MLService
from ..services.weather_service import WeatherService
import hashlib
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

class IntentType(Enum):
    GREETING = "greeting"
    SALES_QUERY = "sales_query"
    WEATHER_QUERY = "weather_query"
    PREDICTION = "prediction"
    CORRELATION = "correlation"
    RECOMMENDATION = "recommendation"
    CHART_REQUEST = "chart_request"
    ALERT_QUERY = "alert_query"
    GENERAL = "general"
    GOODBYE = "goodbye"

class ResponseType(Enum):
    TEXT = "text"
    CHART = "chart"
    TABLE = "table"
    MIXED = "mixed"

@dataclass
class ConversationContext:
    """Contexto da conversa para manter estado"""
    session_id: str
    user_id: str
    company_id: str
    messages_history: List[Dict]
    current_topic: Optional[str]
    data_context: Dict
    
class AIAgentService:
    """Service para agente AI com Google Gemini"""
    
    def __init__(self, db: Session, company_id: str, user_id: str):
        self.db = db
        self.company_id = company_id
        self.user_id = user_id
        
        # Configurar Gemini
        genai.configure(api_key=settings.GEMINI_API_KEY)
        
        # Modelo Gemini
        self.model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL or "gemini-pro",
            generation_config={
                "temperature": 0.7,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 2048,
            },
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            }
        )
        
        # Services auxiliares
        self.sales_service = SalesService(db, company_id)
        self.ml_service = MLService(db, company_id)
        self.weather_service = WeatherService(db, company_id)
        
        # Cache de contexto
        self.context_cache = {}
        
    async def process_message(
        self,
        message: str,
        session_id: Optional[str] = None,
        include_context: bool = True
    ) -> ChatResponse:
        """
        Processa mensagem do usuário e gera resposta
        """
        try:
            # Criar ou recuperar sessão
            session = await self._get_or_create_session(session_id)
            
            # Identificar intenção
            intent = await self._identify_intent(message)
            
            # Coletar contexto relevante
            context = await self._build_context(session.id, intent, message)
            
            # Gerar resposta baseada na intenção
            response = await self._generate_response(
                message,
                intent,
                context,
                include_context
            )
            
            # Salvar no histórico
            await self._save_chat_history(
                session.id,
                message,
                response["content"],
                intent,
                response.get("data")
            )
            
            # Preparar resposta final
            return ChatResponse(
                session_id=session.id,
                message=response["content"],
                intent=intent.value,
                response_type=response["type"],
                data=response.get("data"),
                suggestions=await self._generate_suggestions(intent, context),
                timestamp=datetime.utcnow().isoformat()
            )
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            raise AIServiceError(f"Failed to process message: {str(e)}")
    
    async def generate_insights(
        self,
        data_type: str = "all",
        lookback_days: int = 30
    ) -> List[AIInsight]:
        """
        Gera insights automáticos baseados nos dados
        """
        try:
            insights = []
            
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=lookback_days)
            
            # Coletar dados para análise
            data = await self._collect_analysis_data(start_date, end_date, data_type)
            
            # Preparar prompt para Gemini
            prompt = self._build_insights_prompt(data)
            
            # Gerar insights com Gemini
            response = self.model.generate_content(prompt)
            
            # Processar resposta
            insights_text = response.text
            
            # Extrair insights estruturados
            parsed_insights = self._parse_insights(insights_text)
            
            # Enriquecer com dados e classificação
            for insight in parsed_insights:
                enriched = await self._enrich_insight(insight, data)
                
                insights.append(AIInsight(
                    type=enriched["type"],
                    title=enriched["title"],
                    description=enriched["description"],
                    impact=enriched["impact"],
                    confidence=enriched["confidence"],
                    recommendations=enriched["recommendations"],
                    data_points=enriched["data_points"],
                    created_at=datetime.utcnow()
                ))
            
            # Salvar insights importantes
            await self._save_important_insights(insights)
            
            return insights
            
        except Exception as e:
            logger.error(f"Error generating insights: {str(e)}")
            raise AIServiceError(f"Failed to generate insights: {str(e)}")
    
    async def simulate_scenario(
        self,
        scenario: Dict[str, Any],
        target_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Simula cenário hipotético (e.g., "E se chover 50mm amanhã?")
        """
        try:
            if not target_date:
                target_date = datetime.utcnow() + timedelta(days=1)
            
            # Validar cenário
            validated_scenario = self._validate_scenario(scenario)
            
            # Usar ML service para predição
            impact = await self.ml_service.predict_weather_impact(
                validated_scenario["weather_conditions"],
                target_date,
                validated_scenario.get("impact_type", "revenue")
            )
            
            # Gerar análise narrativa com Gemini
            narrative = await self._generate_scenario_narrative(
                validated_scenario,
                impact,
                target_date
            )
            
            # Gerar recomendações específicas
            recommendations = await self._generate_scenario_recommendations(
                validated_scenario,
                impact
            )
            
            return {
                "scenario": validated_scenario,
                "target_date": target_date.isoformat(),
                "impact_analysis": impact,
                "narrative": narrative,
                "recommendations": recommendations,
                "confidence_level": impact.get("confidence_score", 0.5),
                "visualization": await self._prepare_scenario_visualization(impact)
            }
            
        except Exception as e:
            logger.error(f"Error simulating scenario: {str(e)}")
            raise AIServiceError(f"Failed to simulate scenario: {str(e)}")
    
    async def explain_chart(
        self,
        chart_data: Dict[str, Any],
        chart_type: str
    ) -> str:
        """
        Gera explicação detalhada de um gráfico
        """
        try:
            # Preparar contexto do gráfico
            context = self._prepare_chart_context(chart_data, chart_type)
            
            # Prompt para Gemini
            prompt = f"""
            Analise este gráfico de {chart_type} e forneça uma explicação clara e detalhada:
            
            Dados do gráfico:
            {json.dumps(context, indent=2, default=str)}
            
            Por favor, explique:
            1. O que o gráfico mostra
            2. Principais padrões ou tendências
            3. Pontos notáveis ou anomalias
            4. O que isso significa para o negócio
            5. Ações recomendadas baseadas nos dados
            
            Use linguagem simples e acessível, focando em insights práticos.
            """
            
            response = self.model.generate_content(prompt)
            
            return response.text
            
        except Exception as e:
            logger.error(f"Error explaining chart: {str(e)}")
            return "Desculpe, não consegui analisar este gráfico no momento."
    
    async def generate_report_summary(
        self,
        report_data: Dict[str, Any],
        max_length: int = 500
    ) -> str:
        """
        Gera resumo executivo de relatório
        """
        try:
            # Extrair pontos principais
            key_points = self._extract_key_points(report_data)
            
            # Prompt para Gemini
            prompt = f"""
            Crie um resumo executivo conciso (máximo {max_length} palavras) baseado nestes dados:
            
            {json.dumps(key_points, indent=2, default=str)}
            
            O resumo deve incluir:
            - Visão geral do período analisado
            - Principais métricas de performance
            - Impactos climáticos relevantes
            - Tendências identificadas
            - Recomendações prioritárias
            
            Mantenha um tom profissional mas acessível.
            """
            
            response = self.model.generate_content(prompt)
            
            # Truncar se necessário
            summary = response.text
            if len(summary.split()) > max_length:
                words = summary.split()[:max_length]
                summary = ' '.join(words) + '...'
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating report summary: {str(e)}")
            return "Resumo não disponível."
    
    async def answer_question(
        self,
        question: str,
        data_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Responde perguntas específicas sobre os dados
        """
        try:
            # Coletar dados relevantes se não fornecidos
            if not data_context:
                data_context = await self._collect_relevant_data(question)
            
            # Preparar prompt com contexto
            prompt = self._build_qa_prompt(question, data_context)
            
            # Gerar resposta
            response = self.model.generate_content(prompt)
            
            # Processar resposta
            answer = response.text
            
            # Verificar se precisa de visualização
            needs_chart = self._check_if_needs_chart(question, answer)
            
            result = {
                "question": question,
                "answer": answer,
                "confidence": self._calculate_answer_confidence(answer, data_context),
                "sources": self._identify_data_sources(data_context),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            if needs_chart:
                result["chart_data"] = await self._prepare_chart_data(question, data_context)
                result["chart_type"] = self._suggest_chart_type(question, data_context)
            
            return result
            
        except Exception as e:
            logger.error(f"Error answering question: {str(e)}")
            raise AIServiceError(f"Failed to answer question: {str(e)}")
    
    async def get_chat_history(
        self,
        session_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        Obtém histórico de chat
        """
        try:
            query = self.db.query(ChatHistory).filter(
                ChatHistory.company_id == self.company_id,
                ChatHistory.user_id == self.user_id
            )
            
            if session_id:
                query = query.filter(ChatHistory.session_id == session_id)
            
            history = query.order_by(
                ChatHistory.created_at.desc()
            ).limit(limit).all()
            
            return [
                {
                    "session_id": h.session_id,
                    "user_message": h.user_message,
                    "ai_response": h.ai_response,
                    "intent": h.intent,
                    "timestamp": h.created_at.isoformat(),
                    "data": json.loads(h.context_data) if h.context_data else None
                }
                for h in reversed(history)  # Ordem cronológica
            ]
            
        except Exception as e:
            logger.error(f"Error getting chat history: {str(e)}")
            raise AIServiceError(f"Failed to get chat history: {str(e)}")
    
    # Métodos auxiliares privados
    
    async def _get_or_create_session(self, session_id: Optional[str]) -> ChatSession:
        """Obtém ou cria sessão de chat"""
        
        if session_id:
            session = self.db.query(ChatSession).filter(
                and_(
                    ChatSession.id == session_id,
                    ChatSession.user_id == self.user_id
                )
            ).first()
            
            if session:
                return session
        
        # Criar nova sessão
        session = ChatSession(
            id=self._generate_session_id(),
            user_id=self.user_id,
            company_id=self.company_id,
            created_at=datetime.utcnow(),
            last_activity=datetime.utcnow()
        )
        
        self.db.add(session)
        self.db.commit()
        
        return session
    
    async def _identify_intent(self, message: str) -> IntentType:
        """Identifica intenção da mensagem"""
        
        message_lower = message.lower()
        
        # Padrões para cada intenção
        patterns = {
            IntentType.GREETING: [
                r'\b(olá|oi|bom dia|boa tarde|boa noite|hey|hello)\b',
                r'^(e aí|eai|eae)\b'
            ],
            IntentType.SALES_QUERY: [
                r'\b(vendas?|faturamento|receita|lucro)\b',
                r'\b(quanto vend|performance de vendas)\b'
            ],
            IntentType.WEATHER_QUERY: [
                r'\b(clima|tempo|temperatura|chuva|sol|vento|umidade)\b',
                r'\b(previsão do tempo|condições climáticas)\b'
            ],
            IntentType.PREDICTION: [
                r'\b(previ[sã]|proje[çã]|futur|próxim|amanhã|semana que vem)\b',
                r'\b(vai|irá|será)\b.*\b(vender|chover|fazer)\b'
            ],
            IntentType.CORRELATION: [
                r'\b(correla|relaci|impact|afet|influenc)\b',
                r'\b(como|quanto).*\b(clima|tempo).*\b(vendas?|faturamento)\b'
            ],
            IntentType.RECOMMENDATION: [
                r'\b(recomend|sugest|conselho|dica|o que fazer)\b',
                r'\b(devo|deveria|posso)\b'
            ],
            IntentType.CHART_REQUEST: [
                r'\b(gráfico|chart|visualiz|mostr|exib)\b',
                r'\b(plote|desenhe|crie um gráfico)\b'
            ],
            IntentType.ALERT_QUERY: [
                r'\b(alert|aviso|notific)\b',
                r'\b(problema|atenção|cuidado)\b'
            ],
            IntentType.GOODBYE: [
                r'\b(tchau|até|adeus|bye|finalizar|encerrar)\b',
                r'^(vlw|valeu|obrigad|thanks?)\b'
            ]
        }
        
        # Verificar padrões
        for intent, pattern_list in patterns.items():
            for pattern in pattern_list:
                if re.search(pattern, message_lower):
                    return intent
        
        # Se não encontrar padrão específico, usar Gemini para classificar
        try:
            prompt = f"""
            Classifique a seguinte mensagem em uma destas categorias:
            - GREETING: cumprimentos
            - SALES_QUERY: perguntas sobre vendas
            - WEATHER_QUERY: perguntas sobre clima
            - PREDICTION: pedidos de previsão
            - CORRELATION: análise de correlação
            - RECOMMENDATION: pedido de recomendações
            - CHART_REQUEST: solicitação de gráfico
            - ALERT_QUERY: perguntas sobre alertas
            - GENERAL: outros assuntos
            
            Mensagem: "{message}"
            
            Responda apenas com a categoria.
            """
            
            response = self.model.generate_content(prompt)
            intent_str = response.text.strip().upper()
            
            # Tentar converter para enum
            try:
                return IntentType[intent_str]
            except KeyError:
                return IntentType.GENERAL
                
        except Exception:
            return IntentType.GENERAL
    
    async def _build_context(
        self,
        session_id: str,
        intent: IntentType,
        message: str
    ) -> Dict[str, Any]:
        """Constrói contexto relevante para a resposta"""
        
        context = {
            "session_id": session_id,
            "intent": intent.value,
            "timestamp": datetime.utcnow().isoformat(),
            "company_info": await self._get_company_info()
        }
        
        # Adicionar dados específicos baseado na intenção
        if intent in [IntentType.SALES_QUERY, IntentType.CORRELATION]:
            context["recent_sales"] = await self._get_recent_sales_summary()
            
        if intent in [IntentType.WEATHER_QUERY, IntentType.CORRELATION]:
            context["recent_weather"] = await self._get_recent_weather_summary()
            
        if intent == IntentType.PREDICTION:
            context["predictions"] = await self._get_recent_predictions()
            
        if intent == IntentType.ALERT_QUERY:
            context["active_alerts"] = await self._get_active_alerts_summary()
        
        # Histórico recente da conversa
        context["conversation_history"] = await self._get_recent_conversation(session_id)
        
        return context
    
    async def _generate_response(
        self,
        message: str,
        intent: IntentType,
        context: Dict,
        include_context: bool
    ) -> Dict[str, Any]:
        """Gera resposta baseada na intenção e contexto"""
        
        response = {
            "type": ResponseType.TEXT.value,
            "content": "",
            "data": None
        }
        
        try:
            if intent == IntentType.GREETING:
                response["content"] = await self._generate_greeting_response(context)
                
            elif intent == IntentType.SALES_QUERY:
                result = await self._handle_sales_query(message, context)
                response.update(result)
                
            elif intent == IntentType.WEATHER_QUERY:
                result = await self._handle_weather_query(message, context)
                response.update(result)
                
            elif intent == IntentType.PREDICTION:
                result = await self._handle_prediction_query(message, context)
                response.update(result)
                
            elif intent == IntentType.CORRELATION:
                result = await self._handle_correlation_query(message, context)
                response.update(result)
                
            elif intent == IntentType.RECOMMENDATION:
                response["content"] = await self._generate_recommendations(message, context)
                
            elif intent == IntentType.CHART_REQUEST:
                result = await self._handle_chart_request(message, context)
                response.update(result)
                
            elif intent == IntentType.ALERT_QUERY:
                result = await self._handle_alert_query(message, context)
                response.update(result)
                
            elif intent == IntentType.GOODBYE:
                response["content"] = await self._generate_goodbye_response(context)
                
            else:  # GENERAL
                response["content"] = await self._generate_general_response(message, context)
            
        except Exception as e:
            logger.error(f"Error generating response for intent {intent}: {str(e)}")
            response["content"] = "Desculpe, ocorreu um erro ao processar sua solicitação. Por favor, tente novamente."
        
        return response
    
    async def _generate_greeting_response(self, context: Dict) -> str:
        """Gera resposta de cumprimento"""
        
        hour = datetime.now().hour
        greeting = "Olá" if hour < 12 else "Boa tarde" if hour < 18 else "Boa noite"
        
        company_name = context.get("company_info", {}).get("name", "")
        
        responses = [
            f"{greeting}! Como posso ajudar você hoje com as análises de {company_name}?",
            f"{greeting}! Estou aqui para ajudar com insights sobre vendas e clima. O que gostaria de saber?",
            f"{greeting}! Pronto para analisar seus dados. Como posso ser útil?"
        ]
        
        return responses[hash(context["timestamp"]) % len(responses)]
    
    async def _handle_sales_query(self, message: str, context: Dict) -> Dict[str, Any]:
        """Processa consulta sobre vendas"""
        
        # Extrair período da mensagem
        period = self._extract_time_period(message)
        
        # Buscar dados de vendas
        sales_data = await self.sales_service.get_sales_metrics(
            start_date=period["start"],
            end_date=period["end"]
        )
        
        # Gerar resposta narrativa com Gemini
        prompt = f"""
        O usuário perguntou: "{message}"
        
        Dados de vendas do período:
        {json.dumps(sales_data.dict(), indent=2, default=str)}
        
        Contexto adicional:
        {json.dumps(context.get("recent_sales", {}), indent=2, default=str)}
        
        Forneça uma resposta clara e informativa sobre as vendas, incluindo:
        - Valores principais
        - Comparações relevantes
        - Tendências observadas
        
        Mantenha a resposta concisa e em português brasileiro.
        """
        
        response = self.model.generate_content(prompt)
        
        # Verificar se precisa de gráfico
        if "gráfico" in message.lower() or "visualizar" in message.lower():
            chart_data = await self._prepare_sales_chart_data(period, sales_data)
            return {
                "type": ResponseType.MIXED.value,
                "content": response.text,
                "data": {
                    "chart": chart_data,
                    "metrics": sales_data.dict()
                }
            }
        
        return {
            "type": ResponseType.TEXT.value,
            "content": response.text,
            "data": {"metrics": sales_data.dict()}
        }
    
    async def _handle_weather_query(self, message: str, context: Dict) -> Dict[str, Any]:
        """Processa consulta sobre clima"""
        
        # Buscar dados climáticos atuais e previsão
        current_weather = await self.weather_service.get_current_weather()
        forecast = await self.weather_service.get_forecast(days=7)
        
        # Gerar resposta
        prompt = f"""
        O usuário perguntou: "{message}"
        
        Condições climáticas atuais:
        {json.dumps(current_weather, indent=2, default=str)}
        
        Previsão próximos dias:
        {json.dumps(forecast, indent=2, default=str)}
        
        Forneça uma resposta informativa sobre o clima, incluindo:
        - Condições atuais
        - Previsão relevante
        - Possíveis impactos no negócio
        
        Responda em português brasileiro de forma clara.
        """
        
        response = self.model.generate_content(prompt)
        
        return {
            "type": ResponseType.TEXT.value,
            "content": response.text,
            "data": {
                "current": current_weather,
                "forecast": forecast
            }
        }
    
    async def _handle_prediction_query(self, message: str, context: Dict) -> Dict[str, Any]:
        """Processa consulta sobre previsões"""
        
        # Extrair período para previsão
        period = self._extract_future_period(message)
        
        # Gerar previsão
        predictions = await self.ml_service.predict_sales(
            start_date=period["start"],
            end_date=period["end"]
        )
        
        # Gerar narrativa
        prompt = f"""
        O usuário perguntou: "{message}"
        
        Previsões geradas:
        {json.dumps(predictions.dict(), indent=2, default=str)}
        
        Crie uma resposta explicando:
        - Valores previstos
        - Nível de confiança
        - Fatores considerados
        - Recomendações baseadas na previsão
        
        Use linguagem clara e acessível em português brasileiro.
        """
        
        response = self.model.generate_content(prompt)
        
        return {
            "type": ResponseType.MIXED.value,
            "content": response.text,
            "data": {
                "predictions": predictions.dict(),
                "chart": await self._prepare_prediction_chart_data(predictions)
            }
        }
    
    async def _handle_correlation_query(self, message: str, context: Dict) -> Dict[str, Any]:
        """Processa consulta sobre correlações"""
        
        # Analisar correlações
        period = self._extract_time_period(message)
        correlations = await self.sales_service.analyze_weather_impact(
            start_date=period["start"],
            end_date=period["end"]
        )
        
        # Gerar explicação
        prompt = f"""
        O usuário perguntou: "{message}"
        
        Análise de correlação clima vs vendas:
        {json.dumps(correlations, indent=2, default=str)}
        
        Explique:
        - Principais correlações encontradas
        - O que cada correlação significa na prática
        - Como usar essas informações
        - Limitações da análise
        
        Use linguagem simples e exemplos práticos.
        """
        
        response = self.model.generate_content(prompt)
        
        return {
            "type": ResponseType.MIXED.value,
            "content": response.text,
            "data": {
                "correlations": correlations,
                "chart": await self._prepare_correlation_chart_data(correlations)
            }
        }
    
    async def _generate_recommendations(self, message: str, context: Dict) -> str:
        """Gera recomendações personalizadas"""
        
        # Coletar dados para análise
        sales_summary = context.get("recent_sales", {})
        weather_summary = context.get("recent_weather", {})
        predictions = context.get("predictions", {})
        
        prompt = f"""
        O usuário pediu recomendações: "{message}"
        
        Contexto do negócio:
        - Vendas recentes: {json.dumps(sales_summary, indent=2, default=str)}
        - Condições climáticas: {json.dumps(weather_summary, indent=2, default=str)}
        - Previsões: {json.dumps(predictions, indent=2, default=str)}
        
        Forneça recomendações práticas e acionáveis:
        1. Ações imediatas (próximos 1-3 dias)
        2. Estratégias de médio prazo (próximas 2 semanas)
        3. Considerações de longo prazo
        
        Base as recomendações em dados concretos e seja específico.
        """
        
        response = self.model.generate_content(prompt)
        
        return response.text
    
    async def _handle_chart_request(self, message: str, context: Dict) -> Dict[str, Any]:
        """Processa solicitação de gráfico"""
        
        # Identificar tipo de gráfico desejado
        chart_type = self._identify_chart_type(message)
        
        # Preparar dados para o gráfico
        if "vendas" in message.lower() or "receita" in message.lower():
            data = await self._prepare_sales_chart_data(
                self._extract_time_period(message),
                None
            )
        elif "clima" in message.lower() or "temperatura" in message.lower():
            data = await self._prepare_weather_chart_data(
                self._extract_time_period(message)
            )
        elif "correlação" in message.lower():
            correlations = await self.sales_service.analyze_weather_impact(
                start_date=datetime.utcnow() - timedelta(days=30),
                end_date=datetime.utcnow()
            )
            data = await self._prepare_correlation_chart_data(correlations)
        else:
            # Gráfico padrão: vendas vs clima
            data = await self._prepare_combined_chart_data(
                self._extract_time_period(message)
            )
        
        # Gerar explicação do gráfico
        explanation = await self.explain_chart(data, chart_type)
        
        return {
            "type": ResponseType.CHART.value,
            "content": explanation,
            "data": {
                "chart": data,
                "chart_type": chart_type
            }
        }
    
    async def _handle_alert_query(self, message: str, context: Dict) -> Dict[str, Any]:
        """Processa consulta sobre alertas"""
        
        active_alerts = context.get("active_alerts", [])
        
        if not active_alerts:
            return {
                "type": ResponseType.TEXT.value,
                "content": "Não há alertas ativos no momento. Todos os indicadores estão dentro dos parâmetros normais.",
                "data": None
            }
        
        # Gerar resumo dos alertas
        prompt = f"""
        O usuário perguntou sobre alertas: "{message}"
        
        Alertas ativos:
        {json.dumps(active_alerts, indent=2, default=str)}
        
        Forneça um resumo claro dos alertas, incluindo:
        - Alertas mais críticos
        - Ações recomendadas
        - Prazo para resolução
        
        Mantenha um tom informativo mas não alarmista.
        """
        
        response = self.model.generate_content(prompt)
        
        return {
            "type": ResponseType.TEXT.value,
            "content": response.text,
            "data": {"alerts": active_alerts}
        }
    
    async def _generate_goodbye_response(self, context: Dict) -> str:
        """Gera resposta de despedida"""
        
        responses = [
            "Até logo! Foi um prazer ajudar. Volte sempre que precisar de análises!",
            "Tchau! Espero ter sido útil. Estarei aqui quando precisar!",
            "Até breve! Continue acompanhando seus dados para melhores resultados!",
            "Obrigado por usar nosso assistente. Até a próxima!"
        ]
        
        return responses[hash(context["timestamp"]) % len(responses)]
    
    async def _generate_general_response(self, message: str, context: Dict) -> str:
        """Gera resposta para consultas gerais"""
        
        prompt = f"""
        O usuário fez uma pergunta geral sobre o negócio: "{message}"
        
        Contexto da empresa:
        {json.dumps(context.get("company_info", {}), indent=2, default=str)}
        
        Forneça uma resposta útil e informativa. Se não souber a resposta específica,
        sugira como posso ajudar com análises de vendas, clima ou previsões.
        
        Mantenha um tom amigável e profissional.
        """
        
        response = self.model.generate_content(prompt)
        
        return response.text
    
    async def _save_chat_history(
        self,
        session_id: str,
        user_message: str,
        ai_response: str,
        intent: IntentType,
        data: Optional[Dict]
    ):
        """Salva histórico do chat"""
        
        history = ChatHistory(
            session_id=session_id,
            user_id=self.user_id,
            company_id=self.company_id,
            user_message=user_message,
            ai_response=ai_response,
            intent=intent.value,
            context_data=json.dumps(data) if data else None,
            created_at=datetime.utcnow()
        )
        
        self.db.add(history)
        
        # Atualizar última atividade da sessão
        session = self.db.query(ChatSession).filter(
            ChatSession.id == session_id
        ).first()
        
        if session:
            session.last_activity = datetime.utcnow()
        
        self.db.commit()
    
    async def _generate_suggestions(
        self,
        intent: IntentType,
        context: Dict
    ) -> List[str]:
        """Gera sugestões de próximas perguntas"""
        
        suggestions_map = {
            IntentType.SALES_QUERY: [
                "Como estão as vendas comparadas ao mês passado?",
                "Qual produto está vendendo mais?",
                "Mostre um gráfico de vendas dos últimos 30 dias"
            ],
            IntentType.WEATHER_QUERY: [
                "Como o clima vai afetar as vendas amanhã?",
                "Qual a previsão para o fim de semana?",
                "Histórico de temperatura dos últimos 7 dias"
            ],
            IntentType.PREDICTION: [
                "Qual a previsão de vendas para a próxima semana?",
                "Como será o desempenho se chover nos próximos dias?",
                "Precisão das últimas previsões"
            ],
            IntentType.CORRELATION: [
                "Qual fator climático mais impacta as vendas?",
                "Mostre a correlação entre temperatura e vendas",
                "Como a umidade afeta diferentes produtos?"
            ]
        }
        
        base_suggestions = suggestions_map.get(intent, [
            "Mostre o resumo de hoje",
            "Quais são os alertas ativos?",
            "Gere um relatório executivo"
        ])
        
        # Personalizar baseado no contexto
        if "active_alerts" in context and context["active_alerts"]:
            base_suggestions.append("Explique os alertas ativos")
        
        return base_suggestions[:3]
    
    def _extract_time_period(self, message: str) -> Dict[datetime, datetime]:
        """Extrai período de tempo da mensagem"""
        
        now = datetime.utcnow()
        
        # Padrões comuns
        if "hoje" in message.lower():
            return {"start": now.replace(hour=0, minute=0, second=0), "end": now}
        elif "ontem" in message.lower():
            yesterday = now - timedelta(days=1)
            return {
                "start": yesterday.replace(hour=0, minute=0, second=0),
                "end": yesterday.replace(hour=23, minute=59, second=59)
            }
        elif "semana" in message.lower():
            return {"start": now - timedelta(days=7), "end": now}
        elif "mês" in message.lower() or "mes" in message.lower():
            return {"start": now - timedelta(days=30), "end": now}
        elif "ano" in message.lower():
            return {"start": now - timedelta(days=365), "end": now}
        else:
            # Padrão: últimos 30 dias
            return {"start": now - timedelta(days=30), "end": now}
    
    def _extract_future_period(self, message: str) -> Dict[datetime, datetime]:
        """Extrai período futuro da mensagem"""
        
        now = datetime.utcnow()
        
        if "amanhã" in message.lower():
            tomorrow = now + timedelta(days=1)
            return {
                "start": tomorrow.replace(hour=0, minute=0, second=0),
                "end": tomorrow.replace(hour=23, minute=59, second=59)
            }
        elif "próxima semana" in message.lower() or "proxima semana" in message.lower():
            return {"start": now, "end": now + timedelta(days=7)}
        elif "próximo mês" in message.lower() or "proximo mes" in message.lower():
            return {"start": now, "end": now + timedelta(days=30)}
        else:
            # Padrão: próximos 7 dias
            return {"start": now, "end": now + timedelta(days=7)}
    
    def _identify_chart_type(self, message: str) -> str:
        """Identifica tipo de gráfico solicitado"""
        
        message_lower = message.lower()
        
        if "linha" in message_lower or "temporal" in message_lower:
            return "line"
        elif "barra" in message_lower:
            return "bar"
        elif "pizza" in message_lower or "pie" in message_lower:
            return "pie"
        elif "scatter" in message_lower or "dispersão" in message_lower:
            return "scatter"
        elif "heatmap" in message_lower or "calor" in message_lower:
            return "heatmap"
        else:
            return "line"  # Padrão
    
    async def _prepare_sales_chart_data(
        self,
        period: Dict,
        sales_data: Optional[Any]
    ) -> Dict:
        """Prepara dados para gráfico de vendas"""
        
        if not sales_data:
            sales_data = await self.sales_service.get_sales_metrics(
                start_date=period["start"],
                end_date=period["end"],
                aggregation="daily"
            )
        
        # Buscar dados detalhados
        sales = self.db.query(SalesData).filter(
            and_(
                SalesData.company_id == self.company_id,
                SalesData.date >= period["start"].date(),
                SalesData.date <= period["end"].date()
            )
        ).order_by(SalesData.date).all()
        
        return {
            "type": "line",
            "title": "Evolução das Vendas",
            "data": [
                {
                    "date": s.date.isoformat(),
                    "value": float(s.revenue),
                    "label": f"R$ {s.revenue:,.2f}"
                }
                for s in sales
            ],
            "x_axis": "Data",
            "y_axis": "Vendas (R$)"
        }
    
    async def _prepare_weather_chart_data(self, period: Dict) -> Dict:
        """Prepara dados para gráfico climático"""
        
        weather = self.db.query(WeatherData).filter(
            and_(
                WeatherData.company_id == self.company_id,
                WeatherData.date >= period["start"].date(),
                WeatherData.date <= period["end"].date()
            )
        ).order_by(WeatherData.date).all()
        
        return {
            "type": "multi-line",
            "title": "Condições Climáticas",
            "series": [
                {
                    "name": "Temperatura",
                    "data": [
                        {"date": w.date.isoformat(), "value": w.temperature}
                        for w in weather
                    ]
                },
                {
                    "name": "Precipitação",
                    "data": [
                        {"date": w.date.isoformat(), "value": w.precipitation}
                        for w in weather
                    ]
                }
            ],
            "x_axis": "Data",
            "y_axis": "Valor"
        }
    
    async def _prepare_correlation_chart_data(self, correlations: Dict) -> Dict:
        """Prepara dados para gráfico de correlação"""
        
        corr_data = correlations.get("correlations", {})
        
        return {
            "type": "bar",
            "title": "Correlação Clima vs Vendas",
            "data": [
                {
                    "variable": var.replace("_", " ").title(),
                    "value": info.get("correlation", 0),
                    "significant": info.get("significant", False)
                }
                for var, info in corr_data.items()
            ],
            "x_axis": "Variável Climática",
            "y_axis": "Correlação"
        }
    
    async def _prepare_prediction_chart_data(self, predictions: Any) -> Dict:
        """Prepara dados para gráfico de previsões"""
        
        return {
            "type": "line-with-confidence",
            "title": "Previsão de Vendas",
            "data": [
                {
                    "date": p["date"],
                    "value": p["predicted_sales"],
                    "lower": p["confidence_interval"]["lower"],
                    "upper": p["confidence_interval"]["upper"]
                }
                for p in predictions.predictions[:14]  # 2 semanas
            ],
            "x_axis": "Data",
            "y_axis": "Vendas Previstas (R$)"
        }
    
    async def _prepare_combined_chart_data(self, period: Dict) -> Dict:
        """Prepara dados combinados vendas + clima"""
        
        # Buscar dados
        sales = self.db.query(SalesData).filter(
            and_(
                SalesData.company_id == self.company_id,
                SalesData.date >= period["start"].date(),
                SalesData.date <= period["end"].date()
            )
        ).all()
        
        weather = self.db.query(WeatherData).filter(
            and_(
                WeatherData.company_id == self.company_id,
                WeatherData.date >= period["start"].date(),
                WeatherData.date <= period["end"].date()
            )
        ).all()
        
        # Criar dicionários indexados por data
        sales_dict = {s.date: s.revenue for s in sales}
        weather_dict = {w.date: w for w in weather}
        
        # Combinar dados
        combined_data = []
        for date in sorted(set(sales_dict.keys()) | set(weather_dict.keys())):
            combined_data.append({
                "date": date.isoformat(),
                "sales": float(sales_dict.get(date, 0)),
                "temperature": weather_dict.get(date, {}).temperature if date in weather_dict else None,
                "precipitation": weather_dict.get(date, {}).precipitation if date in weather_dict else None
            })
        
        return {
            "type": "combined",
            "title": "Vendas vs Clima",
            "data": combined_data,
            "series": ["sales", "temperature", "precipitation"],
            "x_axis": "Data"
        }
    
    async def _get_company_info(self) -> Dict:
        """Obtém informações da empresa"""
        
        company = self.db.query(Company).filter(
            Company.id == self.company_id
        ).first()
        
        if company:
            return {
                "id": company.id,
                "name": company.name,
                "business_type": company.business_type,
                "created_at": company.created_at.isoformat()
            }
        
        return {}
    
    async def _get_recent_sales_summary(self) -> Dict:
        """Obtém resumo de vendas recentes"""
        
        try:
            metrics = await self.sales_service.get_sales_metrics(
                start_date=datetime.utcnow() - timedelta(days=7),
                end_date=datetime.utcnow(),
                aggregation="daily"
            )
            
            return metrics.dict()
        except:
            return {}
    
    async def _get_recent_weather_summary(self) -> Dict:
        """Obtém resumo climático recente"""
        
        try:
            current = await self.weather_service.get_current_weather()
            return current
        except:
            return {}
    
    async def _get_recent_predictions(self) -> Dict:
        """Obtém previsões recentes"""
        
        try:
            predictions = await self.ml_service.predict_sales(
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow() + timedelta(days=7)
            )
            
            return predictions.dict()
        except:
            return {}
    
    async def _get_active_alerts_summary(self) -> List[Dict]:
        """Obtém resumo de alertas ativos"""
        
        alerts = self.db.query(Alert).filter(
            and_(
                Alert.company_id == self.company_id,
                Alert.resolved_at.is_(None)
            )
        ).order_by(Alert.priority.desc()).limit(5).all()
        
        return [
            {
                "id": a.id,
                "type": a.alert_type,
                "title": a.title,
                "priority": a.priority,
                "triggered_at": a.triggered_at.isoformat()
            }
            for a in alerts
        ]
    
    async def _get_recent_conversation(self, session_id: str, limit: int = 5) -> List[Dict]:
        """Obtém conversas recentes da sessão"""
        
        history = self.db.query(ChatHistory).filter(
            ChatHistory.session_id == session_id
        ).order_by(ChatHistory.created_at.desc()).limit(limit).all()
        
        return [
            {
                "user": h.user_message,
                "assistant": h.ai_response,
                "timestamp": h.created_at.isoformat()
            }
            for h in reversed(history)
        ]
    
    def _generate_session_id(self) -> str:
        """Gera ID único para sessão"""
        
        timestamp = datetime.utcnow().isoformat()
        unique_string = f"{self.user_id}_{self.company_id}_{timestamp}"
        return hashlib.md5(unique_string.encode()).hexdigest()
    
    async def _collect_analysis_data(
        self,
        start_date: datetime,
        end_date: datetime,
        data_type: str
    ) -> Dict:
        """Coleta dados para análise"""
        
        data = {}
        
        if data_type in ["all", "sales"]:
            sales_metrics = await self.sales_service.get_sales_metrics(
                start_date, end_date
            )
            data["sales"] = sales_metrics.dict()
        
        if data_type in ["all", "weather"]:
            weather_data = await self.weather_service.get_historical_data(
                start_date, end_date
            )
            data["weather"] = weather_data
        
        if data_type in ["all", "correlations"]:
            correlations = await self.sales_service.analyze_weather_impact(
                start_date, end_date
            )
            data["correlations"] = correlations
        
        return data
    
    def _build_insights_prompt(self, data: Dict) -> str:
        """Constrói prompt para gerar insights"""
        
        return f"""
        Analise os seguintes dados e identifique insights importantes:
        
        {json.dumps(data, indent=2, default=str)}
        
        Identifique:
        1. Padrões interessantes ou inesperados
        2. Oportunidades de melhoria
        3. Riscos potenciais
        4. Correlações significativas
        5. Anomalias que merecem atenção
        
        Para cada insight, forneça:
        - Título claro
        - Descrição detalhada
        - Impacto estimado (alto/médio/baixo)
        - Recomendações práticas
        - Dados que suportam a conclusão
        
        Seja específico e baseie-se apenas nos dados fornecidos.
        """
    
    def _parse_insights(self, insights_text: str) -> List[Dict]:
        """Extrai insights estruturados do texto"""
        
        # Implementação simplificada
        # Em produção, usar parsing mais sofisticado ou pedir resposta estruturada
        
        insights = []
        
        # Dividir por seções numeradas
        sections = re.split(r'\d+\.', insights_text)
        
        for section in sections[1:]:  # Pular primeira seção vazia
            lines = section.strip().split('\n')
            if lines:
                insight = {
                    "title": lines[0].strip(),
                    "description": '\n'.join(lines[1:]).strip(),
                    "raw_text": section.strip()
                }
                insights.append(insight)
        
        return insights
    
    async def _enrich_insight(self, insight: Dict, data: Dict) -> Dict:
        """Enriquece insight com dados adicionais"""
        
        enriched = insight.copy()
        
        # Determinar tipo
        if any(word in insight.get("title", "").lower() for word in ["venda", "receita", "faturamento"]):
            enriched["type"] = "sales"
        elif any(word in insight.get("title", "").lower() for word in ["clima", "tempo", "temperatura"]):
            enriched["type"] = "weather"
        elif "correlação" in insight.get("title", "").lower():
            enriched["type"] = "correlation"
        else:
            enriched["type"] = "general"
        
        # Estimar impacto
        if any(word in insight.get("description", "").lower() for word in ["crítico", "urgente", "importante"]):
            enriched["impact"] = "high"
        elif any(word in insight.get("description", "").lower() for word in ["moderado", "médio"]):
            enriched["impact"] = "medium"
        else:
            enriched["impact"] = "low"
        
        # Score de confiança (simplificado)
        enriched["confidence"] = 0.85  # Placeholder
        
        # Extrair recomendações
        recommendations = []
        if "recomend" in insight.get("description", "").lower():
            # Extrair frases que parecem recomendações
            sentences = insight["description"].split('.')
            for sentence in sentences:
                if any(word in sentence.lower() for word in ["recomend", "suger", "deve", "precisa"]):
                    recommendations.append(sentence.strip())
        
        enriched["recommendations"] = recommendations[:3]
        
        # Dados de suporte
        enriched["data_points"] = []
        
        return enriched
    
    async def _save_important_insights(self, insights: List[AIInsight]):
        """Salva insights importantes para referência futura"""
        
        # Implementar salvamento em banco se necessário
        # Por enquanto, apenas log
        
        for insight in insights:
            if insight.impact == "high":
                logger.info(f"High impact insight: {insight.title}")
    
    def _validate_scenario(self, scenario: Dict) -> Dict:
        """Valida e normaliza cenário"""
        
        validated = {
            "weather_conditions": {},
            "impact_type": scenario.get("impact_type", "revenue")
        }
        
        # Validar condições climáticas
        if "temperature" in scenario:
            validated["weather_conditions"]["temperature"] = float(scenario["temperature"])
        
        if "precipitation" in scenario:
            validated["weather_conditions"]["precipitation"] = float(scenario["precipitation"])
        
        if "humidity" in scenario:
            validated["weather_conditions"]["humidity"] = float(scenario["humidity"])
        
        if "wind_speed" in scenario:
            validated["weather_conditions"]["wind_speed"] = float(scenario["wind_speed"])
        
        return validated
    
    async def _generate_scenario_narrative(
        self,
        scenario: Dict,
        impact: Dict,
        target_date: datetime
    ) -> str:
        """Gera narrativa para cenário simulado"""
        
        prompt = f"""
        Explique o impacto do seguinte cenário climático:
        
        Cenário: {json.dumps(scenario, indent=2)}
        Data alvo: {target_date.strftime('%d/%m/%Y')}
        Impacto calculado: {json.dumps(impact, indent=2, default=str)}
        
        Crie uma narrativa clara explicando:
        - O que aconteceria neste cenário
        - Por que o impacto seria esse
        - Fatores considerados na análise
        - Nível de confiança na previsão
        
        Use linguagem acessível e exemplos práticos.
        """
        
        response = self.model.generate_content(prompt)
        return response.text
    
    async def _generate_scenario_recommendations(
        self,
        scenario: Dict,
        impact: Dict
    ) -> List[str]:
        """Gera recomendações para cenário"""
        
        recommendations = []
        
        impact_percentage = impact.get("impact_percentage", 0)
        
        if impact_percentage > 20:
            recommendations.append(
                f"Aumente o estoque em {abs(impact_percentage):.0f}% para atender a demanda esperada"
            )
            recommendations.append(
                "Prepare campanhas de marketing para aproveitar as condições favoráveis"
            )
        elif impact_percentage < -20:
            recommendations.append(
                f"Considere reduzir pedidos em {abs(impact_percentage):.0f}% para evitar excesso de estoque"
            )
            recommendations.append(
                "Implemente promoções para estimular vendas durante período desfavorável"
            )
        else:
            recommendations.append(
                "Mantenha operações normais com monitoramento próximo"
            )
        
        # Adicionar recomendações específicas baseadas no clima
        weather = scenario.get("weather_conditions", {})
        
        if weather.get("precipitation", 0) > 30:
            recommendations.append(
                "Reforce serviços de delivery e opções de compra online"
            )
        
        if weather.get("temperature", 25) > 32:
            recommendations.append(
                "Priorize produtos de verão e bebidas geladas"
            )
        elif weather.get("temperature", 25) < 18:
            recommendations.append(
                "Destaque produtos de inverno e bebidas quentes"
            )
        
        return recommendations[:5]
    
    async def _prepare_scenario_visualization(self, impact: Dict) -> Dict:
        """Prepara visualização para cenário"""
        
        return {
            "type": "gauge",
            "title": "Impacto Esperado",
            "value": impact.get("impact_percentage", 0),
            "ranges": [
                {"from": -100, "to": -20, "color": "red", "label": "Negativo"},
                {"from": -20, "to": 20, "color": "yellow", "label": "Neutro"},
                {"from": 20, "to": 100, "color": "green", "label": "Positivo"}
            ],
            "threshold": 0
        }
    
    def _prepare_chart_context(self, chart_data: Dict, chart_type: str) -> Dict:
        """Prepara contexto para explicação de gráfico"""
        
        context = {
            "type": chart_type,
            "title": chart_data.get("title", ""),
            "data_points": len(chart_data.get("data", [])),
            "x_axis": chart_data.get("x_axis", ""),
            "y_axis": chart_data.get("y_axis", "")
        }
        
        # Adicionar estatísticas básicas
        if "data" in chart_data:
            values = [d.get("value", 0) for d in chart_data["data"]]
            if values:
                context["statistics"] = {
                    "min": min(values),
                    "max": max(values),
                    "mean": sum(values) / len(values),
                    "trend": "increasing" if values[-1] > values[0] else "decreasing"
                }
        
        return context
    
    def _extract_key_points(self, report_data: Dict) -> Dict:
        """Extrai pontos principais de relatório"""
        
        key_points = {}
        
        if "sales_analysis" in report_data:
            key_points["sales"] = {
                "total": report_data["sales_analysis"].get("total_revenue"),
                "growth": report_data["sales_analysis"].get("growth_rate"),
                "trend": report_data["sales_analysis"].get("trend")
            }
        
        if "weather_analysis" in report_data:
            key_points["weather"] = {
                "main_impact": report_data["weather_analysis"].get("most_impactful_variable"),
                "correlation": report_data["weather_analysis"].get("correlations")
            }
        
        if "predictions" in report_data:
            key_points["forecast"] = {
                "next_week": report_data["predictions"].get("summary", {}).get("total_predicted"),
                "confidence": report_data["predictions"].get("confidence_metrics", {}).get("confidence_score")
            }
        
        return key_points
    
    async def _collect_relevant_data(self, question: str) -> Dict:
        """Coleta dados relevantes para responder pergunta"""
        
        # Análise simples de keywords para determinar dados necessários
        data = {}
        
        if any(word in question.lower() for word in ["venda", "receita", "faturamento"]):
            data["sales"] = await self._get_recent_sales_summary()
        
        if any(word in question.lower() for word in ["clima", "tempo", "temperatura", "chuva"]):
            data["weather"] = await self._get_recent_weather_summary()
        
        if any(word in question.lower() for word in ["previsão", "futuro", "próximo"]):
            data["predictions"] = await self._get_recent_predictions()
        
        if any(word in question.lower() for word in ["alert", "aviso", "problema"]):
            data["alerts"] = await self._get_active_alerts_summary()
        
        return data
    
    def _build_qa_prompt(self, question: str, data_context: Dict) -> str:
        """Constrói prompt para Q&A"""
        
        return f"""
        Responda a seguinte pergunta baseado nos dados fornecidos:
        
        Pergunta: "{question}"
        
        Dados disponíveis:
        {json.dumps(data_context, indent=2, default=str)}
        
        Forneça uma resposta precisa e completa. Se os dados não forem suficientes
        para responder completamente, indique o que está faltando.
        
        Use linguagem clara e inclua números específicos quando relevante.
        """
    
    def _check_if_needs_chart(self, question: str, answer: str) -> bool:
        """Verifica se a resposta seria melhor com gráfico"""
        
        chart_keywords = [
            "gráfico", "visualizar", "mostrar", "exibir", "plotar",
            "evolução", "tendência", "comparar", "histórico"
        ]
        
        return any(keyword in question.lower() or keyword in answer.lower() 
                  for keyword in chart_keywords)
    
    def _calculate_answer_confidence(self, answer: str, data_context: Dict) -> float:
        """Calcula confiança na resposta"""
        
        # Heurística simples baseada em quantidade de dados
        if not data_context:
            return 0.3
        
        confidence = 0.5
        
        # Aumentar confiança se há dados relevantes
        if data_context:
            confidence += 0.1 * min(len(data_context), 3)
        
        # Ajustar baseado na resposta
        if "não" in answer.lower() or "insuficiente" in answer.lower():
            confidence *= 0.7
        
        return min(confidence, 0.95)
    
    def _identify_data_sources(self, data_context: Dict) -> List[str]:
        """Identifica fontes de dados usadas"""
        
        sources = []
        
        if "sales" in data_context:
            sources.append("Dados de vendas")
        
        if "weather" in data_context:
            sources.append("Dados climáticos")
        
        if "predictions" in data_context:
            sources.append("Modelos preditivos")
        
        if "alerts" in data_context:
            sources.append("Sistema de alertas")
        
        return sources
    
    async def _prepare_chart_data(self, question: str, data_context: Dict) -> Dict:
        """Prepara dados para gráfico baseado na pergunta"""
        
        # Implementação simplificada
        # Determinar tipo de gráfico baseado na pergunta
        
        if "sales" in data_context:
            return await self._prepare_sales_chart_data(
                self._extract_time_period(question),
                None
            )
        elif "weather" in data_context:
            return await self._prepare_weather_chart_data(
                self._extract_time_period(question)
            )
        else:
            return {}
    
    def _suggest_chart_type(self, question: str, data_context: Dict) -> str:
        """Sugere tipo de gráfico apropriado"""
        
        if "evolução" in question.lower() or "histórico" in question.lower():
            return "line"
        elif "comparar" in question.lower():
            return "bar"
        elif "proporção" in question.lower() or "percentual" in question.lower():
            return "pie"
        else:
            return "line"