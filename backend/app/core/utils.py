# Utilitários gerais
"""
Utilitários gerais para o sistema Asterion.
Funções auxiliares reutilizáveis em todo o projeto.
"""

import re
import uuid
import hashlib
import random
import string
import json
import logging
from typing import Any, Dict, List, Optional, Union, TypeVar, Callable
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from functools import wraps
import asyncio
from time import time
import unicodedata
import phonenumbers
from email_validator import validate_email, EmailNotValidError

# Type hints
T = TypeVar('T')

# Logger
logger = logging.getLogger(__name__)


# ==================== STRING UTILITIES ====================

def normalize_string(text: str) -> str:
    """
    Normaliza string removendo acentos e caracteres especiais.
    
    Args:
        text: Texto a normalizar
        
    Returns:
        str: Texto normalizado
    """
    if not text:
        return ""
    
    # Remove acentos
    text = unicodedata.normalize('NFKD', text)
    text = ''.join([c for c in text if not unicodedata.combining(c)])
    
    # Converte para lowercase e remove espaços extras
    text = ' '.join(text.lower().split())
    
    return text


def slugify(text: str) -> str:
    """
    Converte texto em slug URL-friendly.
    
    Args:
        text: Texto a converter
        
    Returns:
        str: Slug
    """
    text = normalize_string(text)
    # Remove caracteres não-alfanuméricos
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    # Substitui espaços por hífens
    text = re.sub(r'[\s-]+', '-', text)
    # Remove hífens do início e fim
    return text.strip('-')


def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Trunca string para tamanho máximo.
    
    Args:
        text: Texto a truncar
        max_length: Comprimento máximo
        suffix: Sufixo a adicionar se truncado
        
    Returns:
        str: Texto truncado
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def mask_sensitive_data(data: str, visible_chars: int = 4) -> str:
    """
    Mascara dados sensíveis mantendo apenas alguns caracteres visíveis.
    
    Args:
        data: Dado a mascarar
        visible_chars: Número de caracteres visíveis no final
        
    Returns:
        str: Dado mascarado
    """
    if len(data) <= visible_chars:
        return "*" * len(data)
    
    masked_length = len(data) - visible_chars
    return "*" * masked_length + data[-visible_chars:]


def generate_random_string(
    length: int = 10,
    include_uppercase: bool = True,
    include_lowercase: bool = True,
    include_digits: bool = True,
    include_special: bool = False
) -> str:
    """
    Gera string aleatória com caracteres especificados.
    
    Args:
        length: Comprimento da string
        include_uppercase: Incluir letras maiúsculas
        include_lowercase: Incluir letras minúsculas
        include_digits: Incluir dígitos
        include_special: Incluir caracteres especiais
        
    Returns:
        str: String aleatória
    """
    chars = ""
    if include_uppercase:
        chars += string.ascii_uppercase
    if include_lowercase:
        chars += string.ascii_lowercase
    if include_digits:
        chars += string.digits
    if include_special:
        chars += "!@#$%^&*()_+-="
    
    if not chars:
        chars = string.ascii_letters + string.digits
    
    return ''.join(random.choice(chars) for _ in range(length))


# ==================== EMAIL & PHONE VALIDATION ====================

def is_valid_email(email: str) -> bool:
    """
    Valida endereço de email.
    
    Args:
        email: Email a validar
        
    Returns:
        bool: True se válido
    """
    try:
        validate_email(email)
        return True
    except EmailNotValidError:
        return False


def normalize_email(email: str) -> str:
    """
    Normaliza endereço de email.
    
    Args:
        email: Email a normalizar
        
    Returns:
        str: Email normalizado
    """
    try:
        validation = validate_email(email)
        return validation.email.lower()
    except EmailNotValidError:
        return email.lower()


def is_valid_phone(phone: str, country: str = "BR") -> bool:
    """
    Valida número de telefone.
    
    Args:
        phone: Número de telefone
        country: Código do país (padrão BR)
        
    Returns:
        bool: True se válido
    """
    try:
        parsed = phonenumbers.parse(phone, country)
        return phonenumbers.is_valid_number(parsed)
    except:
        return False


def format_phone(phone: str, country: str = "BR") -> str:
    """
    Formata número de telefone.
    
    Args:
        phone: Número de telefone
        country: Código do país
        
    Returns:
        str: Telefone formatado
    """
    try:
        parsed = phonenumbers.parse(phone, country)
        return phonenumbers.format_number(
            parsed,
            phonenumbers.PhoneNumberFormat.INTERNATIONAL
        )
    except:
        return phone


# ==================== DATE & TIME UTILITIES ====================

def get_current_timestamp() -> datetime:
    """
    Retorna timestamp atual com timezone UTC.
    
    Returns:
        datetime: Timestamp atual
    """
    return datetime.now(timezone.utc)


def format_datetime(
    dt: datetime,
    format_str: str = "%Y-%m-%d %H:%M:%S"
) -> str:
    """
    Formata datetime para string.
    
    Args:
        dt: Datetime a formatar
        format_str: String de formato
        
    Returns:
        str: Data formatada
    """
    if not dt:
        return ""
    
    return dt.strftime(format_str)


def parse_datetime(
    date_str: str,
    format_str: str = "%Y-%m-%d %H:%M:%S"
) -> Optional[datetime]:
    """
    Converte string para datetime.
    
    Args:
        date_str: String de data
        format_str: Formato esperado
        
    Returns:
        datetime ou None se inválido
    """
    try:
        return datetime.strptime(date_str, format_str)
    except (ValueError, TypeError):
        return None


def date_range(
    start_date: date,
    end_date: date,
    step: timedelta = timedelta(days=1)
) -> List[date]:
    """
    Gera lista de datas entre início e fim.
    
    Args:
        start_date: Data inicial
        end_date: Data final
        step: Intervalo entre datas
        
    Returns:
        list: Lista de datas
    """
    dates = []
    current_date = start_date
    
    while current_date <= end_date:
        dates.append(current_date)
        current_date += step
    
    return dates


def get_quarter(dt: datetime) -> int:
    """
    Retorna o trimestre de uma data.
    
    Args:
        dt: Data
        
    Returns:
        int: Trimestre (1-4)
    """
    return (dt.month - 1) // 3 + 1


def get_week_of_month(dt: datetime) -> int:
    """
    Retorna a semana do mês.
    
    Args:
        dt: Data
        
    Returns:
        int: Semana do mês (1-5)
    """
    first_day = dt.replace(day=1)
    dom = dt.day
    adjusted_dom = dom + first_day.weekday()
    
    return (adjusted_dom - 1) // 7 + 1


# ==================== UUID & ID GENERATION ====================

def generate_uuid() -> str:
    """
    Gera UUID v4.
    
    Returns:
        str: UUID
    """
    return str(uuid.uuid4())


def generate_short_id(length: int = 8) -> str:
    """
    Gera ID curto único.
    
    Args:
        length: Comprimento do ID
        
    Returns:
        str: ID curto
    """
    return uuid.uuid4().hex[:length]


def generate_order_number() -> str:
    """
    Gera número de pedido único.
    
    Returns:
        str: Número do pedido (ex: ORD-20240101-A1B2C3)
    """
    date_part = datetime.now().strftime("%Y%m%d")
    random_part = generate_short_id(6).upper()
    return f"ORD-{date_part}-{random_part}"


# ==================== HASH UTILITIES ====================

def hash_string(text: str, algorithm: str = "sha256") -> str:
    """
    Gera hash de uma string.
    
    Args:
        text: Texto a hashear
        algorithm: Algoritmo de hash
        
    Returns:
        str: Hash hexadecimal
    """
    h = hashlib.new(algorithm)
    h.update(text.encode())
    return h.hexdigest()


def generate_file_hash(file_path: Path, algorithm: str = "md5") -> str:
    """
    Gera hash de um arquivo.
    
    Args:
        file_path: Caminho do arquivo
        algorithm: Algoritmo de hash
        
    Returns:
        str: Hash do arquivo
    """
    h = hashlib.new(algorithm)
    
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    
    return h.hexdigest()


# ==================== JSON UTILITIES ====================

class DecimalEncoder(json.JSONEncoder):
    """Encoder JSON que suporta Decimal."""
    
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


def safe_json_dumps(obj: Any, **kwargs) -> str:
    """
    Serializa objeto para JSON com suporte a tipos especiais.
    
    Args:
        obj: Objeto a serializar
        **kwargs: Argumentos adicionais para json.dumps
        
    Returns:
        str: JSON string
    """
    return json.dumps(obj, cls=DecimalEncoder, **kwargs)


def safe_json_loads(json_str: str) -> Any:
    """
    Deserializa JSON com tratamento de erro.
    
    Args:
        json_str: String JSON
        
    Returns:
        Objeto deserializado ou None se inválido
    """
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return None


# ==================== VALIDATION UTILITIES ====================

def is_valid_cpf(cpf: str) -> bool:
    """
    Valida CPF brasileiro.
    
    Args:
        cpf: CPF a validar
        
    Returns:
        bool: True se válido
    """
    # Remove caracteres não numéricos
    cpf = re.sub(r'[^0-9]', '', cpf)
    
    if len(cpf) != 11:
        return False
    
    # Verifica se todos os dígitos são iguais
    if cpf == cpf[0] * 11:
        return False
    
    # Valida primeiro dígito
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    digito1 = (soma * 10) % 11
    if digito1 == 10:
        digito1 = 0
    
    if int(cpf[9]) != digito1:
        return False
    
    # Valida segundo dígito
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    digito2 = (soma * 10) % 11
    if digito2 == 10:
        digito2 = 0
    
    return int(cpf[10]) == digito2


def is_valid_cnpj(cnpj: str) -> bool:
    """
    Valida CNPJ brasileiro.
    
    Args:
        cnpj: CNPJ a validar
        
    Returns:
        bool: True se válido
    """
    # Remove caracteres não numéricos
    cnpj = re.sub(r'[^0-9]', '', cnpj)
    
    if len(cnpj) != 14:
        return False
    
    # Verifica se todos os dígitos são iguais
    if cnpj == cnpj[0] * 14:
        return False
    
    # Peso para validação
    peso = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    
    # Valida primeiro dígito
    soma = sum(int(cnpj[i]) * peso[i] for i in range(12))
    digito1 = 11 - (soma % 11)
    if digito1 >= 10:
        digito1 = 0
    
    if int(cnpj[12]) != digito1:
        return False
    
    # Valida segundo dígito
    peso.insert(0, 6)
    soma = sum(int(cnpj[i]) * peso[i] for i in range(13))
    digito2 = 11 - (soma % 11)
    if digito2 >= 10:
        digito2 = 0
    
    return int(cnpj[13]) == digito2


# ==================== PAGINATION UTILITIES ====================

def paginate(
    items: List[T],
    page: int = 1,
    page_size: int = 20
) -> Dict[str, Any]:
    """
    Pagina lista de itens.
    
    Args:
        items: Lista de itens
        page: Número da página (1-indexed)
        page_size: Tamanho da página
        
    Returns:
        dict: Dados paginados
    """
    total = len(items)
    total_pages = (total + page_size - 1) // page_size
    
    start = (page - 1) * page_size
    end = start + page_size
    
    return {
        "items": items[start:end],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1
    }


# ==================== FILE UTILITIES ====================

def get_file_extension(filename: str) -> str:
    """
    Obtém extensão de arquivo.
    
    Args:
        filename: Nome do arquivo
        
    Returns:
        str: Extensão (sem ponto)
    """
    return Path(filename).suffix.lstrip('.')


def sanitize_filename(filename: str) -> str:
    """
    Sanitiza nome de arquivo removendo caracteres perigosos.
    
    Args:
        filename: Nome do arquivo
        
    Returns:
        str: Nome sanitizado
    """
    # Remove path traversal
    filename = filename.replace('..', '')
    filename = filename.replace('/', '')
    filename = filename.replace('\\', '')
    
    # Remove caracteres especiais
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    
    # Limita comprimento
    name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
    if len(name) > 100:
        name = name[:100]
    
    return f"{name}.{ext}" if ext else name


def format_file_size(size_bytes: int) -> str:
    """
    Formata tamanho de arquivo para formato legível.
    
    Args:
        size_bytes: Tamanho em bytes
        
    Returns:
        str: Tamanho formatado (ex: "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    
    return f"{size_bytes:.1f} PB"


# ==================== DECORATORS ====================

def timing_decorator(func: Callable) -> Callable:
    """
    Decorator para medir tempo de execução.
    
    Args:
        func: Função a decorar
        
    Returns:
        Função decorada
    """
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start = time()
        result = await func(*args, **kwargs)
        elapsed = time() - start
        logger.debug(f"{func.__name__} levou {elapsed:.3f}s")
        return result
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        start = time()
        result = func(*args, **kwargs)
        elapsed = time() - start
        logger.debug(f"{func.__name__} levou {elapsed:.3f}s")
        return result
    
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


def retry_decorator(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0
) -> Callable:
    """
    Decorator para retry automático.
    
    Args:
        max_attempts: Número máximo de tentativas
        delay: Delay inicial entre tentativas
        backoff: Fator de multiplicação do delay
        
    Returns:
        Decorator
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    logger.warning(
                        f"{func.__name__} falhou (tentativa {attempt + 1}/{max_attempts}): {e}"
                    )
            
            raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        asyncio.sleep(current_delay)
                        current_delay *= backoff
                    logger.warning(
                        f"{func.__name__} falhou (tentativa {attempt + 1}/{max_attempts}): {e}"
                    )
            
            raise last_exception
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# ==================== MATH UTILITIES ====================

def round_decimal(value: Decimal, places: int = 2) -> Decimal:
    """
    Arredonda decimal para número de casas especificado.
    
    Args:
        value: Valor decimal
        places: Número de casas decimais
        
    Returns:
        Decimal: Valor arredondado
    """
    quantizer = Decimal(10) ** -places
    return value.quantize(quantizer)


def calculate_percentage(part: float, whole: float) -> float:
    """
    Calcula porcentagem.
    
    Args:
        part: Parte
        whole: Total
        
    Returns:
        float: Porcentagem
    """
    if whole == 0:
        return 0.0
    
    return (part / whole) * 100


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Divisão segura com valor padrão para divisão por zero.
    
    Args:
        numerator: Numerador
        denominator: Denominador
        default: Valor padrão se denominador for zero
        
    Returns:
        float: Resultado da divisão
    """
    if denominator == 0:
        return default
    
    return numerator / denominator


# Export
__all__ = [
    # String
    "normalize_string",
    "slugify",
    "truncate_string",
    "mask_sensitive_data",
    "generate_random_string",
    
    # Email & Phone
    "is_valid_email",
    "normalize_email",
    "is_valid_phone",
    "format_phone",
    
    # Date & Time
    "get_current_timestamp",
    "format_datetime",
    "parse_datetime",
    "date_range",
    "get_quarter",
    "get_week_of_month",
    
    # UUID & ID
    "generate_uuid",
    "generate_short_id",
    "generate_order_number",
    
    # Hash
    "hash_string",
    "generate_file_hash",
    
    # JSON
    "DecimalEncoder",
    "safe_json_dumps",
    "safe_json_loads",
    
    # Validation
    "is_valid_cpf",
    "is_valid_cnpj",
    
    # Pagination
    "paginate",
    
    # Files
    "get_file_extension",
    "sanitize_filename",
    "format_file_size",
    
    # Decorators
    "timing_decorator",
    "retry_decorator",
    
    # Math
    "round_decimal",
    "calculate_percentage",
    "safe_divide"
]