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
    """Crée le compte admin par défaut s'il n'existe aucun admin.

    Ne doit JAMAIS empêcher l'application de démarrer : si le compte existe déjà
    sous un autre rôle, ou si une autre instance l'a créé en même temps, on le
    signale dans les logs et on continue.
    """
    from sqlalchemy import or_, select
    from sqlalchemy.exc import IntegrityError
    from database import async_session
    from models import User, UserRole
    from auth import hash_password

    admin_email = os.getenv("ADMIN_EMAIL", "admin@animecey.app")
    admin_password = os.getenv("ADMIN_PASSWORD")
    if not admin_password:
        logger.warning(
            "ADMIN_PASSWORD n'est pas défini : mot de passe par défaut utilisé. "
            "Définis ADMIN_PASSWORD dans les variables d'environnement."
        )
        admin_password = "m@cabre"

    async with async_session() as db:
        has_admin = (
            await db.execute(select(User.id).where(User.role == UserRole.admin).limit(1))
        ).first()
        if has_admin:
            logger.info("Admin account already exists, skipping.")
            return

        taken = (
            await db.execute(
                select(User.id, User.role)
                .where(or_(User.username == "admin", User.email == admin_email))
                .limit(1)
            )
        ).first()
        if taken:
            # On ne promeut jamais automatiquement ce compte : l'inscription est ouverte,
            # il pourrait appartenir à quelqu'un d'autre.
            logger.warning(
                "Aucun compte n'a le rôle admin, mais le compte id=%s (rôle actuel : %s) occupe "
                "déjà le nom « admin » ou l'email %s. Création ignorée. Si ce compte est le tien : "
                "UPDATE users SET role='admin' WHERE id=%s;",
                taken.id, getattr(taken.role, "value", taken.role), admin_email, taken.id,
            )
            return

        db.add(
            User(
                username="admin",
                email=admin_email,
                password_hash=hash_password(admin_password),
                role=UserRole.admin,
            )
        )
        try:
            await db.commit()
            logger.info("Default admin created — %s", admin_email)
        except IntegrityError:
            await db.rollback()
            logger.info("Admin déjà créé en parallèle par une autre instance, on continue.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initialising database...")
    await init_db()
    try:
        await _ensure_admin()
    except Exception:  # noqa: BLE001 — jamais bloquer le démarrage pour le compte admin
        logger.exception("Vérification du compte admin impossible, l'application démarre quand même.")

    bot_running = False
    if settings.ENABLE_TELEGRAM_BOT and settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_API_ID:
        # Clean up stale Pyrogram session files (prevents auth key errors after restart)
        import glob
        for stale in glob.glob("*.session*"):
            try:
                os.remove(stale)
                logger.info("Cleaned up stale session file: %s", stale)
            except OSError:
                pass

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
        logger.info("Telegram bot disabled (ENABLE_TELEGRAM_BOT=false).")

    # Synchronisation périodique des liens TMCooper
    from services import tmcooper_sync
    tmcooper_sync.start_loop()

    # Import automatique du catalogue (démarrage + refresh périodique)
    from services import catalog_sync
    catalog_sync.start_loop()

    yield

    await catalog_sync.stop_loop()
    await tmcooper_sync.stop_loop()

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

from routers import admin, anilist, animes, auth, comments, episodes, folders, notifications, push, search, tmcooper, tmdb, users  # noqa: E402
from routers import catalog as catalog_router  # noqa: E402

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
app.include_router(tmcooper.router, prefix="/api/admin/tmcooper", tags=["Admin - TMCooper"])
app.include_router(tmdb.router, prefix="/api/tmdb", tags=["TMDB"])
app.include_router(anilist.router, prefix="/api/anilist", tags=["AniList"])
app.include_router(catalog_router.router, prefix="/api/catalog", tags=["Catalog"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
