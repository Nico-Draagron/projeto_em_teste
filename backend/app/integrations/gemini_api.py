# Google Gemini AI
# ===========================
# backend/app/integrations/gemini_api.py
# ===========================
"""
Google Gemini AI Integration
For intelligent chat agent and insights
"""

import httpx
import json
from typing import Dict, List, Optional, Any, AsyncGenerator
import logging
from datetime import datetime

from app.core.config import settings
from app.core.exceptions import AIServiceError

logger = logging.getLogger(__name__)


class GeminiClient:
    """
    Client for Google Gemini AI API
    """
    
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GOOGLE_GEMINI_API_KEY
        if not self.api_key:
            logger.warning("Gemini API key not configured")
        self.client = httpx.AsyncClient(timeout=60.0)
        self.model = "gemini-pro"  # or "gemini-pro-vision" for multimodal
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def generate_response(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Generate AI response for user query
        """
        if not self.api_key:
            raise AIServiceError("Gemini API key not configured")
        
        try:
            # Build the prompt with context
            full_prompt = self._build_prompt(prompt, context, system_prompt)
            
            response = await self.client.post(
                f"{self.BASE_URL}/models/{self.model}:generateContent",
                params={"key": self.api_key},
                json={
                    "contents": [{
                        "parts": [{
                            "text": full_prompt
                        }]
                    }],
                    "generationConfig": {
                        "temperature": temperature,
                        "maxOutputTokens": max_tokens,
                        "topP": 0.95,
                        "topK": 40
                    }
                }
            )
            
            if response.status_code != 200:
                logger.error(f"Gemini API error: {response.text}")
                raise AIServiceError(f"Gemini API error: {response.status_code}")
            
            data = response.json()
            
            # Extract text from response
            if "candidates" in data and data["candidates"]:
                content = data["candidates"][0].get("content", {})
                parts = content.get("parts", [])
                if parts:
                    return parts[0].get("text", "")
            
            return "Desculpe, não consegui gerar uma resposta."
            
        except Exception as e:
            logger.error(f"Gemini API error: {str(e)}")
            raise AIServiceError(f"Failed to generate response: {str(e)}")
    
    async def analyze_data(
        self,
        data: Dict[str, Any],
        question: str,
        analysis_type: str = "correlation"
    ) -> Dict[str, Any]:
        """
        Analyze data and provide insights
        """
        if not self.api_key:
            raise AIServiceError("Gemini API key not configured")
        
        try:
            # Prepare data summary for AI
            data_summary = self._summarize_data(data)
            
            prompt = f"""
            Analise os seguintes dados de vendas e clima:
            
            {json.dumps(data_summary, indent=2)}
            
            Tipo de análise: {analysis_type}
            Pergunta: {question}
            
            Forneça:
            1. Principais insights
            2. Correlações identificadas
            3. Recomendações acionáveis
            4. Previsões baseadas nos padrões
            
            Responda em formato JSON estruturado.
            """
            
            response = await self.generate_response(
                prompt=prompt,
                temperature=0.5,  # Lower temperature for analytical tasks
                max_tokens=1500
            )
            
            # Try to parse JSON response
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                # If not valid JSON, return as text insight
                return {
                    "insights": response,
                    "type": "text",
                    "confidence": 0.8
                }
                
        except Exception as e:
            logger.error(f"Data analysis error: {str(e)}")
            raise AIServiceError(f"Failed to analyze data: {str(e)}")
    
    async def generate_report_summary(
        self,
        report_data: Dict[str, Any],
        report_type: str = "executive"
    ) -> str:
        """
        Generate executive summary for reports
        """
        prompt = f"""
        Crie um resumo executivo baseado nos seguintes dados:
        
        Tipo de relatório: {report_type}
        Período: {report_data.get('period', 'Último mês')}
        
        Métricas principais:
        - Vendas totais: R$ {report_data.get('total_sales', 0):,.2f}
        - Crescimento: {report_data.get('growth_rate', 0):.1f}%
        - Impacto climático: {report_data.get('weather_impact', 'Moderado')}
        
        Crie um resumo de 3-4 parágrafos destacando:
        1. Performance geral
        2. Principais fatores de impacto
        3. Recomendações estratégicas
        """
        
        return await self.generate_response(
            prompt=prompt,
            temperature=0.6,
            max_tokens=800
        )
    
    async def stream_response(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream response for real-time chat
        """
        if not self.api_key:
            raise AIServiceError("Gemini API key not configured")
        
        try:
            full_prompt = self._build_prompt(prompt, context)
            
            # Gemini doesn't support streaming yet, simulate it
            response = await self.generate_response(prompt, context)
            
            # Simulate streaming by yielding chunks
            words = response.split()
            chunk_size = 5
            
            for i in range(0, len(words), chunk_size):
                chunk = " ".join(words[i:i+chunk_size])
                yield chunk + " "
                
        except Exception as e:
            logger.error(f"Streaming error: {str(e)}")
            yield f"Erro: {str(e)}"
    
    def _build_prompt(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Build complete prompt with context
        """
        if not system_prompt:
            system_prompt = """
            Você é um assistente especializado em análise de impacto climático em vendas.
            Você tem acesso aos dados de vendas e clima da empresa.
            Sempre forneça insights acionáveis e baseados em dados.
            Seja conciso e direto, mas completo em suas análises.
            """
        
        full_prompt = system_prompt + "\n\n"
        
        if context:
            full_prompt += "Contexto:\n"
            full_prompt += f"- Empresa: {context.get('company_name', 'N/A')}\n"
            full_prompt += f"- Período: {context.get('period', 'N/A')}\n"
            full_prompt += f"- Localização: {context.get('location', 'N/A')}\n"
            
            if "recent_data" in context:
                full_prompt += f"\nDados recentes:\n{json.dumps(context['recent_data'], indent=2)}\n"
        
        full_prompt += f"\nPergunta do usuário: {prompt}\n"
        full_prompt += "\nResposta:"
        
        return full_prompt
    
    def _summarize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Summarize data for AI analysis
        """
        summary = {
            "data_points": len(data.get("values", [])),
            "date_range": {
                "start": data.get("start_date"),
                "end": data.get("end_date")
            }
        }
        
        # Calculate statistics if numerical data
        if "values" in data and data["values"]:
            import numpy as np
            values = [v for v in data["values"] if isinstance(v, (int, float))]
            if values:
                summary["statistics"] = {
                    "mean": float(np.mean(values)),
                    "std": float(np.std(values)),
                    "min": float(np.min(values)),
                    "max": float(np.max(values)),
                    "median": float(np.median(values))
                }
        
        # Add any patterns or trends
        if "patterns" in data:
            summary["patterns"] = data["patterns"]
        
        return summary