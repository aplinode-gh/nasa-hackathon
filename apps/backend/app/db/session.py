"""Database connection pool and query helpers."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import asyncpg

from app.core.config import settings

_pool: asyncpg.Pool | None = None
_pool_lock = asyncio.Lock()


async def init_pool() -> asyncpg.Pool:
    """Initialize and return the global connection pool."""
    global _pool
    async with _pool_lock:
        if _pool is not None:
            return _pool
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL is not configured")
        _pool = await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=1,
            max_size=10,
            command_timeout=30,
        )
        return _pool


async def close_pool() -> None:
    """Close the global connection pool."""
    global _pool
    async with _pool_lock:
        if _pool is not None:
            await _pool.close()
            _pool = None


def get_pool() -> asyncpg.Pool:
    """Return the initialized pool."""
    if _pool is None:
        raise RuntimeError("Database pool is not initialized")
    return _pool


async def _run_with_retry(op):
    global _pool
    try:
        return await op()
    except (asyncpg.PostgresConnectionError, ConnectionResetError, OSError):
        async with _pool_lock:
            if _pool is not None:
                try:
                    await _pool.close()
                except Exception:
                    pass
                _pool = None
        await init_pool()
        return await op()


def _record_to_dict(record: asyncpg.Record) -> dict[str, Any]:
    return dict(record)


async def query(sql: str, *args: Any) -> list[dict[str, Any]]:
    """Execute a query and return all rows as dictionaries."""

    async def _exec():
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *args)
        return [_record_to_dict(r) for r in rows]

    return await _run_with_retry(_exec)


async def query_one(sql: str, *args: Any) -> dict[str, Any] | None:
    """Execute a query and return the first row or None."""

    async def _exec():
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(sql, *args)
        return _record_to_dict(row) if row else None

    return await _run_with_retry(_exec)


async def execute(sql: str, *args: Any) -> str:
    """Execute a statement and return status string."""

    async def _exec():
        pool = get_pool()
        async with pool.acquire() as conn:
            return await conn.execute(sql, *args)

    return await _run_with_retry(_exec)


@asynccontextmanager
async def transaction() -> AsyncIterator[asyncpg.Connection]:
    """Yield a connection inside a transaction."""
    pool = get_pool()
    async with pool.acquire() as conn:
        tx = conn.transaction()
        await tx.start()
        try:
            yield conn
            await tx.commit()
        except Exception:
            await tx.rollback()
            raise
