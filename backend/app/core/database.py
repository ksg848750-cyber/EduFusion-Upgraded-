from contextlib import asynccontextmanager

from psycopg_pool import AsyncConnectionPool

from app.core.config import get_settings

_pool: AsyncConnectionPool | None = None


async def init_pool() -> None:
    global _pool
    settings = get_settings()
    if not settings.database_url:
        return
    _pool = AsyncConnectionPool(
        settings.database_url,
        open=False,
        min_size=1,
        max_size=5,
        timeout=30,
    )
    await _pool.open()
    await _pool.wait()


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> AsyncConnectionPool | None:
    return _pool


@asynccontextmanager
async def connection():
    """Yield a connection from the pool (or None when DB is unconfigured)."""
    pool = get_pool()
    if pool is None:
        yield None
        return
    async with pool.connection() as conn:
        yield conn
