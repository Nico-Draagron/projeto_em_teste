# ===========================
# backend/app/integrations/utils.py
# ===========================
"""
Utility functions for integrations
"""

import hashlib
import hmac
from typing import Dict, Any, Optional
import json
from datetime import datetime, timedelta
from functools import wraps
import asyncio

import logging

logger = logging.getLogger(__name__)


def verify_webhook_signature(
    payload: bytes,
    signature: str,
    secret: str,
    algorithm: str = "sha256"
) -> bool:
    """
    Verify webhook signature for security
    """
    expected_signature = hmac.new(
        secret.encode(),
        payload,
        getattr(hashlib, algorithm)
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)


def retry_on_failure(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator to retry function on failure
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            attempt = 0
            current_delay = delay
            
            while attempt < max_attempts:
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        logger.error(f"Max retries reached for {func.__name__}: {str(e)}")
                        raise
                    
                    logger.warning(f"Attempt {attempt} failed for {func.__name__}: {str(e)}")
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            attempt = 0
            current_delay = delay
            
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        logger.error(f"Max retries reached for {func.__name__}: {str(e)}")
                        raise
                    
                    logger.warning(f"Attempt {attempt} failed for {func.__name__}: {str(e)}")
                    import time
                    time.sleep(current_delay)
                    current_delay *= backoff
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class RateLimiter:
    """
    Simple rate limiter for API calls
    """
    
    def __init__(self, calls: int, period: timedelta):
        self.calls = calls
        self.period = period
        self.timestamps = []
    
    async def acquire(self):
        """
        Wait if necessary to respect rate limit
        """
        now = datetime.utcnow()
        
        # Remove old timestamps
        cutoff = now - self.period
        self.timestamps = [ts for ts in self.timestamps if ts > cutoff]
        
        # Check if we need to wait
        if len(self.timestamps) >= self.calls:
            oldest = self.timestamps[0]
            sleep_time = (oldest + self.period - now).total_seconds()
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
                return await self.acquire()  # Retry after sleeping
        
        # Add current timestamp
        self.timestamps.append(now)


def sanitize_phone_number(phone: str, country_code: str = "55") -> str:
    """
    Sanitize and format phone number
    """
    # Remove all non-numeric characters
    phone = ''.join(filter(str.isdigit, phone))
    
    # Remove leading zeros
    phone = phone.lstrip('0')
    
    # Add country code if not present
    if not phone.startswith(country_code):
        phone = country_code + phone
    
    # Validate length (Brazil example)
    if country_code == "55" and len(phone) not in [12, 13]:  # 55 + 2 area + 8-9 number
        raise ValueError(f"Invalid phone number length: {phone}")
    
    return phone


def parse_webhook_timestamp(timestamp: Any) -> datetime:
    """
    Parse webhook timestamp from various formats
    """
    if isinstance(timestamp, datetime):
        return timestamp
    
    if isinstance(timestamp, (int, float)):
        # Assume Unix timestamp
        return datetime.fromtimestamp(timestamp)
    
    if isinstance(timestamp, str):
        # Try common formats
        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",  # ISO with microseconds
            "%Y-%m-%dT%H:%M:%SZ",      # ISO without microseconds
            "%Y-%m-%d %H:%M:%S",        # Simple format
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(timestamp, fmt)
            except ValueError:
                continue
        
        raise ValueError(f"Unable to parse timestamp: {timestamp}")
    
    raise TypeError(f"Unsupported timestamp type: {type(timestamp)}")