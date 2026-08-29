from __future__ import annotations
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import create_engine
from .models import Base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./satiq.db")

def get_engine():
    # async engine for app; sync for alembic/create_all
    if DATABASE_URL.startswith("sqlite"):
        # need aiosqlite driver for async
        url = DATABASE_URL
        if "+aiosqlite" not in url:
            url = url.replace("sqlite://", "sqlite+aiosqlite://")
        return create_async_engine(url, echo=False)
    return create_async_engine(DATABASE_URL, echo=False)

engine = get_engine()
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

def sync_init_db(url: str | None = None):
    u = url or DATABASE_URL.replace("+asyncpg", "").replace("+aiosqlite", "")
    # sync engine for scripts
    if u.startswith("sqlite"):
        u = u.replace("sqlite+aiosqlite://", "sqlite://")
    eng = create_engine(u)
    Base.metadata.create_all(bind=eng)
    return eng
