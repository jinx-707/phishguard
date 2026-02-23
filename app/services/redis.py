"""
Redis service for caching operations.
"""
from typing import Optional, Any, AsyncGenerator
import json
import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

# Global Redis connection pool
_redis_pool: Optional[ConnectionPool] = None


async def init_redis():
    """Initialize Redis connection pool."""
    global _redis_pool
    
    _redis_pool = ConnectionPool.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        max_connections=50,
    )
    
    # Test connection
    client = redis.Redis(connection_pool=_redis_pool)
    await client.ping()
    await client.close()
    logger.info("Redis connection pool initialized", url=settings.REDIS_URL)


async def close_redis():
    """Close Redis connection pool."""
    global _redis_pool
    if _redis_pool:
        await _redis_pool.disconnect()
        _redis_pool = None
        logger.info("Redis connection pool closed")


async def get_redis_client() -> AsyncGenerator[redis.Redis, None]:
    """
    Get Redis client from connection pool.
    Use as dependency injection or async context manager.
    """
    global _redis_pool
    if _redis_pool is None:
        await init_redis()
    
    client = redis.Redis(connection_pool=_redis_pool)
    try:
        yield client
    finally:
        await client.close()


async def get_cache(key: str) -> Optional[Any]:
    """Get value from cache."""
    async for client in get_redis_client():
        value = await client.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None


async def set_cache(key: str, value: Any, ttl: Optional[int] = None):
    """Set value in cache with optional TTL."""
    async for client in get_redis_client():
        if ttl is None:
            ttl = settings.REDIS_CACHE_TTL
        
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        
        await client.setex(key, ttl, value)


async def delete_cache(key: str):
    """Delete value from cache."""
    async for client in get_redis_client():
        await client.delete(key)


async def get_cache_ttl(key: str) -> int:
    """Get TTL for a key."""
    async for client in get_redis_client():
        return await client.ttl(key)


async def check_redis_health() -> bool:
    """Check if Redis is healthy."""
    try:
        async for client in get_redis_client():
            await client.ping()
            return True
    except Exception as e:
        logger.error("Redis health check failed", error=str(e))
        return False
