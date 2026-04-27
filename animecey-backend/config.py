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
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./animecey.db")

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
    TELEGRAM_API_ID: int = int(os.getenv("TELEGRAM_API_ID", "0"))
    TELEGRAM_API_HASH: str = os.getenv("TELEGRAM_API_HASH", "")
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHANNEL_ID: int = int(os.getenv("TELEGRAM_CHANNEL_ID", "0"))
    TELEGRAM_ADMIN_IDS: List[int] = _csv_to_int_list(
        os.getenv("TELEGRAM_ADMIN_IDS", "")
    )

    # Byse.sx
    BYSE_API_KEY: str = os.getenv("BYSE_API_KEY", "")
    BYSE_BASE_URL: str = os.getenv("BYSE_BASE_URL", "https://api.byse.sx/")

    # TMDB
    TMDB_API_KEY: str = os.getenv("TMDB_API_KEY", "")
    TMDB_BASE_URL: str = os.getenv(
        "TMDB_BASE_URL", "https://api.themoviedb.org/3"
    )

    # AniList
    ANILIST_BASE_URL: str = os.getenv(
        "ANILIST_BASE_URL", "https://graphql.anilist.co"
    )

    # Web Push VAPID
    VAPID_PUBLIC_KEY: str = os.getenv("VAPID_PUBLIC_KEY", "")
    VAPID_PRIVATE_KEY: str = os.getenv("VAPID_PRIVATE_KEY", "")
    VAPID_CLAIMS_EMAIL: str = os.getenv(
        "VAPID_CLAIMS_EMAIL", "admin@animecey.app"
    )

    # CORS
    CORS_ORIGINS: List[str] = [
        o.strip()
        for o in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,https://animecey.vercel.app"
        ).split(",")
        if o.strip()
    ]

    # Debug
    DEBUG: bool = os.getenv("DEBUG", "true").lower() in ("true", "1", "yes")


settings = _Settings()
