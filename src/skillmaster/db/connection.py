import asyncpg

from skillmaster.config import settings

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool | None:
    """Get or create the NeonDB connection pool. Returns None if not configured."""
    global _pool
    if not settings.neondb_url:
        return None
    if _pool is None:
        _pool = await asyncpg.create_pool(settings.neondb_url, min_size=1, max_size=5)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
