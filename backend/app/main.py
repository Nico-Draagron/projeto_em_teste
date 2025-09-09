# ===========================
# backend/app/main.py
from contextlib import asynccontextmanager
import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.database import init_db
from app.core.middleware import register_middlewares
from app.api.v1.router import api_router
from app.core.celery_app import celery_app

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


# ==================== LIFESPAN EVENTS ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handle startup and shutdown events
    """
    # Startup
    logger.info("🚀 Starting WeatherBiz Analytics Backend...")
    
    # Initialize database
    try:
        init_db()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise
    
    # Test Redis connection
    try:
        from app.core.cache import redis_client
        await redis_client.ping()
        logger.info("✅ Redis connection successful")
    except Exception as e:
        logger.warning(f"⚠️ Redis connection failed: {e}")
    
    # Test Celery
    try:
        result = celery_app.send_task("app.tasks.health_check")
        logger.info(f"✅ Celery task queued: {result.id}")
    except Exception as e:
        logger.warning(f"⚠️ Celery connection failed: {e}")
    
    logger.info(f"✨ {settings.APP_NAME} v{settings.APP_VERSION} started successfully!")
    logger.info(f"📍 Environment: {settings.ENVIRONMENT}")
    logger.info(f"🔗 API Docs: http://localhost:8000/docs")
    
    yield
    
    # Shutdown
    logger.info("👋 Shutting down WeatherBiz Analytics...")
    
    # Close Redis connection
    try:
        from app.core.cache import redis_client
        await redis_client.close()
        logger.info("✅ Redis connection closed")
    except Exception as e:
        logger.warning(f"⚠️ Error closing Redis: {e}")
    
    logger.info("✨ Shutdown complete")


# ==================== CREATE APPLICATION ====================

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Weather impact analysis platform for business intelligence",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)


# ==================== SETUP MIDDLEWARE ====================

register_middlewares(app)


# ==================== EXCEPTION HANDLERS ====================

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    Handle HTTP exceptions
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle validation errors
    """
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": exc.errors(),
            "body": exc.body
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Handle general exceptions
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    # Don't expose internal errors in production
    if settings.DEBUG:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": str(exc),
                "type": type(exc).__name__
            }
        )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )


# ==================== ROUTES ====================

@app.get("/", tags=["Root"])
async def root() -> dict:
    """
    Root endpoint
    """
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """
    Health check endpoint
    """
    health_status = {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }
    
    # Check database
    try:
        from app.core.database import SessionLocal
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        health_status["database"] = "connected"
    except Exception as e:
        health_status["database"] = f"error: {str(e)}"
        health_status["status"] = "degraded"
    
    # Check Redis
    try:
        from app.core.cache import redis_client
        redis_client.ping()
        health_status["redis"] = "connected"
    except Exception as e:
        health_status["redis"] = f"error: {str(e)}"
        health_status["status"] = "degraded"
    
    # Check Celery
    try:
        from app.core.celery_app import celery_app
        stats = celery_app.control.inspect().stats()
        if stats:
            health_status["celery"] = "connected"
        else:
            health_status["celery"] = "no workers"
    except Exception as e:
        health_status["celery"] = f"error: {str(e)}"
        health_status["status"] = "degraded"
    
    return health_status


# ==================== INCLUDE API ROUTER ====================

app.include_router(
    api_router,
    prefix="/api/v1"
)


# ==================== STARTUP MESSAGE ====================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info"
    )