# CRUD empresas (multi-tenant)
"""
Service de gerenciamento de empresas (tenants) para o sistema WeatherBiz Analytics.
Implementa operações multi-tenant, planos e limites.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
import logging
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, update
from sqlalchemy.orm import selectinload

from app.models.company import Company, CompanyPlan, CompanyStatus
from app.models.user import User, UserRole
from app.models.weather import WeatherStation
from app.models.schemas import (
    CompanyCreate, CompanyUpdate, CompanyResponse,
    UserCreate, WeatherStationCreate
)
from app.config.settings import settings
from app.core.exceptions import (
    NotFoundError, DuplicateError, ValidationError,
    BusinessLogicError, PlanLimitExceeded
)
from app.core.utils import slugify, is_valid_cnpj

logger = logging.getLogger(__name__)


class CompanyService:
    """Service para gerenciamento de empresas."""
    
    def __init__(self, db: AsyncSession):
        """
        Inicializa o service.
        
        Args:
            db: Sessão do banco de dados
        """
        self.db = db
    
    async def get_company_by_id(
        self,
        company_id: int,
        include_stats: bool = False
    ) -> CompanyResponse:
        """
        Busca empresa por ID.
        
        Args:
            company_id: ID da empresa
            include_stats: Se deve incluir estatísticas
            
        Returns:
            CompanyResponse: Empresa encontrada
            
        Raises:
            NotFoundError: Se empresa não encontrada
        """
        query = select(Company).where(Company.id == company_id)
        result = await self.db.execute(query)
        company = result.scalar_one_or_none()
        
        if not company:
            raise NotFoundError("Company", company_id)
        
        response = CompanyResponse.model_validate(company)
        
        if include_stats:
            stats = await self.get_company_statistics(company_id)
            response.metadata = {**response.metadata, "stats": stats}
        
        return response
    
    async def get_company_by_slug(
        self,
        slug: str
    ) -> CompanyResponse:
        """
        Busca empresa por slug.
        
        Args:
            slug: Slug da empresa
            
        Returns:
            CompanyResponse: Empresa encontrada
            
        Raises:
            NotFoundError: Se empresa não encontrada
        """
        query = select(Company).where(Company.slug == slug)
        result = await self.db.execute(query)
        company = result.scalar_one_or_none()
        
        if not company:
            raise NotFoundError("Company", f"slug={slug}")
        
        return CompanyResponse.model_validate(company)
    
    async def create_company(
        self,
        company_data: CompanyCreate,
        owner_data: UserCreate
    ) -> CompanyResponse:
        """
        Cria nova empresa com usuário administrador.
        
        Args:
            company_data: Dados da empresa
            owner_data: Dados do usuário administrador
            
        Returns:
            CompanyResponse: Empresa criada
            
        Raises:
            DuplicateError: Se slug ou CNPJ já existem
            ValidationError: Se dados inválidos
        """
        # Valida CNPJ se fornecido
        if company_data.cnpj:
            if not is_valid_cnpj(company_data.cnpj):
                raise ValidationError("CNPJ inválido")
            
            # Verifica se CNPJ já existe
            cnpj_query = select(Company).where(Company.cnpj == company_data.cnpj)
            cnpj_result = await self.db.execute(cnpj_query)
            if cnpj_result.scalar_one_or_none():
                raise DuplicateError("Company", "cnpj", company_data.cnpj)
        
        # Gera slug único
        base_slug = slugify(company_data.slug or company_data.name)
        slug = await self._generate_unique_slug(base_slug)
        
        # Cria empresa
        company = Company(
            name=company_data.name,
            slug=slug,
            legal_name=company_data.legal_name,
            cnpj=company_data.cnpj,
            business_type=company_data.business_type,
            industry=company_data.industry,
            description=company_data.description,
            email=company_data.email,
            phone=company_data.phone,
            website=company_data.website,
            timezone=company_data.timezone,
            currency=company_data.currency,
            language=company_data.language,
            # Configurações de plano trial
            plan=CompanyPlan.FREE,
            status=CompanyStatus.TRIAL,
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=14),
            # Limites do plano
            max_users=settings.PLAN_LIMITS["free"]["max_users"],
            max_alerts=settings.PLAN_LIMITS["free"]["max_alerts"],
            max_api_calls_daily=settings.PLAN_LIMITS["free"]["max_api_calls_daily"],
            data_retention_days=settings.PLAN_LIMITS["free"]["data_retention_days"]
        )
        
        self.db.add(company)
        await self.db.flush()  # Para obter o ID
        
        # Cria usuário administrador
        admin_user = User(
            email=owner_data.email.lower(),
            username=owner_data.username,
            full_name=owner_data.full_name,
            phone=owner_data.phone,
            company_id=company.id,
            role=UserRole.COMPANY_ADMIN,
            timezone=owner_data.timezone or company.timezone,
            language=owner_data.language or company.language,
            hashed_password=get_password_hash(owner_data.password),
            is_active=True,
            is_verified=False,
            is_superuser=False
        )
        
        self.db.add(admin_user)
        
        # Cria estação meteorológica padrão se localização fornecida
        if hasattr(company_data, 'latitude') and company_data.latitude:
            weather_station = WeatherStation(
                company_id=company.id,
                name=f"{company.name} - Principal",
                latitude=company_data.latitude,
                longitude=company_data.longitude,
                city=company_data.address_city,
                state=company_data.address_state,
                country=company_data.address_country or "BR",
                is_primary=True
            )
            self.db.add(weather_station)
        
        # Atualiza contador
        company.current_users_count = 1
        
        await self.db.commit()
        await self.db.refresh(company)
        
        logger.info(f"Company created: {company.name} (ID: {company.id})")
        
        return CompanyResponse.model_validate(company)
    
    async def update_company(
        self,
        company_id: int,
        company_data: CompanyUpdate
    ) -> CompanyResponse:
        """
        Atualiza empresa.
        
        Args:
            company_id: ID da empresa
            company_data: Dados para atualizar
            
        Returns:
            CompanyResponse: Empresa atualizada
            
        Raises:
            NotFoundError: Se empresa não encontrada
        """
        company = await self._get_company_for_update(company_id)
        
        # Atualiza campos fornecidos
        update_data = company_data.model_dump(exclude_unset=True)
        
        for field, value in update_data.items():
            if hasattr(company, field):
                setattr(company, field, value)
        
        await self.db.commit()
        await self.db.refresh(company)
        
        logger.info(f"Company updated: {company.name}")
        
        return CompanyResponse.model_validate(company)
    
    async def upgrade_plan(
        self,
        company_id: int,
        new_plan: str,
        billing_period: str = "monthly"
    ) -> CompanyResponse:
        """
        Faz upgrade do plano da empresa.
        
        Args:
            company_id: ID da empresa
            new_plan: Novo plano
            billing_period: Período de cobrança
            
        Returns:
            CompanyResponse: Empresa com plano atualizado
            
        Raises:
            ValidationError: Se plano inválido
        """
        if new_plan not in settings.PLAN_LIMITS:
            raise ValidationError(f"Plano inválido: {new_plan}")
        
        company = await self._get_company_for_update(company_id)
        
        # Atualiza plano e limites
        company.upgrade_plan(new_plan)
        
        # Define período de assinatura
        if billing_period == "monthly":
            company.subscription_ends_at = datetime.now(timezone.utc) + timedelta(days=30)
        elif billing_period == "yearly":
            company.subscription_ends_at = datetime.now(timezone.utc) + timedelta(days=365)
        
        await self.db.commit()
        await self.db.refresh(company)
        
        logger.info(f"Company plan upgraded: {company.name} to {new_plan}")
        
        return CompanyResponse.model_validate(company)
    
    async def suspend_company(
        self,
        company_id: int,
        reason: Optional[str] = None
    ) -> CompanyResponse:
        """
        Suspende empresa.
        
        Args:
            company_id: ID da empresa
            reason: Motivo da suspensão
            
        Returns:
            CompanyResponse: Empresa suspensa
        """
        company = await self._get_company_for_update(company_id)
        
        company.status = CompanyStatus.SUSPENDED
        
        if reason:
            company.metadata = {
                **company.metadata,
                "suspension_reason": reason,
                "suspended_at": datetime.now(timezone.utc).isoformat()
            }
        
        # Desativa todos os usuários
        await self.db.execute(
            update(User)
            .where(User.company_id == company_id)
            .values(is_active=False)
        )
        
        await self.db.commit()
        await self.db.refresh(company)
        
        logger.warning(f"Company suspended: {company.name}")
        
        return CompanyResponse.model_validate(company)
    
    async def reactivate_company(
        self,
        company_id: int
    ) -> CompanyResponse:
        """
        Reativa empresa suspensa.
        
        Args:
            company_id: ID da empresa
            
        Returns:
            CompanyResponse: Empresa reativada
        """
        company = await self._get_company_for_update(company_id)
        
        if company.status != CompanyStatus.SUSPENDED:
            raise BusinessLogicError("Empresa não está suspensa")
        
        company.status = CompanyStatus.ACTIVE
        
        # Reativa usuários
        await self.db.execute(
            update(User)
            .where(
                and_(
                    User.company_id == company_id,
                    User.deleted_at.is_(None)
                )
            )
            .values(is_active=True)
        )
        
        await self.db.commit()
        await self.db.refresh(company)
        
        logger.info(f"Company reactivated: {company.name}")
        
        return CompanyResponse.model_validate(company)
    
    async def check_and_update_limits(
        self,
        company_id: int
    ) -> Dict[str, Any]:
        """
        Verifica e atualiza limites da empresa.
        
        Args:
            company_id: ID da empresa
            
        Returns:
            dict: Status dos limites
        """
        company = await self._get_company_for_update(company_id)
        
        # Verifica trial expirado
        if company.status == CompanyStatus.TRIAL:
            if company.trial_ends_at < datetime.now(timezone.utc):
                company.status = CompanyStatus.EXPIRED
                logger.warning(f"Company trial expired: {company.name}")
        
        # Reseta contadores diários
        if hasattr(company, 'last_reset_date'):
            last_reset = company.metadata.get('last_reset_date')
            today = datetime.now(timezone.utc).date()
            
            if not last_reset or last_reset != today.isoformat():
                company.reset_daily_counters()
                company.metadata = {
                    **company.metadata,
                    'last_reset_date': today.isoformat()
                }
        
        # Verifica limites
        limits_status = company.check_limits()
        
        await self.db.commit()
        
        return {
            "company_id": company_id,
            "plan": company.plan,
            "status": company.status,
            "limits": limits_status,
            "usage": company.usage_percentage
        }
    
    async def get_company_statistics(
        self,
        company_id: int
    ) -> Dict[str, Any]:
        """
        Obtém estatísticas da empresa.
        
        Args:
            company_id: ID da empresa
            
        Returns:
            dict: Estatísticas
        """
        company = await self._get_company_for_update(company_id)
        
        # Contagem de usuários
        users_query = select(func.count()).where(
            and_(
                User.company_id == company_id,
                User.deleted_at.is_(None)
            )
        )
        users_result = await self.db.execute(users_query)
        total_users = users_result.scalar()
        
        # Contagem de usuários ativos
        active_users_query = select(func.count()).where(
            and_(
                User.company_id == company_id,
                User.is_active == True,
                User.deleted_at.is_(None)
            )
        )
        active_users_result = await self.db.execute(active_users_query)
        active_users = active_users_result.scalar()
        
        # Outras estatísticas
        from app.models.sales import SalesData
        from app.models.alert import Alert
        
        # Total de vendas
        sales_query = select(func.sum(SalesData.revenue)).where(
            SalesData.company_id == company_id
        )
        sales_result = await self.db.execute(sales_query)
        total_revenue = sales_result.scalar() or Decimal(0)
        
        # Alertas ativos
        alerts_query = select(func.count()).where(
            and_(
                Alert.company_id == company_id,
                Alert.status.in_(["pending", "triggered"])
            )
        )
        alerts_result = await self.db.execute(alerts_query)
        active_alerts = alerts_result.scalar()
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "total_revenue": float(total_revenue),
            "active_alerts": active_alerts,
            "storage_used_mb": float(company.storage_used_mb),
            "api_calls_today": company.api_calls_today,
            "api_calls_month": company.api_calls_month,
            "plan": company.plan,
            "status": company.status,
            "trial_days_left": company.trial_days_left,
            "usage_percentage": company.usage_percentage,
            "created_at": company.created_at.isoformat(),
            "days_active": (datetime.now(timezone.utc) - company.created_at).days
        }
    
    async def add_weather_station(
        self,
        company_id: int,
        station_data: WeatherStationCreate
    ) -> WeatherStation:
        """
        Adiciona estação meteorológica para a empresa.
        
        Args:
            company_id: ID da empresa
            station_data: Dados da estação
            
        Returns:
            WeatherStation: Estação criada
        """
        # Se marcada como primária, remove flag das outras
        if station_data.is_primary:
            await self.db.execute(
                update(WeatherStation)
                .where(WeatherStation.company_id == company_id)
                .values(is_primary=False)
            )
        
        station = WeatherStation(
            company_id=company_id,
            **station_data.model_dump()
        )
        
        self.db.add(station)
        await self.db.commit()
        await self.db.refresh(station)
        
        logger.info(f"Weather station added for company {company_id}: {station.name}")
        
        return station
    
    async def update_onboarding_status(
        self,
        company_id: int,
        step: int,
        completed: bool = False
    ) -> CompanyResponse:
        """
        Atualiza status do onboarding.
        
        Args:
            company_id: ID da empresa
            step: Passo atual
            completed: Se completou onboarding
            
        Returns:
            CompanyResponse: Empresa atualizada
        """
        company = await self._get_company_for_update(company_id)
        
        company.onboarding_step = step
        company.onboarding_completed = completed
        
        if completed:
            company.metadata = {
                **company.metadata,
                "onboarding_completed_at": datetime.now(timezone.utc).isoformat()
            }
        
        await self.db.commit()
        await self.db.refresh(company)
        
        logger.info(f"Company onboarding updated: {company.name}, step {step}")
        
        return CompanyResponse.model_validate(company)
    
    async def delete_company(
        self,
        company_id: int,
        soft_delete: bool = True
    ) -> bool:
        """
        Exclui empresa e todos os dados relacionados.
        
        Args:
            company_id: ID da empresa
            soft_delete: Se deve fazer soft delete
            
        Returns:
            bool: Sucesso
        """
        company = await self._get_company_for_update(company_id)
        
        if soft_delete:
            # Soft delete
            company.deleted_at = datetime.now(timezone.utc)
            company.status = CompanyStatus.INACTIVE
            
            # Desativa todos os usuários
            await self.db.execute(
                update(User)
                .where(User.company_id == company_id)
                .values(is_active=False)
            )
        else:
            # Hard delete - cascata remove tudo
            await self.db.delete(company)
        
        await self.db.commit()
        
        logger.warning(f"Company deleted: {company.name}")
        
        return True
    
    # ==================== HELPERS ====================
    
    async def _get_company_for_update(self, company_id: int) -> Company:
        """
        Busca empresa para atualização.
        
        Args:
            company_id: ID da empresa
            
        Returns:
            Company: Empresa encontrada
            
        Raises:
            NotFoundError: Se não encontrada
        """
        query = select(Company).where(Company.id == company_id)
        result = await self.db.execute(query)
        company = result.scalar_one_or_none()
        
        if not company:
            raise NotFoundError("Company", company_id)
        
        return company
    
    async def _generate_unique_slug(self, base_slug: str) -> str:
        """
        Gera slug único para empresa.
        
        Args:
            base_slug: Slug base
            
        Returns:
            str: Slug único
        """
        slug = base_slug
        counter = 1
        
        while True:
            query = select(Company).where(Company.slug == slug)
            result = await self.db.execute(query)
            if not result.scalar_one_or_none():
                break
            
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        return slug