"""Recherche floue dans les animés d'AnimeCey (titre, titre japonais, autres noms).

Tolère : accents (« démon » = « demon »), majuscules, ponctuation, fautes de frappe
(« demom slayr ») et autres noms de l'animé (« Shingeki no Kyojin » -> « Attack des Titans »,
grâce à la table anime_aliases).
Pas d'extension Postgres nécessaire : l'index des noms est gardé en mémoire (quelques centaines
d'animés) et rafraîchi toutes les 30 s.
"""

from __future__ import annotations

import asyncio
import re
import time
import unicodedata
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Anime
from models_catalog import AnimeAlias

MIN_SCORE = 55
_TTL = 30.0

_index: list[tuple[int, list[str]]] = []
_index_at = 0.0
_lock = asyncio.Lock()


def norm(value: str | None) -> str:
    """'Démon  Slayer: Kimetsu!' -> 'demon slayer kimetsu' (sans accents ni ponctuation)."""
    if not value:
        return ""
    s = unicodedata.normalize("NFKD", value)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[\W_]+", " ", s).strip()


def score_name(q: str, qtokens: list[str], name: str) -> float:
    """Note de 0 à 100 : à quel point `name` correspond à la recherche `q` (déjà normalisés)."""
    if not name or not q:
        return 0.0
    if name == q:
        return 100.0
    if name.startswith(q):
        return 92.0
    padded = f" {name} "
    if f" {q} " in padded:
        return 88.0
    if q in name:
        return 82.0

    ntokens = name.split()
    total = 0.0
    for t in qtokens:
        best = 0.0
        for w in ntokens:
            if w == t:
                best = 1.0
                break
            if len(t) >= 2 and w.startswith(t):
                best = max(best, 0.9)
            elif len(t) >= 3 and t in w:
                best = max(best, 0.8)
            elif len(t) >= 3 and abs(len(t) - len(w)) <= 2:
                r = SequenceMatcher(None, t, w).ratio()
                if r >= 0.75:
                    best = max(best, r * 0.9)
        if best == 0.0:
            total = -1.0  # un mot de la recherche ne correspond à rien
            break
        total += best
    if total >= 0:
        return 60.0 + 20.0 * (total / len(qtokens))

    if len(q) >= 4:  # faute de frappe sur l'ensemble (« demomslayer », « atack on titan »)
        sm = SequenceMatcher(None, q, name)
        if sm.real_quick_ratio() >= 0.7 and sm.quick_ratio() >= 0.7:
            r = sm.ratio()
            if r >= 0.78:
                return 50.0 + 30.0 * r
    return 0.0


async def _load_index(db: AsyncSession) -> list[tuple[int, list[str]]]:
    global _index, _index_at
    if time.monotonic() - _index_at < _TTL and _index:
        return _index
    async with _lock:
        if time.monotonic() - _index_at < _TTL and _index:
            return _index
        names: dict[int, set[str]] = {}
        for aid, title, title_jp in (await db.execute(select(Anime.id, Anime.title, Anime.title_jp))).all():
            names[aid] = {n for n in (norm(title), norm(title_jp)) if n}
        for aid, alias_norm in (await db.execute(select(AnimeAlias.anime_id, AnimeAlias.alias_norm))).all():
            if aid in names and alias_norm:
                names[aid].add(alias_norm)
        _index = [(aid, sorted(ns)) for aid, ns in names.items()]
        _index_at = time.monotonic()
        return _index


def invalidate() -> None:
    global _index_at
    _index_at = 0.0


async def ranked_anime_ids(db: AsyncSession, query: str) -> list[int]:
    """Ids des animés qui correspondent, du plus pertinent au moins pertinent."""
    q = norm(query)
    if len(q) < 2:
        return []
    qtokens = q.split()
    scored: list[tuple[float, int]] = []
    for aid, ns in await _load_index(db):
        best = max((score_name(q, qtokens, n) for n in ns), default=0.0)
        if best >= MIN_SCORE:
            scored.append((best, aid))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [aid for _, aid in scored]
