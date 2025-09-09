# Conexão PostgreSQL + Multi-tenant
"""
Configuração do banco de dados PostgreSQL com SQLAlchemy 2.0+.
Implementa suporte para multi-tenancy com isolamento por company_id.
"""

from typing import AsyncGenerator, Optional, Any
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
    AsyncEngine
)
from sqlalchemy.orm import declarative_base, Session
from sqlalchemy import (
    Column, 
    Integer, 
    DateTime, 
    String,
    event,
    inspect,
    text
)
from sqlalchemy.sql import func
from sqlalchemy.pool import NullPool, QueuePool
from contextlib import asynccontextmanager
import logging
from datetime import datetime

from app.config.settings import settings

# Logger
logger = logging.getLogger(__name__)

# ==================== ENGINE CONFIGURATION ====================

# Configuração do engine assíncrono
engine_config = {
    "echo": settings.DB_ECHO,  # Log SQL statements
    "future": True,  # SQLAlchemy 2.0 style
    "pool_pre_ping": settings.DB_POOL_PRE_PING,  # Verifica conexões antes de usar
}

# Configuração do pool de conexões baseado no ambiente
if settings.DEBUG:
    # Em desenvolvimento, usa NullPool (sem pool)
    engine_config["poolclass"] = NullPool
else:
    # Em produção, usa QueuePool com configurações otimizadas
    engine_config.update({
        "poolclass": QueuePool,
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_timeout": 30,
        "pool_recycle": 1800,  # Recicla conexões a cada 30 minutos
    })

# Cria o engine assíncrono
engine: AsyncEngine = create_async_engine(
    str(settings.DATABASE_URL),
    **engine_config
)

# Session factory assíncrono
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Não expira objetos após commit
    autocommit=False,
    autoflush=False,
)

# ==================== BASE MODELS ====================

# Base para todos os modelos
Base = declarative_base()


class TimestampMixin:
    """
    Mixin para adicionar campos de timestamp em todos os modelos.
    Padrão para auditoria e rastreamento.
    """
    
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        index=True
    )


class TenantMixin:
    """
    Mixin para adicionar suporte multi-tenant.
    Todos os modelos que precisam de isolamento por empresa devem herdar isso.
    """
    
    company_id = Column(
        Integer,
        nullable=False,
        index=True,
        doc="ID da empresa (tenant) para isolamento de dados"
    )


class SoftDeleteMixin:
    """
    Mixin para soft delete (exclusão lógica).
    Registros não são deletados fisicamente, apenas marcados como deletados.
    """
    
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        doc="Timestamp de quando o registro foi deletado (soft delete)"
    )
    
    deleted_by = Column(
        Integer,
        nullable=True,
        doc="ID do usuário que deletou o registro"
    )
    
    @property
    def is_deleted(self) -> bool:
        """Verifica se o registro está deletado."""
        return self.deleted_at is not None


# ==================== SESSION MANAGEMENT ====================

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency para obter sessão do banco de dados.
    Usado com FastAPI Depends().
    
    Yields:
        AsyncSession: Sessão assíncrona do SQLAlchemy
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager para sessão do banco de dados.
    Útil para operações fora do contexto de requisição.
    
    Example:
        async with get_db_context() as db:
            result = await db.execute(query)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ==================== MULTI-TENANT UTILITIES ====================

class TenantFilter:
    """
    Classe para gerenciar filtros multi-tenant automaticamente.
    """
    
    @staticmethod
    def apply_tenant_filter(query: Any, company_id: int) -> Any:
        """
        Aplica filtro de tenant em uma query.
        
        Args:
            query: Query SQLAlchemy
            company_id: ID da empresa para filtrar
            
        Returns:
            Query filtrada por company_id
        """
        model = query.column_descriptions[0]['entity']
        
        # Verifica se o modelo tem o campo company_id
        if hasattr(model, 'company_id'):
            return query.filter(model.company_id == company_id)
        
        return query
    
    @staticmethod
    def ensure_tenant_isolation(model_instance: Any, company_id: int) -> None:
        """
        Garante que um modelo pertence ao tenant correto.
        
        Args:
            model_instance: Instância do modelo
            company_id: ID esperado da empresa
            
        Raises:
            PermissionError: Se o modelo não pertence ao tenant
        """
        if hasattr(model_instance, 'company_id'):
            if model_instance.company_id != company_id:
                raise PermissionError(
                    f"Acesso negado: Recurso pertence a outra empresa"
                )


# ==================== DATABASE INITIALIZATION ====================

async def init_db() -> None:
    """
    Inicializa o banco de dados.
    Cria todas as tabelas se não existirem.
    """
    try:
        logger.info("Inicializando banco de dados...")
        
        async with engine.begin() as conn:
            # Importa todos os modelos para garantir que estão registrados
            from app.models import (
                user, company, notification,
                # Importar outros modelos conforme forem criados
            )
            
            # Cria todas as tabelas
            await conn.run_sync(Base.metadata.create_all)
            
            # Cria índices adicionais para performance
            await create_custom_indexes(conn)
            
        logger.info("Banco de dados inicializado com sucesso!")
        
    except Exception as e:
        logger.error(f"Erro ao inicializar banco de dados: {e}")
        raise


async def create_custom_indexes(conn: Any) -> None:
    """
    Cria índices customizados para otimização.
    Especialmente importante para queries multi-tenant.
    """
    # Índices compostos para queries multi-tenant comuns
    indexes = [
        # Exemplo: índice para buscar usuários por empresa
        "CREATE INDEX IF NOT EXISTS idx_users_company_email ON users(company_id, email);",
        # Exemplo: índice para buscar vendas por empresa e data
        "CREATE INDEX IF NOT EXISTS idx_sales_company_date ON sales_data(company_id, date DESC);",
        # Exemplo: índice para notificações não lidas por empresa
        "CREATE INDEX IF NOT EXISTS idx_notifications_company_read ON notifications(company_id, is_read) WHERE is_read = false;",
    ]
    
    for index_sql in indexes:
        try:
            await conn.execute(text(index_sql))
        except Exception as e:
            logger.warning(f"Não foi possível criar índice: {e}")


async def check_database_connection() -> bool:
    """
    Verifica se a conexão com o banco está funcionando.
    
    Returns:
        bool: True se conectado, False caso contrário
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            await conn.commit()
        return True
    except Exception as e:
        logger.error(f"Erro ao conectar ao banco de dados: {e}")
        return False


async def close_db() -> None:
    """
    Fecha todas as conexões com o banco de dados.
    Deve ser chamado ao desligar a aplicação.
    """
    await engine.dispose()
    logger.info("Conexões com banco de dados fechadas")


# ==================== TRANSACTION UTILITIES ====================

@asynccontextmanager
async def transaction(session: AsyncSession):
    """
    Context manager para transações explícitas.
    
    Example:
        async with transaction(session) as tx:
            # Operações dentro da transação
            await session.execute(...)
    """
    async with session.begin():
        yield session


# ==================== PERFORMANCE MONITORING ====================

@event.listens_for(engine.sync_engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """
    Hook para monitorar queries (desenvolvimento).
    """
    if settings.DEBUG:
        conn.info.setdefault('query_start_time', []).append(datetime.utcnow())
        logger.debug(f"Executando query: {statement[:100]}...")


@event.listens_for(engine.sync_engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """
    Hook para medir tempo de execução de queries (desenvolvimento).
    """
    if settings.DEBUG:
        total = datetime.utcnow() - conn.info['query_start_time'].pop(-1)
        logger.debug(f"Query executada em {total.total_seconds():.3f}s")


# ==================== UTILITY FUNCTIONS ====================

async def bulk_insert(session: AsyncSession, models: list) -> None:
    """
    Insere múltiplos registros de forma otimizada.
    
    Args:
        session: Sessão do banco
        models: Lista de instâncias de modelo
    """
    session.add_all(models)
    await session.commit()


async def execute_raw_sql(sql: str, params: Optional[dict] = None) -> Any:
    """
    Executa SQL raw quando necessário.
    
    Args:
        sql: Query SQL
        params: Parâmetros da query
        
    Returns:
        Resultado da query
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(text(sql), params or {})
        await session.commit()
        return result


# Export
__all__ = [
    "Base",
    "engine",
    "AsyncSessionLocal",
    "get_db",
    "get_db_context",
    "init_db",
    "close_db",
    "TimestampMixin",
    "TenantMixin",
    "SoftDeleteMixin",
    "TenantFilter",
    "transaction",
    "bulk_insert",
    "execute_raw_sql",
    "check_database_connection"
]