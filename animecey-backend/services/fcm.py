"""Notifications Firebase (FCM) vers l'application Android.

Variable d'environnement : FIREBASE_CREDENTIALS_JSON = contenu du JSON « compte de service » (console Firebase →
Paramètres du projet → Comptes de service → Générer une nouvelle clé privée). Sans elle, ce module ne fait rien :
l'app continue de vérifier le serveur toutes les ~15 minutes (/api/app-notifications).

Le message est « data-only » (sans bloc notification) : c'est l'app (MagiFirebaseService) qui l'affiche, avec l'image
et le bon lien au clic. Les champs sont les mêmes que ceux de GET /api/app-notifications.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import timedelta

from sqlalchemy import delete, select

from database import async_session
from models_ads import FcmToken

logger = logging.getLogger(__name__)

_ready: bool | None = None


def _init() -> bool:
    """Initialise Firebase une seule fois. False si la clé est absente ou invalide."""
    global _ready
    if _ready is not None:
        return _ready
    raw = (os.getenv("FIREBASE_CREDENTIALS_JSON") or "").strip()
    if not raw:
        logger.info("FIREBASE_CREDENTIALS_JSON absent : notifications Firebase désactivées.")
        _ready = False
        return False
    try:
        import firebase_admin
        from firebase_admin import credentials

        if not firebase_admin._apps:
            firebase_admin.initialize_app(credentials.Certificate(json.loads(raw)))
        _ready = True
    except Exception as exc:  # noqa: BLE001
        logger.error("Firebase : initialisation impossible (%s)", exc)
        _ready = False
    return _ready


def is_enabled() -> bool:
    return _init()


def _send_sync(data: dict[str, str], tokens: list[str]) -> tuple[int, list[str]]:
    """Envoi par paquets de 500 (limite FCM). Renvoie (nombre envoyés, jetons devenus invalides)."""
    from firebase_admin import messaging

    ok, dead = 0, []
    for i in range(0, len(tokens), 500):
        batch = tokens[i : i + 500]
        res = messaging.send_each_for_multicast(
            messaging.MulticastMessage(
                data=data,
                tokens=batch,
                android=messaging.AndroidConfig(priority="high", ttl=timedelta(hours=24)),
            )
        )
        for tok, r in zip(batch, res.responses):
            if r.success:
                ok += 1
            elif isinstance(r.exception, (messaging.UnregisteredError, messaging.SenderIdMismatchError)):
                dead.append(tok)
            else:
                logger.warning("FCM : échec pour un jeton (%s)", r.exception)
    return ok, dead


async def send_app_notification(
    notif_id: int, title: str, body: str, path: str, image_url: str | None = None
) -> tuple[int, int]:
    """Envoie la notification à tous les téléphones enregistrés. Renvoie (envoyés, total de jetons)."""
    if not _init():
        return 0, 0
    async with async_session() as db:
        tokens = list((await db.execute(select(FcmToken.token))).scalars().all())
    if not tokens:
        return 0, 0
    data = {  # toutes les valeurs doivent être des chaînes
        "id": str(notif_id),
        "title": title,
        "body": body or "",
        "path": path or "/",  # « /anime/12 » ou un lien https://…
        "image_url": image_url or "",
    }
    try:
        ok, dead = await asyncio.to_thread(_send_sync, data, tokens)
    except Exception as exc:  # noqa: BLE001
        logger.error("FCM : envoi impossible (%s)", exc)
        return 0, len(tokens)
    if dead:
        async with async_session() as db:
            await db.execute(delete(FcmToken).where(FcmToken.token.in_(dead)))
            await db.commit()
    logger.info("FCM : notification #%s envoyée à %s/%s téléphones (%s jetons périmés supprimés)", notif_id, ok, len(tokens), len(dead))
    return ok, len(tokens)
