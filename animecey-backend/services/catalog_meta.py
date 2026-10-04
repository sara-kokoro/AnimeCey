"""Métadonnées d'un titre du catalogue : TMDB (français) + AniList.

Comme quand tu créais un animé à la main depuis l'admin : titre japonais,
synopsis, genres, année, note, statut, affiche, bannière, bande-annonce.
TMCooper ne fournit que les épisodes ; tout le reste vient d'ici.

Si TMDB ou AniList ne répondent pas, ou si aucun résultat ne ressemble assez au
titre, l'animé est quand même créé avec ce qu'on a (jamais de blocage).

Mettre ce fichier dans services/catalog_meta.py.
"""

from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from difflib import SequenceMatcher

from sqlalchemy.ext.asyncio import AsyncSession

from services import anilist, tmdb

logger = logging.getLogger(__name__)

TIMEOUT = 12.0
MIN_RATIO = 0.62
TMDB_IMG = "https://image.tmdb.org/t/p"


def _norm(text: str | None) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _ratio(a: str | None, b: str | None) -> float:
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def _clean_html(text: str | None) -> str | None:
    if not text:
        return None
    text = re.sub(r"<br\s*/?>", "\n", str(text), flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text).strip()
    return text or None


def pick_tmdb(title: str, results: list[dict]) -> dict | None:
    """Choisit la fiche TMDB la plus probable pour un ANIMÉ.

    Un titre identique ne suffit pas (ex. « Demon Slayer » existe aussi comme film d'horreur de
    2003) : on favorise fortement la catégorie Animation et la langue d'origine japonaise, et on
    pénalise ce qui n'est ni l'un ni l'autre.
    """
    best, best_score = None, 0.0
    for r in results or []:
        names = [r.get("name"), r.get("title"), r.get("original_name"), r.get("original_title")]
        score = max((_ratio(title, n) for n in names), default=0.0)
        is_anim = 16 in (r.get("genre_ids") or [])
        is_ja = r.get("original_language") == "ja"
        if is_anim:
            score += 0.30
        if is_ja:
            score += 0.10
        if not is_anim and not is_ja:
            score -= 0.35
        if score > best_score:
            best, best_score = r, score
    return best if best is not None and best_score >= MIN_RATIO else None


def pick_anilist(title: str, results: list[dict]) -> dict | None:
    best, best_score = None, 0.0
    for r in results or []:
        t = r.get("title") or {}
        score = max((_ratio(title, t.get(k)) for k in ("english", "romaji", "native")), default=0.0)
        if score > best_score:
            best, best_score = r, score
    return best if best is not None and best_score >= MIN_RATIO else None


_TMDB_STATUS = {
    "returning series": "ongoing",
    "in production": "upcoming",
    "planned": "upcoming",
    "ended": "completed",
    "canceled": "completed",
    "cancelled": "completed",
    "released": "completed",
}
_ANILIST_STATUS = {"RELEASING": "ongoing", "FINISHED": "completed", "NOT_YET_RELEASED": "upcoming"}


def merge_metadata(
    tmdb_details: dict | None,
    tmdb_media: str | None,
    anilist_data: dict | None,
    fallback_poster: str | None,
) -> dict:
    """Fusionne TMDB (prioritaire pour le texte en français) et AniList."""
    td, al = tmdb_details or {}, anilist_data or {}
    out: dict = {}

    # titre japonais
    native = (al.get("title") or {}).get("native") or td.get("original_name") or td.get("original_title")
    out["title_jp"] = native[:255] if native else None

    # synopsis : TMDB en français d'abord, AniList (anglais) sinon
    out["synopsis"] = (td.get("overview") or "").strip() or _clean_html(al.get("description"))

    # genres
    genres = [g.get("name") for g in td.get("genres") or [] if g.get("name")]
    out["genres"] = genres or list(al.get("genres") or [])

    # année
    year = None
    date = td.get("first_air_date") or td.get("release_date") or ""
    if len(date) >= 4 and date[:4].isdigit():
        year = int(date[:4])
    if year is None:
        year = (al.get("startDate") or {}).get("year")
    out["year"] = year

    # note sur 10
    score = td.get("vote_average") or 0
    if not score and al.get("averageScore"):
        score = al["averageScore"] / 10
    out["score"] = round(float(score), 1) if score else 0.0

    # statut
    status = _TMDB_STATUS.get(str(td.get("status") or "").lower()) or _ANILIST_STATUS.get(al.get("status"))
    out["status"] = status

    # type
    out["is_film"] = tmdb_media == "movie" or al.get("format") == "MOVIE"

    # images (on n'écrase pas l'affiche du catalogue si rien de mieux)
    poster = f"{TMDB_IMG}/w500{td['poster_path']}" if td.get("poster_path") else None
    poster = poster or (al.get("coverImage") or {}).get("extraLarge") or fallback_poster
    out["poster_url"] = poster[:500] if poster else None
    banner = f"{TMDB_IMG}/original{td['backdrop_path']}" if td.get("backdrop_path") else None
    banner = banner or al.get("bannerImage")
    out["banner_url"] = banner[:500] if banner else None

    # bande-annonce
    trailer = td.get("trailer_url")
    if not trailer:
        tr = al.get("trailer") or {}
        if tr.get("site") == "youtube" and tr.get("id"):
            trailer = f"https://www.youtube.com/embed/{tr['id']}"
    out["trailer_url"] = trailer[:500] if trailer else None

    out["tmdb_id"] = td.get("id")
    out["anilist_id"] = al.get("id")
    return out


async def _tmdb_lookup(title: str, db: AsyncSession) -> tuple[dict | None, str | None]:
    results = await tmdb.search(title, db)
    picked = pick_tmdb(title, results)
    if not picked:
        return None, None
    media = "movie" if picked.get("media_type") == "movie" else "tv"
    details = await tmdb.get_details(int(picked["id"]), media, db)
    details = dict(details or {})
    details.setdefault("id", picked["id"])
    return details, media


async def _anilist_lookup(title: str, db: AsyncSession) -> dict | None:
    results = await anilist.search(title, db)
    return pick_anilist(title, results)


async def find_metadata(title: str, fallback_poster: str | None, db: AsyncSession) -> dict:
    """Ne lève jamais d'exception : renvoie au pire un dict avec l'affiche de repli."""
    td = media = al = None
    try:
        td, media = await asyncio.wait_for(_tmdb_lookup(title, db), TIMEOUT)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Métadonnées TMDB indisponibles pour '%s': %s", title, exc)
    try:
        al = await asyncio.wait_for(_anilist_lookup(title, db), TIMEOUT)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Métadonnées AniList indisponibles pour '%s': %s", title, exc)
    return merge_metadata(td, media, al, fallback_poster)


async def apply_metadata(db: AsyncSession, anime, meta: dict) -> None:
    """Applique une fiche (résultat de merge_metadata) sur un animé déjà en base."""
    from sqlalchemy import select

    from models import Anime, AnimeStatus

    value = meta.get("anilist_id")
    if value:  # colonne unique : on ignore si un autre animé a déjà cet id AniList
        taken = (
            await db.execute(select(Anime.id).where(Anime.anilist_id == value, Anime.id != anime.id))
        ).first()
        if taken:
            meta = {**meta, "anilist_id": None}

    for field in ("title_jp", "synopsis", "genres", "year", "poster_url", "banner_url", "trailer_url"):
        if meta.get(field):
            setattr(anime, field, meta[field])
    if meta.get("score"):
        anime.score = meta["score"]
    if meta.get("status"):
        try:
            anime.status = AnimeStatus(meta["status"])
        except ValueError:
            pass
    if meta.get("tmdb_id"):
        anime.tmdb_id = meta["tmdb_id"]
    if meta.get("anilist_id"):
        anime.anilist_id = meta["anilist_id"]
    await db.commit()
