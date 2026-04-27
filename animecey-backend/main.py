"""AnimeCey — FastAPI + Pyrogram entrypoint.

Runs both the FastAPI web server and the Pyrogram Telegram bot in the
same asyncio event loop.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("animecey")


async def _ensure_admin():
    """Create default admin account if none exists."""
    from sqlalchemy import select
    from database import async_session
    from models import User, UserRole
    from auth import hash_password

    async with async_session() as db:
        result = await db.execute(select(User).where(User.role == UserRole.admin))
        if result.scalar_one_or_none() is None:
            admin = User(
                username="admin",
                email="admin@animecey.app",
                password_hash=hash_password("m@cabre"),
                role=UserRole.admin,
            )
            db.add(admin)
            await db.commit()
            logger.info("Default admin created — admin@animecey.app")
        else:
            logger.info("Admin account already exists, skipping.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initialising database...")
    await init_db()
    await _ensure_admin()

    bot_running = False
    if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_API_ID:
        try:
            from bot.client import bot
            from bot.handlers import register_all

            register_all(bot)

            logger.info("Starting Telegram bot...")
            await bot.start()
            bot_running = True
            logger.info("Bot started: @%s", bot.me.username if bot.me else "unknown")
        except Exception as exc:
            logger.warning("Telegram bot failed to start: %s. API will run without bot.", exc)
    else:
        logger.info("Telegram credentials not configured. Bot disabled.")

    yield

    if bot_running:
        logger.info("Stopping Telegram bot...")
        from bot.client import bot
        await bot.stop()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="AnimeCey API",
    version="1.0.0",
    description="API backend for AnimeCey anime streaming platform",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────

from routers import admin, anilist, animes, auth, comments, episodes, folders, notifications, push, search, tmdb, users  # noqa: E402

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(animes.router, prefix="/api/animes", tags=["Animes"])
app.include_router(episodes.router, prefix="/api/episodes", tags=["Episodes"])
app.include_router(comments.router, prefix="/api/comments", tags=["Comments"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["Notifications"])
app.include_router(push.router, prefix="/api/push", tags=["Push"])
app.include_router(search.router, prefix="/api/search", tags=["Search"])
app.include_router(folders.router, prefix="/api/admin/folders", tags=["Admin - Folders"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(tmdb.router, prefix="/api/tmdb", tags=["TMDB"])
app.include_router(anilist.router, prefix="/api/anilist", tags=["AniList"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
