# CRUD usuários + permissions
"""
Service de gerenciamento de usuários para o sistema WeatherBiz Analytics.
Implementa CRUD de usuários com isolamento multi-tenant.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.models.company import Company
from app.models.notification import NotificationPreference
from app.models.schemas import (
    UserCreate, UserUpdate, UserResponse,
    PaginationParams, PaginatedResponse
)
from app.config.security import get_password_hash, UserRole
from app.core.exceptions import (
    NotFoundError, DuplicateError, ValidationError,
    TenantAccessDenied, InsufficientPermissions,
    PlanLimitExceeded
)
from app.core.utils import normalize_email, paginate

logger = logging.getLogger(__name__)


class UserService:
    """Service para gerenciamento de usuários."""
    
    def __init__(self, db: AsyncSession):
        """
        Inicializa o service.
        
        Args:
            db: Sessão do banco de dados
        """
        self.db = db
    
    async def get_user_by_id(
        self,
        user_id: int,
        company_id: Optional[int] = None
    ) -> UserResponse:
        """
        Busca usuário por ID.
        
        Args:
            user_id: ID do usuário
            company_id: ID da empresa (para validação multi-tenant)
            
        Returns:
            UserResponse: Usuário encontrado
            
        Raises:
            NotFoundError: Se usuário não encontrado
            TenantAccessDenied: Se usuário de outra empresa
        """
        query = select(User).options(
            selectinload(User.company)
        ).where(User.id == user_id)
        
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise NotFoundError("User", user_id)
        
        # Validação multi-tenant
        if company_id and user.company_id != company_id:
            raise TenantAccessDenied()
        
        return UserResponse.model_validate(user)
    
    async def get_user_by_email(
        self,
        email: str,
        company_id: Optional[int] = None
    ) -> UserResponse:
        """
        Busca usuário por email.
        
        Args:
            email: Email do usuário
            company_id: ID da empresa (opcional)
            
        Returns:
            UserResponse: Usuário encontrado
            
        Raises:
            NotFoundError: Se usuário não encontrado
        """
        query = select(User).options(
            selectinload(User.company)
        ).where(User.email == normalize_email(email))
        
        if company_id:
            query = query.where(User.company_id == company_id)
        
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise NotFoundError("User", f"email={email}")
        
        return UserResponse.model_validate(user)
    
    async def list_users(
        self,
        company_id: int,
        pagination: PaginationParams,
        filters: Optional[Dict[str, Any]] = None
    ) -> PaginatedResponse:
        """
        Lista usuários da empresa com paginação.
        
        Args:
            company_id: ID da empresa
            pagination: Parâmetros de paginação
            filters: Filtros opcionais
            
        Returns:
            PaginatedResponse: Lista paginada de usuários
        """
        # Query base
        query = select(User).options(
            selectinload(User.company)
        ).where(User.company_id == company_id)
        
        # Aplica filtros
        if filters:
            if filters.get("is_active") is not None:
                query = query.where(User.is_active == filters["is_active"])
            
            if filters.get("role"):
                query = query.where(User.role == filters["role"])
            
            if filters.get("is_verified") is not None:
                query = query.where(User.is_verified == filters["is_verified"])
            
            if filters.get("search"):
                search_term = f"%{filters['search']}%"
                query = query.where(
                    or_(
                        User.full_name.ilike(search_term),
                        User.email.ilike(search_term),
                        User.username.ilike(search_term)
                    )
                )
        
        # Ordenação
        if pagination.sort_by:
            order_column = getattr(User, pagination.sort_by, User.created_at)
            if pagination.sort_order == "desc":
                query = query.order_by(order_column.desc())
            else:
                query = query.order_by(order_column)
        else:
            query = query.order_by(User.created_at.desc())
        
        # Executa query para contar total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Aplica paginação
        offset = (pagination.page - 1) * pagination.page_size
        query = query.offset(offset).limit(pagination.page_size)
        
        # Executa query paginada
        result = await self.db.execute(query)
        users = result.scalars().all()
        
        # Converte para response
        items = [UserResponse.model_validate(user) for user in users]
        
        return PaginatedResponse(
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=(total + pagination.page_size - 1) // pagination.page_size,
            has_next=pagination.page * pagination.page_size < total,
            has_prev=pagination.page > 1
        )
    
    async def create_user(
        self,
        user_data: UserCreate,
        company_id: int,
        created_by_id: Optional[int] = None
    ) -> UserResponse:
        """
        Cria novo usuário.
        
        Args:
            user_data: Dados do usuário
            company_id: ID da empresa
            created_by_id: ID do usuário que está criando
            
        Returns:
            UserResponse: Usuário criado
            
        Raises:
            DuplicateError: Se email já existe
            PlanLimitExceeded: Se limite de usuários excedido
        """
        # Verifica limite do plano
        company_query = select(Company).where(Company.id == company_id)
        company_result = await self.db.execute(company_query)
        company = company_result.scalar_one()
        
        if not company.can_add_user:
            raise PlanLimitExceeded(
                "usuários",
                company.current_users_count,
                company.max_users
            )
        
        # Verifica se email já existe
        email = normalize_email(user_data.email)
        existing_query = select(User).where(User.email == email)
        existing_result = await self.db.execute(existing_query)
        if existing_result.scalar_one_or_none():
            raise DuplicateError("User", "email", email)
        
        # Cria usuário
        user = User(
            email=email,
            username=user_data.username,
            full_name=user_data.full_name,
            phone=user_data.phone,
            company_id=company_id,
            role=user_data.role,
            timezone=user_data.timezone,
            language=user_data.language,
            hashed_password=get_password_hash(user_data.password),
            is_active=True,
            is_verified=False,
            invited_by_id=created_by_id
        )
        
        self.db.add(user)
        
        # Cria preferências de notificação padrão
        notification_pref = NotificationPreference(
            user_id=user.id,
            company_id=company_id
        )
        self.db.add(notification_pref)
        
        # Atualiza contador da empresa
        company.current_users_count += 1
        
        await self.db.commit()
        await self.db.refresh(user)
        
        logger.info(f"User created: {user.email} for company {company_id}")
        
        return UserResponse.model_validate(user)
    
    async def update_user(
        self,
        user_id: int,
        user_data: UserUpdate,
        company_id: int,
        updated_by_id: Optional[int] = None
    ) -> UserResponse:
        """
        Atualiza usuário.
        
        Args:
            user_id: ID do usuário
            user_data: Dados para atualizar
            company_id: ID da empresa
            updated_by_id: ID do usuário que está atualizando
            
        Returns:
            UserResponse: Usuário atualizado
            
        Raises:
            NotFoundError: Se usuário não encontrado
            TenantAccessDenied: Se usuário de outra empresa
        """
        # Busca usuário
        query = select(User).where(
            and_(
                User.id == user_id,
                User.company_id == company_id
            )
        )
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise NotFoundError("User", user_id)
        
        # Atualiza campos fornecidos
        update_data = user_data.model_dump(exclude_unset=True)
        
        # Verifica se está mudando email
        if "email" in update_data:
            new_email = normalize_email(update_data["email"])
            if new_email != user.email:
                # Verifica se novo email já existe
                existing_query = select(User).where(User.email == new_email)
                existing_result = await self.db.execute(existing_query)
                if existing_result.scalar_one_or_none():
                    raise DuplicateError("User", "email", new_email)
                
                user.email = new_email
                user.is_verified = False  # Precisa reverificar
        
        # Atualiza outros campos
        for field, value in update_data.items():
            if field != "email" and hasattr(user, field):
                setattr(user, field, value)
        
        await self.db.commit()
        await self.db.refresh(user)
        
        logger.info(f"User updated: {user.email}")
        
        return UserResponse.model_validate(user)
    
    async def delete_user(
        self,
        user_id: int,
        company_id: int,
        deleted_by_id: Optional[int] = None,
        soft_delete: bool = True
    ) -> bool:
        """
        Exclui usuário.
        
        Args:
            user_id: ID do usuário
            company_id: ID da empresa
            deleted_by_id: ID do usuário que está excluindo
            soft_delete: Se deve fazer soft delete
            
        Returns:
            bool: Sucesso
            
        Raises:
            NotFoundError: Se usuário não encontrado
            ValidationError: Se tentando excluir único admin
        """
        # Busca usuário
        query = select(User).where(
            and_(
                User.id == user_id,
                User.company_id == company_id
            )
        )
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise NotFoundError("User", user_id)
        
        # Verifica se não é o único admin
        if user.role == UserRole.COMPANY_ADMIN:
            admin_count_query = select(func.count()).where(
                and_(
                    User.company_id == company_id,
                    User.role == UserRole.COMPANY_ADMIN,
                    User.is_active == True,
                    User.id != user_id
                )
            )
            admin_count_result = await self.db.execute(admin_count_query)
            admin_count = admin_count_result.scalar()
            
            if admin_count == 0:
                raise ValidationError(
                    "Não é possível excluir o único administrador da empresa"
                )
        
        if soft_delete:
            # Soft delete
            user.deleted_at = datetime.now(timezone.utc)
            user.deleted_by = deleted_by_id
            user.is_active = False
        else:
            # Hard delete
            await self.db.delete(user)
        
        # Atualiza contador da empresa
        company_query = select(Company).where(Company.id == company_id)
        company_result = await self.db.execute(company_query)
        company = company_result.scalar_one()
        company.current_users_count = max(0, company.current_users_count - 1)
        
        await self.db.commit()
        
        logger.info(f"User deleted: {user.email}")
        
        return True
    
    async def activate_user(
        self,
        user_id: int,
        company_id: int
    ) -> UserResponse:
        """
        Ativa usuário.
        
        Args:
            user_id: ID do usuário
            company_id: ID da empresa
            
        Returns:
            UserResponse: Usuário ativado
        """
        user = await self._get_user_for_update(user_id, company_id)
        user.is_active = True
        user.locked_until = None
        user.failed_login_attempts = 0
        
        await self.db.commit()
        await self.db.refresh(user)
        
        logger.info(f"User activated: {user.email}")
        
        return UserResponse.model_validate(user)
    
    async def deactivate_user(
        self,
        user_id: int,
        company_id: int
    ) -> UserResponse:
        """
        Desativa usuário.
        
        Args:
            user_id: ID do usuário
            company_id: ID da empresa
            
        Returns:
            UserResponse: Usuário desativado
        """
        user = await self._get_user_for_update(user_id, company_id)
        user.is_active = False
        
        await self.db.commit()
        await self.db.refresh(user)
        
        logger.info(f"User deactivated: {user.email}")
        
        return UserResponse.model_validate(user)
    
    async def change_role(
        self,
        user_id: int,
        new_role: UserRole,
        company_id: int,
        changed_by_id: int
    ) -> UserResponse:
        """
        Altera role do usuário.
        
        Args:
            user_id: ID do usuário
            new_role: Novo role
            company_id: ID da empresa
            changed_by_id: ID de quem está alterando
            
        Returns:
            UserResponse: Usuário atualizado
            
        Raises:
            InsufficientPermissions: Se não tem permissão
        """
        # Verifica permissão de quem está alterando
        changer_query = select(User).where(User.id == changed_by_id)
        changer_result = await self.db.execute(changer_query)
        changer = changer_result.scalar_one()
        
        if changer.role not in [UserRole.COMPANY_ADMIN, UserRole.SUPER_ADMIN]:
            raise InsufficientPermissions("Apenas administradores podem alterar roles")
        
        # Busca e atualiza usuário
        user = await self._get_user_for_update(user_id, company_id)
        
        # Validação especial para remover último admin
        if (user.role == UserRole.COMPANY_ADMIN and 
            new_role != UserRole.COMPANY_ADMIN):
            
            admin_count_query = select(func.count()).where(
                and_(
                    User.company_id == company_id,
                    User.role == UserRole.COMPANY_ADMIN,
                    User.is_active == True
                )
            )
            admin_count_result = await self.db.execute(admin_count_query)
            admin_count = admin_count_result.scalar()
            
            if admin_count <= 1:
                raise ValidationError(
                    "Não é possível remover o único administrador da empresa"
                )
        
        user.role = new_role
        
        await self.db.commit()
        await self.db.refresh(user)
        
        logger.info(f"User role changed: {user.email} to {new_role}")
        
        return UserResponse.model_validate(user)
    
    async def get_user_statistics(
        self,
        company_id: int
    ) -> Dict[str, Any]:
        """
        Obtém estatísticas de usuários da empresa.
        
        Args:
            company_id: ID da empresa
            
        Returns:
            dict: Estatísticas
        """
        # Total de usuários
        total_query = select(func.count()).where(
            and_(
                User.company_id == company_id,
                User.deleted_at.is_(None)
            )
        )
        total_result = await self.db.execute(total_query)
        total_users = total_result.scalar()
        
        # Usuários ativos
        active_query = select(func.count()).where(
            and_(
                User.company_id == company_id,
                User.is_active == True,
                User.deleted_at.is_(None)
            )
        )
        active_result = await self.db.execute(active_query)
        active_users = active_result.scalar()
        
        # Por role
        role_query = select(
            User.role,
            func.count().label('count')
        ).where(
            and_(
                User.company_id == company_id,
                User.deleted_at.is_(None)
            )
        ).group_by(User.role)
        
        role_result = await self.db.execute(role_query)
        users_by_role = {row.role: row.count for row in role_result}
        
        # Verificados
        verified_query = select(func.count()).where(
            and_(
                User.company_id == company_id,
                User.is_verified == True,
                User.deleted_at.is_(None)
            )
        )
        verified_result = await self.db.execute(verified_query)
        verified_users = verified_result.scalar()
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": total_users - active_users,
            "verified_users": verified_users,
            "users_by_role": users_by_role,
            "verification_rate": (verified_users / total_users * 100) if total_users > 0 else 0
        }
    
    # ==================== HELPERS ====================
    
    async def _get_user_for_update(
        self,
        user_id: int,
        company_id: int
    ) -> User:
        """
        Busca usuário para atualização com validação.
        
        Args:
            user_id: ID do usuário
            company_id: ID da empresa
            
        Returns:
            User: Usuário encontrado
            
        Raises:
            NotFoundError: Se não encontrado
            TenantAccessDenied: Se de outra empresa
        """
        query = select(User).where(User.id == user_id)
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise NotFoundError("User", user_id)
        
        if user.company_id != company_id:
            raise TenantAccessDenied()
        
        return user