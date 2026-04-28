from __future__ import annotations

import ssl as _ssl

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import settings

# Strip ?ssl=require from URL (asyncpg doesn't support it as query param)
# and pass SSL context via connect_args instead.
_db_url = settings.DATABASE_URL.replace("?ssl=require", "").replace("&ssl=require", "")
_connect_args: dict = {}
if "asyncpg" in _db_url:
    _ssl_ctx = _ssl.create_default_context()
    _ssl_ctx.check_hostname = False
    _ssl_ctx.verify_mode = _ssl.CERT_NONE
    _connect_args["ssl"] = _ssl_ctx

engine = create_async_engine(_db_url, echo=settings.DEBUG, connect_args=_connect_args)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
