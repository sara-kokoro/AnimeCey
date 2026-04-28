from __future__ import annotations

import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")


def _csv_to_int_list(raw: str) -> List[int]:
    if not raw:
        return []
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


class _Settings:
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://neondb_owner:npg_PA2ZHWcl7SUe@ep-sweet-water-anqfx5fa.c-6.us-east-1.aws.neon.tech/neondb?ssl=require")

    # JWT
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY",
        "IHUbWjz5614iPbdrHVbCnnO8mbSJzgOrwBJ4FjbgZYQm0UizUmi8OKvbExVxW3n5zi61U8Dc8b3FJhhq+PKwfQ==",
    )
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080")
    )

    # Telegram Bot
    TELEGRAM_API_ID: int = int(os.getenv("TELEGRAM_API_ID", "37641587"))
    TELEGRAM_API_HASH: str = os.getenv("TELEGRAM_API_HASH", "9bce1167e828939f39452795e56202a9")
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "8732815098:AAGwppoI115Z7Y7p5McnW2BN-LanwJpvsOY")
    TELEGRAM_CHANNEL_ID: int = int(os.getenv("TELEGRAM_CHANNEL_ID", "-1003340962000"))
    TELEGRAM_ADMIN_IDS: List[int] = _csv_to_int_list(
        os.getenv("TELEGRAM_ADMIN_IDS", "8467461906")
    )

    # Byse.sx
    BYSE_API_KEY: str = os.getenv("BYSE_API_KEY", "109610faqw0934hma3ggqz")
    BYSE_BASE_URL: str = os.getenv("BYSE_BASE_URL", "https://api.byse.sx/")

    # TMDB
    TMDB_API_KEY: str = os.getenv("TMDB_API_KEY", "f2bed62b5977bce26540055276d0046c")
    TMDB_BASE_URL: str = os.getenv(
        "TMDB_BASE_URL", "https://api.themoviedb.org/3"
    )

    # AniList
    ANILIST_BASE_URL: str = os.getenv(
        "ANILIST_BASE_URL", "https://graphql.anilist.co"
    )

    # Web Push VAPID
    VAPID_PUBLIC_KEY: str = os.getenv("VAPID_PUBLIC_KEY", "BI2pC9_yPeTU11_q-Cw-FNpxt2sXxGaTDHkAfqLhWuWVyweOrAlySohMPN492MlyI-3L41hp8W1w0Lgw3AHcNOI")
    VAPID_PRIVATE_KEY: str = os.getenv("VAPID_PRIVATE_KEY", "5snml5V9vp7jJNCC7oUivHz4mnA3G2PFphwla4LmEsw")
    VAPID_CLAIMS_EMAIL: str = os.getenv(
        "VAPID_CLAIMS_EMAIL", "admin@animecey.vercel.app"
    )

    # CORS
    CORS_ORIGINS: List[str] = [
        o.strip()
        for o in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,https://animecey.vercel.app"
        ).split(",")
        if o.strip()
    ]

    # Debug — false by default in production
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")


settings = _Settings()
