"""
Database core for SQLAlchemy setup (Base, engine, SessionLocal) for WeatherBiz Analytics.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
import os

# Síncrono (ajuste para seu banco, ex: 'sqlite:///./test.db' ou 'postgresql://user:pass@host/db')
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in SQLALCHEMY_DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para modelos
Base = declarative_base()

# Função utilitária para inicializar o banco (criar tabelas)
def init_db():
    import app.models.database  # Garante que todos os modelos sejam importados
    Base.metadata.create_all(bind=engine)

__all__ = ["Base", "engine", "SessionLocal", "init_db"]
