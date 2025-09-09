# Tenant isolation, CORS, etc
"""
Middlewares customizados para o sistema Asterion.
Implementa isolamento multi-tenant, CORS, rate limiting, logging, etc.
"""

import time
import uuid
import json
import logging
from typing import Optional, Dict, Any, Callable, List
from datetime import datetime, timezone
from contextvars import ContextVar

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.config.security import SECURITY_HEADERS
from app.core.exceptions import (
    TenantAccessDenied,
    RateLimitExceeded,
    APIException
)

# Logger
logger = logging.getLogger(__name__)

# Context variables para dados compartilhados na requisição
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
company_id_var: ContextVar[Optional[int]] = ContextVar("company_id", default=None)
user_id_var: ContextVar[Optional[int]] = ContextVar("user_id", default=None)


# ==================== REQUEST ID MIDDLEWARE ====================

class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Adiciona ID único para cada requisição.
    Útil para rastreamento e debugging.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Gera ou obtém request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request_id_var.set(request_id)
        
        # Adiciona ao state da request
        request.state.request_id = request_id
        
        # Processa requisição
        response = await call_next(request)
        
        # Adiciona header na resposta
        response.headers["X-Request-ID"] = request_id
        
        return response


# ==================== LOGGING MIDDLEWARE ====================

class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Loga todas as requisições e respostas.
    Inclui métricas de performance.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Início da requisição
        start_time = time.time()
        
        # Dados da requisição
        request_data = {
            "request_id": request_id_var.get(),
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "client_host": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        }
        
        # Log de entrada
        logger.info(f"Request started: {json.dumps(request_data)}")
        
        try:
            # Processa requisição
            response = await call_next(request)
            
            # Calcula tempo de resposta
            process_time = time.time() - start_time
            
            # Log de saída
            response_data = {
                "request_id": request_id_var.get(),
                "status_code": response.status_code,
                "process_time": f"{process_time:.3f}s",
            }
            
            # Adiciona header de tempo de processamento
            response.headers["X-Process-Time"] = f"{process_time:.3f}"
            
            # Log level baseado no status
            if response.status_code >= 500:
                logger.error(f"Request failed: {json.dumps(response_data)}")
            elif response.status_code >= 400:
                logger.warning(f"Request client error: {json.dumps(response_data)}")
            else:
                logger.info(f"Request completed: {json.dumps(response_data)}")
            
            return response
            
        except Exception as e:
            # Log de erro
            process_time = time.time() - start_time
            logger.error(
                f"Request exception: {request_id_var.get()} - {e} - {process_time:.3f}s",
                exc_info=True
            )
            raise


# ==================== TENANT ISOLATION MIDDLEWARE ====================

class TenantIsolationMiddleware(BaseHTTPMiddleware):
    """
    Middleware para isolamento multi-tenant.
    Garante que cada requisição acessa apenas dados da empresa correta.
    """
    
    # Endpoints que não precisam de tenant
    TENANT_EXEMPT_PATHS = [
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/forgot-password",
        "/api/v1/health",
        "/docs",
        "/redoc",
        "/openapi.json",
    ]
    
    async def dispatch(self, request: Request, call_next):
        # Verifica se path está isento
        if any(request.url.path.startswith(path) for path in self.TENANT_EXEMPT_PATHS):
            return await call_next(request)
        
        # Obtém company_id do token JWT (será setado pelo auth dependency)
        company_id = getattr(request.state, "company_id", None)
        
        # Se não tem company_id em rotas protegidas, é erro
        if not company_id and settings.ENABLE_MULTI_TENANT:
            # Verifica header alternativo (para API keys)
            company_id = request.headers.get(settings.TENANT_HEADER_NAME)
            
            if company_id:
                try:
                    company_id = int(company_id)
                except ValueError:
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={"error": "Invalid company ID in header"}
                    )
        
        # Seta no context var para uso global
        if company_id:
            company_id_var.set(company_id)
            request.state.company_id = company_id
        
        # Log de tenant
        if company_id:
            logger.debug(f"Request for company {company_id}")
        
        # Processa requisição
        response = await call_next(request)
        
        return response


# ==================== RATE LIMITING MIDDLEWARE ====================

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware para rate limiting.
    Usa Redis para controle distribuído.
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.redis_client: Optional[redis.Redis] = None
    
    async def dispatch(self, request: Request, call_next):
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)
        
        # Conecta ao Redis se necessário
        if not self.redis_client:
            try:
                self.redis_client = redis.from_url(
                    str(settings.REDIS_URL),
                    encoding="utf-8",
                    decode_responses=True
                )
            except Exception as e:
                logger.error(f"Failed to connect to Redis for rate limiting: {e}")
                return await call_next(request)
        
        # Identifica cliente (IP ou user_id)
        client_id = request.client.host if request.client else "unknown"
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            client_id = f"user:{user_id}"
        
        # Chave no Redis
        key = f"rate_limit:{client_id}:{request.url.path}"
        
        try:
            # Incrementa contador
            pipe = self.redis_client.pipeline()
            pipe.incr(key)
            pipe.expire(key, 60)  # Expira em 1 minuto
            result = await pipe.execute()
            
            request_count = result[0]
            
            # Verifica limite
            limit = settings.RATE_LIMIT_PER_MINUTE
            
            # Limites específicos por endpoint
            if "/export" in request.url.path:
                limit = 10  # Exports são pesados
            elif "/ml/train" in request.url.path:
                limit = 1  # Treinamento é muito pesado
            
            if request_count > limit:
                # Calcula tempo até reset
                ttl = await self.redis_client.ttl(key)
                
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "Rate limit exceeded",
                        "retry_after": ttl
                    },
                    headers={"Retry-After": str(ttl)}
                )
            
            # Adiciona headers de rate limit
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(max(0, limit - request_count))
            response.headers["X-RateLimit-Reset"] = str(int(time.time()) + 60)
            
            return response
            
        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            # Em caso de erro, permite a requisição
            return await call_next(request)


# ==================== SECURITY HEADERS MIDDLEWARE ====================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adiciona headers de segurança em todas as respostas.
    """
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Adiciona headers de segurança
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        
        return response


# ==================== ERROR HANDLING MIDDLEWARE ====================

class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Middleware para tratamento centralizado de erros.
    Converte exceções em respostas JSON padronizadas.
    """
    
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
            
        except APIException as e:
            # Erros de API customizados já têm formato correto
            raise
            
        except Exception as e:
            # Erros não tratados
            logger.error(
                f"Unhandled exception: {request_id_var.get()}",
                exc_info=True
            )
            
            # Resposta genérica em produção
            if not settings.DEBUG:
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "error": "Internal Server Error",
                        "message": "An unexpected error occurred",
                        "request_id": request_id_var.get()
                    }
                )
            
            # Em debug, mostra detalhes do erro
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": type(e).__name__,
                    "message": str(e),
                    "request_id": request_id_var.get()
                }
            )


# ==================== COMPRESSION MIDDLEWARE ====================

class CompressionMiddleware(BaseHTTPMiddleware):
    """
    Middleware para compressão de respostas grandes.
    """
    
    MIN_SIZE = 1024  # Mínimo de 1KB para comprimir
    
    async def dispatch(self, request: Request, call_next):
        # Verifica se cliente aceita gzip
        accept_encoding = request.headers.get("accept-encoding", "")
        
        response = await call_next(request)
        
        # Só comprime se cliente aceita e resposta é grande
        if "gzip" in accept_encoding and hasattr(response, "body"):
            # TODO: Implementar compressão gzip
            pass
        
        return response


# ==================== PERFORMANCE MONITORING MIDDLEWARE ====================

class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    """
    Monitora performance e envia métricas.
    """
    
    # Limites de alerta (em segundos)
    SLOW_REQUEST_THRESHOLD = 1.0
    VERY_SLOW_REQUEST_THRESHOLD = 5.0
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Adiciona timing ao state
        request.state.start_time = start_time
        
        # Processa requisição
        response = await call_next(request)
        
        # Calcula duração
        duration = time.time() - start_time
        
        # Log se requisição está lenta
        if duration > self.VERY_SLOW_REQUEST_THRESHOLD:
            logger.error(
                f"Very slow request: {request.url.path} took {duration:.2f}s"
            )
        elif duration > self.SLOW_REQUEST_THRESHOLD:
            logger.warning(
                f"Slow request: {request.url.path} took {duration:.2f}s"
            )
        
        # TODO: Enviar métricas para Prometheus/Grafana
        
        return response


# ==================== CORS CONFIGURATION ====================

def get_cors_middleware() -> CORSMiddleware:
    """
    Retorna middleware CORS configurado.
    
    Returns:
        CORSMiddleware configurado
    """
    return CORSMiddleware(
        app=None,  # Será setado pelo FastAPI
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-Request-ID",
            "X-Process-Time",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
        ]
    )


# ==================== TRUSTED HOST MIDDLEWARE ====================

def get_trusted_host_middleware() -> TrustedHostMiddleware:
    """
    Retorna middleware para validação de host.
    
    Returns:
        TrustedHostMiddleware configurado
    """
    allowed_hosts = ["localhost", "127.0.0.1"]
    
    # Adiciona hosts de produção
    if not settings.DEBUG:
        allowed_hosts.extend([
            "*.weatherbiz.com",
            "weatherbiz.com"
        ])
    
    return TrustedHostMiddleware(
        app=None,  # Será setado pelo FastAPI
        allowed_hosts=allowed_hosts
    )


# ==================== UTILITY FUNCTIONS ====================

def get_current_company_id() -> Optional[int]:
    """
    Obtém company_id do contexto atual.
    
    Returns:
        int: Company ID ou None
    """
    return company_id_var.get()


def get_current_user_id() -> Optional[int]:
    """
    Obtém user_id do contexto atual.
    
    Returns:
        int: User ID ou None
    """
    return user_id_var.get()


def get_current_request_id() -> str:
    """
    Obtém request_id do contexto atual.
    
    Returns:
        str: Request ID
    """
    return request_id_var.get()


# ==================== MIDDLEWARE REGISTRATION ====================

def register_middlewares(app) -> None:
    """
    Registra todos os middlewares na aplicação FastAPI.
    
    Args:
        app: Instância do FastAPI
    """
    # Ordem importa! Middlewares são executados na ordem reversa
    
    # Security headers (último a executar na resposta)
    app.add_middleware(SecurityHeadersMiddleware)
    
    # Compression
    app.add_middleware(CompressionMiddleware)
    
    # Error handling
    app.add_middleware(ErrorHandlingMiddleware)
    
    # Performance monitoring
    app.add_middleware(PerformanceMonitoringMiddleware)
    
    # Rate limiting
    app.add_middleware(RateLimitMiddleware)
    
    # Tenant isolation
    app.add_middleware(TenantIsolationMiddleware)
    
    # Logging
    app.add_middleware(LoggingMiddleware)
    
    # Request ID (primeiro a executar)
    app.add_middleware(RequestIDMiddleware)
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-Request-ID",
            "X-Process-Time",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
        ]
    )
    
    # Trusted hosts
    if not settings.DEBUG:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["*.weatherbiz.com", "weatherbiz.com", "localhost"]
        )
    
    logger.info("All middlewares registered successfully")


# Export
__all__ = [
    # Middlewares
    "RequestIDMiddleware",
    "LoggingMiddleware",
    "TenantIsolationMiddleware",
    "RateLimitMiddleware",
    "SecurityHeadersMiddleware",
    "ErrorHandlingMiddleware",
    "CompressionMiddleware",
    "PerformanceMonitoringMiddleware",
    
    # Functions
    "get_cors_middleware",
    "get_trusted_host_middleware",
    "register_middlewares",
    
    # Context utilities
    "get_current_company_id",
    "get_current_user_id",
    "get_current_request_id",
    
    # Context vars
    "request_id_var",
    "company_id_var",
    "user_id_var"
]