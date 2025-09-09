# ===========================
# backend/app/core/cache.py (NOVO)
# ===========================
"""
Redis cache configuration
"""

import redis.asyncio as redis
from typing import Optional, Any
import json
import pickle
from datetime import timedelta

from app.core.config import settings

# Redis client
redis_client = redis.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True
)


class CacheService:
    """
    Service for caching with Redis
    """
    
    def __init__(self, prefix: str = "weatherbiz"):
        self.prefix = prefix
        self.client = redis_client
    
    def _make_key(self, key: str) -> str:
        """Create namespaced key"""
        return f"{self.prefix}:{key}"
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            value = await self.client.get(self._make_key(key))
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning(f"Cache get error: {e}")
            return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        expire: Optional[int] = None
    ) -> bool:
        """Set value in cache"""
        try:
            serialized = json.dumps(value)
            return await self.client.set(
                self._make_key(key),
                serialized,
                ex=expire
            )
        except Exception as e:
            logger.warning(f"Cache set error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete from cache"""
        try:
            return await self.client.delete(self._make_key(key)) > 0
        except Exception as e:
            logger.warning(f"Cache delete error: {e}")
            return False
    
    async def get_or_set(
        self,
        key: str,
        factory,
        expire: Optional[int] = None
    ) -> Any:
        """Get from cache or set if not exists"""
        value = await self.get(key)
        if value is None:
            value = await factory() if asyncio.iscoroutinefunction(factory) else factory()
            await self.set(key, value, expire)
        return value
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching pattern"""
        try:
            keys = await self.client.keys(f"{self.prefix}:{pattern}")
            if keys:
                return await self.client.delete(*keys)
            return 0
        except Exception as e:
            logger.warning(f"Cache invalidate error: {e}")
            return 0


# Cache instance for tenant-specific data
cache_service = CacheService()


# Cache decorators
def cache_result(expire: int = 300, key_prefix: str = None):
    """
    Decorator to cache function results
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{key_prefix or func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Try to get from cache
            cached = await cache_service.get(cache_key)
            if cached is not None:
                return cached
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache result
            await cache_service.set(cache_key, result, expire)
            
            return result
        
        return wrapper
    return decorator
