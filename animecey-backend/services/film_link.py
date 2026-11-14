"""Un film peut vivre à deux endroits : dans sa série (« One Piece » > Film 15) ET sur sa propre fiche
(« One Piece Film - Red »). Ce module relie les deux sans dupliquer le fichier : les deux épisodes
pointent vers le MÊME message du canal Telegram.

  • find_sibling()   : retrouve la fiche propre d'un film d'après le titre de la légende ;
  • mirror_episode() : crée / met à jour l'épisode du film sur cette fiche ;
  • tokens()         : comparaison de titres par mots (« Chainsaw Man - The Movie : Reze Arc » =
                       « Chainsaw Man - Le film : Arc Reze »), insensible à l'ordre, aux accents, à
                       « Film / Movie / The / Le », aux années.

Un message du canal encore utilisé par un autre épisode n'est jamais effacé (voir supprimer.unshared_messages).
"""

from __future__ import annotations

import re
import unicodedata

from sqlalchemy import select

from models import Anime, AnimeType, Episode, LanguageEnum
from services.tmcooper_sync import _get_or_create_folder

_STOP = {"film", "films", "movie", "the", "le", "la", "les", "l", "de", "du", "des", "un", "une", "of", "and", "et", "arc", "part", "partie", "saga"}


def tokens(text: str | None) -> frozenset[str]:
    """Mots significatifs d'un titre (minuscules, sans accents, sans mots vides ni années)."""
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    words = re.findall(r"[a-z0-9]+", t)
    return frozenset(w for w in words if w not in _STOP and not (len(w) == 4 and w.isdigit() and 1900 <= int(w) <= 2099))


def same_title(a: str | None, b: str | None) -> bool:
    ta = tokens(a)
    return bool(ta) and ta == tokens(b)


async def find_sibling(db, full_title: str | None, exclude_id: int | None = None):
    """La fiche « film » (type film) dont le titre correspond à `full_title`, ou None (aucune, ou plusieurs : ambigu)."""
    if not full_title:
        return None
    q = select(Anime.id, Anime.title, Anime.title_jp).where(Anime.type == AnimeType.film)
    if exclude_id is not None:
        q = q.where(Anime.id != exclude_id)
    hits = [r for r in (await db.execute(q)).all() if same_title(full_title, r.title) or same_title(full_title, r.title_jp)]
    return hits[0] if len(hits) == 1 else None


async def mirror_episode(
    db,
    film: Anime,
    season_number: int,
    season_label: str | None,
    language: LanguageEnum,
    num: int,
    file_id: str,
    msg_id: int,
    duration: int | None,
    replace: bool,
) -> tuple[str, int | None]:
    """Crée ou met à jour l'épisode de la fiche du film. Renvoie (« added » | « replaced » | « kept », ancien message à purger).

    « kept » : la fiche du film a déjà un fichier et `replace` est faux : on n'y touche pas.
    Ne fait pas de commit (l'appelant s'en charge).
    """
    folder = await _get_or_create_folder(db, film, language, season_number)
    if season_label and folder.name != season_label:
        folder.name = season_label[:255]
    ep = (
        await db.execute(
            select(Episode).where(
                Episode.anime_id == film.id,
                Episode.language == language,
                Episode.season_number == season_number,
                Episode.episode_number == num,
            )
        )
    ).scalars().first()
    stale: int | None = None
    status = "added"
    if ep is None:
        ep = Episode(anime_id=film.id, folder_id=folder.id, episode_number=num, language=language, season_number=season_number)
        db.add(ep)
    elif ep.servcey1_file_id:
        if ep.servcey1_msg_id == msg_id:
            return "kept", None  # déjà relié à ce même fichier
        if not replace:
            return "kept", None
        status = "replaced"
        stale = ep.servcey1_msg_id if ep.servcey1_msg_id and ep.servcey1_msg_id != msg_id else None
    ep.servcey1_file_id = file_id
    ep.servcey1_msg_id = msg_id
    ep.servcey1_available = True
    if duration:
        ep.duration = duration
    await db.flush()
    return status, stale
