from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Add new columns to existing tables (safe: IF NOT EXISTS)
        await conn.execute(text(
            "ALTER TABLE episodes ADD COLUMN IF NOT EXISTS servcey1_msg_id INTEGER"
        ))
        # TMCooper : lien de lecture résolu + date du dernier rafraîchissement
        await conn.execute(text(
            "ALTER TABLE episodes ADD COLUMN IF NOT EXISTS stream_url TEXT"
        ))
        await conn.execute(text(
            "ALTER TABLE episodes ADD COLUMN IF NOT EXISTS stream_type VARCHAR(10)"
        ))
        await conn.execute(text(
            "ALTER TABLE episodes ADD COLUMN IF NOT EXISTS links_refreshed_at TIMESTAMPTZ"
        ))
        await conn.execute(text(
            "ALTER TABLE episodes ADD COLUMN IF NOT EXISTS thumb_msg_id INTEGER"
        ))
        # Catégorie : « anime » (animation) ou « live » (films et séries avec de vrais acteurs)
        await conn.execute(text(
            "ALTER TABLE animes ADD COLUMN IF NOT EXISTS category VARCHAR(10) NOT NULL DEFAULT 'anime'"
        ))
        # Type d'emplacement (saison, saga, film, oav...) pour les filtres et les icônes
        await conn.execute(text(
            "ALTER TABLE anime_seasons ADD COLUMN IF NOT EXISTS kind VARCHAR(16)"
        ))
        await conn.execute(text(
            "UPDATE anime_seasons SET kind = CASE "
            "WHEN api_season LIKE 'saison%' THEN 'saison' "
            "WHEN api_season LIKE 'saga%' THEN 'saga' "
            "WHEN api_season LIKE 'film%' THEN 'film' "
            "WHEN api_season LIKE 'oav%' THEN 'oav' "
            "WHEN api_season LIKE 'special%' THEN 'special' "
            "ELSE 'autre' END WHERE kind IS NULL"
        ))


async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
