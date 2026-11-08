"""Cache mémoire des réponses publiques (GET) pour ménager la base Neon.

Seules les routes de lecture publiques listées dans RULES sont mises en cache, et seulement pour les
visiteurs anonymes (pas d'en-tête Authorization). Chaque entrée vit quelques dizaines de secondes :
un visiteur ne voit donc jamais une donnée vieille de plus de TTL, mais mille visiteurs = 1 requête SQL.
"""
from __future__ import annotations

import time
from typing import Dict, Tuple

# (préfixe de chemin, durée en secondes). Le premier préfixe qui correspond gagne.
RULES: Tuple[Tuple[str, int], ...] = (
    ("/api/animes/sitemap", 600),
    ("/api/animes/live-home", 60),
    ("/api/animes/featured", 120),
    ("/api/animes/top-week", 300),
    ("/api/animes/top-rated", 300),
    ("/api/animes/trending", 120),
    ("/api/animes/latest", 60),
    ("/api/animes", 120),
    ("/api/catalog/latest", 60),
    ("/api/catalog/search", 60),
    ("/api/catalog/anime/", 120),
    ("/api/calendar", 300),
    ("/api/search", 60),
    ("/api/ads/contact", 600),
    ("/api/episodes/sizes", 120),
)
# routes à ne jamais mettre en cache même si le préfixe correspond
NEVER = ("/stream", "/video", "/download", "/thumb", "/like", "/media", "/go", "/ticket")

MAX_ENTRIES = 400
MAX_BYTES = 600_000

_store: Dict[str, Tuple[float, int, list, bytes]] = {}


def _ttl(path: str) -> int:
    if any(n in path for n in NEVER):
        return 0
    if path == "/api/episodes":
        return 60
    for prefix, ttl in RULES:
        if path.startswith(prefix):
            return ttl
    return 0


def clear() -> None:
    _store.clear()


class ResponseCacheMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "GET":
            return await self.app(scope, receive, send)
        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        path = scope["path"]
        ttl = _ttl(path)
        if not ttl or b"authorization" in headers or b"cookie" in headers:
            return await self.app(scope, receive, send)

        key = path + "?" + scope.get("query_string", b"").decode("latin-1")
        now = time.monotonic()
        hit = _store.get(key)
        if hit and hit[0] > now:
            _, status, hdrs, body = hit
            await send({"type": "http.response.start", "status": status, "headers": hdrs + [(b"x-cache", b"HIT")]})
            await send({"type": "http.response.body", "body": body})
            return

        state: dict = {"status": 200, "headers": [], "body": b"", "ok": True}

        async def capture(message):
            if message["type"] == "http.response.start":
                state["status"] = message["status"]
                hdrs = [(k, v) for k, v in message.get("headers", []) if k.lower() != b"cache-control"]
                if message["status"] == 200:
                    hdrs.append((b"cache-control", f"public, max-age={min(ttl, 60)}".encode()))
                state["headers"] = hdrs
                message = {**message, "headers": hdrs + [(b"x-cache", b"MISS")]}
            elif message["type"] == "http.response.body":
                state["body"] += message.get("body", b"")
                if message.get("more_body") and len(state["body"]) > MAX_BYTES:
                    state["ok"] = False
            await send(message)

        await self.app(scope, receive, capture)

        if state["status"] == 200 and state["ok"] and len(state["body"]) <= MAX_BYTES:
            if len(_store) >= MAX_ENTRIES:
                for k in [k for k, v in _store.items() if v[0] <= now] or list(_store)[:50]:
                    _store.pop(k, None)
            _store[key] = (now + ttl, 200, state["headers"], state["body"])
