# Lógica de autenticação/JWT
"""
Service de autenticação para o sistema WeatherBiz Analytics.
Gerencia login, tokens JWT, refresh tokens e reset de senha.
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone
import secrets
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from jose import JWTError

from app.models.user import User
from app.models.company import Company
from app.models.schemas import (
    UserCreate, UserResponse, LoginRequest,
    TokenResponse, PasswordReset
)
from app.config.settings import settings
from app.config.security import (
    verify_password, get_password_hash,
    create_access_token, create_refresh_token,
    decode_token, TokenType, UserRole
)
from app.core.exceptions import (
    InvalidCredentials, TokenExpired, InvalidToken,
    NotFoundError, ValidationError, AuthenticationError
)
from app.integrations.notifications.email import EmailService

logger = logging.getLogger(__name__)


class AuthService:
    """Service para autenticação e autorização."""
    
    def __init__(self, db: AsyncSession):
        """
        Inicializa o service.
        
        Args:
            db: Sessão do banco de dados
        """
        self.db = db
        self.email_service = EmailService()
    
    async def login(self, credentials: LoginRequest) -> TokenResponse:
        """
        Realiza login do usuário.
        
        Args:
            credentials: Credenciais de login
            
        Returns:
            TokenResponse: Tokens de acesso
            
        Raises:
            InvalidCredentials: Se credenciais inválidas
            AuthenticationError: Se conta bloqueada
        """
        # Busca usuário
        query = select(User).where(
            User.email == credentials.email.lower()
        )
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            logger.warning(f"Login attempt for non-existent user: {credentials.email}")
            raise InvalidCredentials()
        
        # Verifica se conta está bloqueada
        if user.is_locked:
            logger.warning(f"Login attempt for locked account: {user.email}")
            raise AuthenticationError("Conta bloqueada. Tente novamente mais tarde")
        
        # Verifica senha
        if not user.verify_password(credentials.password):
            user.increment_failed_login()
            await self.db.commit()
            logger.warning(f"Invalid password for user: {user.email}")
            raise InvalidCredentials()
        
        # Verifica se usuário está ativo
        if not user.is_active:
            raise AuthenticationError("Conta desativada")
        
        # Verifica se email foi verificado
        if not user.is_verified and not settings.DEBUG:
            raise AuthenticationError("Email não verificado. Verifique sua caixa de entrada")
        
        # Atualiza último login
        user.update_last_login(
            ip_address=credentials.ip_address if hasattr(credentials, 'ip_address') else None
        )
        
        # Gera tokens
        access_token = create_access_token(
            user_id=user.id,
            company_id=user.company_id,
            role=user.role
        )
        
        refresh_token = create_refresh_token(
            user_id=user.id,
            company_id=user.company_id
        )
        
        # Salva refresh token
        user.refresh_token = refresh_token
        await self.db.commit()
        
        logger.info(f"Successful login for user: {user.email}")
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    
    async def register(
        self,
        user_data: UserCreate,
        create_company: bool = False
    ) -> UserResponse:
        """
        Registra novo usuário.
        
        Args:
            user_data: Dados do usuário
            create_company: Se deve criar nova empresa
            
        Returns:
            UserResponse: Usuário criado
            
        Raises:
            ValidationError: Se dados inválidos
        """
        # Verifica se email já existe
        query = select(User).where(User.email == user_data.email.lower())
        result = await self.db.execute(query)
        if result.scalar_one_or_none():
            raise ValidationError(
                "Email já cadastrado",
                fields={"email": "Este email já está em uso"}
            )
        
        # Se deve criar empresa
        company_id = user_data.company_id
        if create_company:
            company = Company(
                name=user_data.full_name + "'s Company",
                slug=user_data.email.split('@')[0] + "-company",
                email=user_data.email,
                timezone=user_data.timezone,
                language=user_data.language,
                plan="trial",
                status="trial",
                trial_ends_at=datetime.now(timezone.utc) + timedelta(days=14)
            )
            self.db.add(company)
            await self.db.flush()  # Para obter o ID
            company_id = company.id
            
            # Primeiro usuário vira admin
            user_data.role = UserRole.COMPANY_ADMIN
        
        if not company_id:
            raise ValidationError("company_id é obrigatório")
        
        # Cria usuário
        user = User(
            email=user_data.email.lower(),
            username=user_data.username,
            full_name=user_data.full_name,
            phone=user_data.phone,
            company_id=company_id,
            role=user_data.role,
            timezone=user_data.timezone,
            language=user_data.language,
            hashed_password=get_password_hash(user_data.password),
            is_active=True,
            is_verified=False  # Precisa verificar email
        )
        
        # Gera token de verificação de email
        user.email_verification_token = secrets.token_urlsafe(32)
        
        self.db.add(user)
        
        # Atualiza contador da empresa
        company_query = select(Company).where(Company.id == company_id)
        company_result = await self.db.execute(company_query)
        company = company_result.scalar_one()
        company.current_users_count += 1
        
        await self.db.commit()
        await self.db.refresh(user)
        
        # Envia email de verificação
        await self._send_verification_email(user)
        
        logger.info(f"New user registered: {user.email}")
        
        return UserResponse.model_validate(user)
    
    async def refresh_access_token(self, refresh_token: str) -> TokenResponse:
        """
        Gera novo access token usando refresh token.
        
        Args:
            refresh_token: Refresh token
            
        Returns:
            TokenResponse: Novo access token
            
        Raises:
            InvalidToken: Se token inválido
        """
        try:
            # Decodifica refresh token
            payload = decode_token(refresh_token, TokenType.REFRESH)
            user_id = int(payload.get("sub"))
            
            # Busca usuário
            query = select(User).where(
                and_(
                    User.id == user_id,
                    User.refresh_token == refresh_token
                )
            )
            result = await self.db.execute(query)
            user = result.scalar_one_or_none()
            
            if not user:
                raise InvalidToken()
            
            if not user.is_active:
                raise AuthenticationError("Conta desativada")
            
            # Gera novo access token
            access_token = create_access_token(
                user_id=user.id,
                company_id=user.company_id,
                role=user.role
            )
            
            # Opcionalmente, gera novo refresh token
            new_refresh_token = create_refresh_token(
                user_id=user.id,
                company_id=user.company_id
            )
            
            user.refresh_token = new_refresh_token
            await self.db.commit()
            
            return TokenResponse(
                access_token=access_token,
                refresh_token=new_refresh_token,
                token_type="bearer",
                expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
            )
            
        except (JWTError, ValueError) as e:
            logger.error(f"Invalid refresh token: {e}")
            raise InvalidToken()
    
    async def logout(self, user_id: int) -> bool:
        """
        Realiza logout do usuário.
        
        Args:
            user_id: ID do usuário
            
        Returns:
            bool: Sucesso
        """
        query = select(User).where(User.id == user_id)
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()
        
        if user:
            user.refresh_token = None
            await self.db.commit()
            logger.info(f"User logged out: {user.email}")
            return True
        
        return False
    
    async def request_password_reset(self, email: str) -> bool:
        """
        Solicita reset de senha.
        
        Args:
            email: Email do usuário
            
        Returns:
            bool: Sucesso (sempre True por segurança)
        """
        # Sempre retorna True para não revelar se email existe
        query = select(User).where(User.email == email.lower())
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()
        
        if user:
            # Gera token de reset
            user.reset_password_token = secrets.token_urlsafe(32)
            user.reset_password_expires = datetime.now(timezone.utc) + timedelta(hours=1)
            
            await self.db.commit()
            
            # Envia email
            await self._send_password_reset_email(user)
            
            logger.info(f"Password reset requested for: {user.email}")
        
        return True
    
    async def reset_password(self, reset_data: PasswordReset) -> bool:
        """
        Reseta senha do usuário.
        
        Args:
            reset_data: Dados de reset
            
        Returns:
            bool: Sucesso
            
        Raises:
            InvalidToken: Se token inválido ou expirado
        """
        query = select(User).where(
            User.reset_password_token == reset_data.token
        )
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise InvalidToken()
        
        # Verifica se token expirou
        if user.reset_password_expires < datetime.now(timezone.utc):
            raise TokenExpired()
        
        # Atualiza senha
        user.set_password(reset_data.new_password)
        
        await self.db.commit()
        
        # Envia confirmação por email
        await self._send_password_changed_email(user)
        
        logger.info(f"Password reset completed for: {user.email}")
        
        return True
    
    async def verify_email(self, token: str) -> bool:
        """
        Verifica email do usuário.
        
        Args:
            token: Token de verificação
            
        Returns:
            bool: Sucesso
            
        Raises:
            InvalidToken: Se token inválido
        """
        query = select(User).where(
            User.email_verification_token == token
        )
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise InvalidToken()
        
        user.is_verified = True
        user.email_verification_token = None
        
        await self.db.commit()
        
        logger.info(f"Email verified for: {user.email}")
        
        return True
    
    async def change_password(
        self,
        user_id: int,
        current_password: str,
        new_password: str
    ) -> bool:
        """
        Altera senha do usuário.
        
        Args:
            user_id: ID do usuário
            current_password: Senha atual
            new_password: Nova senha
            
        Returns:
            bool: Sucesso
            
        Raises:
            InvalidCredentials: Se senha atual incorreta
        """
        query = select(User).where(User.id == user_id)
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise NotFoundError("User", user_id)
        
        # Verifica senha atual
        if not user.verify_password(current_password):
            raise InvalidCredentials()
        
        # Atualiza senha
        user.set_password(new_password)
        
        await self.db.commit()
        
        # Envia confirmação
        await self._send_password_changed_email(user)
        
        logger.info(f"Password changed for: {user.email}")
        
        return True
    
    async def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Valida access token.
        
        Args:
            token: Access token
            
        Returns:
            dict: Payload do token
            
        Raises:
            InvalidToken: Se token inválido
        """
        try:
            payload = decode_token(token, TokenType.ACCESS)
            
            # Verifica se usuário ainda existe e está ativo
            user_id = int(payload.get("sub"))
            query = select(User).where(
                and_(
                    User.id == user_id,
                    User.is_active == True
                )
            )
            result = await self.db.execute(query)
            user = result.scalar_one_or_none()
            
            if not user:
                raise InvalidToken()
            
            return payload
            
        except (JWTError, ValueError) as e:
            logger.error(f"Invalid access token: {e}")
            raise InvalidToken()
    
    # ==================== EMAIL HELPERS ====================
    
    async def _send_verification_email(self, user: User) -> None:
        """Envia email de verificação."""
        verification_url = f"{settings.FRONTEND_URL}/verify-email?token={user.email_verification_token}"
        
        await self.email_service.send_email(
            to=user.email,
            subject="Verifique seu email - WeatherBiz Analytics",
            template="email_verification",
            context={
                "user_name": user.full_name,
                "verification_url": verification_url
            }
        )
    
    async def _send_password_reset_email(self, user: User) -> None:
        """Envia email de reset de senha."""
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={user.reset_password_token}"
        
        await self.email_service.send_email(
            to=user.email,
            subject="Reset de Senha - WeatherBiz Analytics",
            template="password_reset",
            context={
                "user_name": user.full_name,
                "reset_url": reset_url,
                "expires_in": "1 hora"
            }
        )
    
    async def _send_password_changed_email(self, user: User) -> None:
        """Envia email de confirmação de mudança de senha."""
        await self.email_service.send_email(
            to=user.email,
            subject="Senha Alterada - WeatherBiz Analytics",
            template="password_changed",
            context={
                "user_name": user.full_name,
                "changed_at": datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")
            }
        )