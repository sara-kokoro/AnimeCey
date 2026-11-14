"""/vignettes <n° animé> [verif] [force] [stills] : titres des épisodes depuis TMDB (saisons ET sagas).

Depuis que les épisodes affichent le backdrop du titre (voir services/images.py), cette commande sert
surtout à remplir les TITRES des épisodes. Les vignettes TMDB (« stills ») ne sont écrites qu'avec « stills ».

Deux façons de faire correspondre nos épisodes à ceux de TMDB :

  • « Saison N »          -> saison N de TMDB, épisode par épisode (comme avant) ;
  • « Saga N », « Arc N » -> TMDB découpe One Piece en saisons-sagas (East Blue 61 ép., Whiskey Peak 16 ép., ...)
                             alors qu'Anime-Sama regroupe autrement. On aligne donc par NUMÉRO ABSOLU :
                             les sagas sont mises bout à bout (Saga 1 : 1-61, Saga 2 : 62-130...) et chaque
                             épisode est cherché dans la saison TMDB qui contient ce numéro.

« verif » n'écrit rien : il montre seulement comment les sagas correspondent aux saisons TMDB, pour vérifier
avant d'appliquer. Les films, OAV et spéciaux n'ont pas de correspondance fiable chez TMDB et sont ignorés.
"""

from __future__ import annotations

import logging
import re

import httpx
from pyrogram import Client, filters
from pyrogram.types import Message
from sqlalchemy import select

from bot.handlers.admin import is_admin
from database import async_session
from models import Anime, AnimeType, Episode
from models_catalog import AnimeSeason
from services import httpcache, tmdb

logger = logging.getLogger(__name__)

TMDB_IMG = "https://image.tmdb.org/t/p/w500"
_SEASON_KEY = re.compile(r"^saison(\d+)$")
_CHAIN_KEY = re.compile(r"^(saga|arc)\d+")


# ── Alignement (fonctions pures, testables) ────────────────────────────


def tmdb_ranges(details: dict) -> list[dict]:
    """Saisons TMDB (hors spéciaux) avec leur plage de numéros absolus : [{n, name, count, start, end}]."""
    out, start = [], 1
    seasons = [s for s in details.get("seasons") or [] if int(s.get("season_number") or 0) >= 1 and (s.get("episode_count") or 0) > 0]
    for s in sorted(seasons, key=lambda s: int(s["season_number"])):
        count = int(s["episode_count"])
        out.append({"n": int(s["season_number"]), "name": s.get("name") or f"Saison {s['season_number']}", "count": count, "start": start, "end": start + count - 1})
        start += count
    return out


def locate(ranges: list[dict], absolute: int) -> tuple[dict, int] | None:
    """(saison TMDB, numéro d'épisode dans cette saison) pour un numéro absolu, ou None s'il dépasse TMDB."""
    for r in ranges:
        if r["start"] <= absolute <= r["end"]:
            return r, absolute - r["start"] + 1
    return None


def chain_plan(seasons: list[dict]) -> tuple[list[dict], str | None]:
    """Met les sagas bout à bout.

    seasons : [{"season_number", "label", "numbers": set[int]}] dans l'ordre de l'animé.
    Renvoie (plan, avertissement) ; plan = [{"season_number", "label", "base", "first", "last"}] où
    numéro absolu = base + numéro local. S'arrête à la première saga sans épisode en ligne :
    sans elle, impossible de savoir de combien décaler les suivantes.
    """
    plan, offset, warning = [], 0, None
    for s in sorted(seasons, key=lambda s: s["season_number"]):
        nums = sorted(s["numbers"])
        if not nums:
            warning = (
                f"« {s['label']} » n'a aucun épisode en ligne : les sagas suivantes ne peuvent pas être alignées "
                "(ouvre-la sur le site pour la synchroniser, puis relance)."
            )
            break
        if offset > 0 and nums[0] == offset + 1:
            base = 0  # numérotation déjà absolue dans cette saga
        else:
            base = offset  # numérotation locale : 1, 2, 3...
        plan.append({"season_number": s["season_number"], "label": s["label"], "base": base, "first": base + nums[0], "last": base + nums[-1]})
        offset = base + nums[-1]
    return plan, warning


def describe(entry: dict, ranges: list[dict]) -> tuple[str, bool]:
    """(texte, aligné ?) : à quelles saisons TMDB correspond cette saga."""
    a, b = locate(ranges, entry["first"]), locate(ranges, entry["last"])
    count = entry["last"] - entry["first"] + 1
    if a is None:
        return f"{count} ép. → au-delà de ce que connaît TMDB", False
    if b is None:
        b = (ranges[-1], ranges[-1]["count"])
    first, last = a[0], b[0]
    covered = [r for r in ranges if first["n"] <= r["n"] <= last["n"]]
    names = " ; ".join(r["name"] for r in covered[:4]) + (" …" if len(covered) > 4 else "")
    span = f"S{first['n']}" if first["n"] == last["n"] else f"S{first['n']}–S{last['n']}"
    aligned = entry["first"] == first["start"] and entry["last"] == last["end"]
    note = "✓" if aligned else "⚠️ ne tombe pas pile sur les saisons TMDB"
    return f"{count} ép. → TMDB {span} ({names}) {note}", aligned


# ── Commande ───────────────────────────────────────────────────────────


def register(bot: Client):

    @bot.on_message(filters.private & filters.command("vignettes"))
    async def cmd_vignettes(client: Client, message: Message):
        if not message.from_user or not is_admin(message.from_user.id):
            return
        args = message.command[1:]
        if not args or not args[0].isdigit():
            return await message.reply(
                "Usage : /vignettes <n° animé> [verif] [force] [stills]\n"
                "Ex. /vignettes 10 verif → montre comment les sagas de One Piece correspondent aux saisons TMDB\n"
                "Ex. /vignettes 10 → remplit les titres des épisodes manquants\n"
                "• force : remplace aussi les titres déjà présents\n"
                "• stills : écrit aussi les vignettes TMDB (non affichées : le site montre le backdrop du titre)"
            )
        flags = {a.lower() for a in args[1:]}
        anime_id, force, stills, dry = int(args[0]), "force" in flags, "stills" in flags, bool({"verif", "test"} & flags)
        status = await message.reply("⏳ Lecture des saisons TMDB…")
        try:
            async with async_session() as db:
                anime = await db.get(Anime, anime_id)
                if not anime:
                    return await status.edit_text("Animé introuvable.")
                if not anime.tmdb_id:
                    return await status.edit_text(f"« {anime.title} » n'a pas de fiche TMDB. Fais d'abord /fiche {anime_id}.")
                if anime.type == AnimeType.film:
                    return await status.edit_text("Un film n'a pas d'épisodes chez TMDB : rien à remplir.")
                try:
                    details = await tmdb.get_details(anime.tmdb_id, "tv", db)
                except httpx.HTTPStatusError:
                    return await status.edit_text("Fiche TMDB introuvable (est-ce bien une série ? Refais /fiche).")
                ranges = tmdb_ranges(details or {})
                if not ranges:
                    return await status.edit_text("TMDB ne liste aucune saison pour cette fiche.")

                seasons = (await db.execute(select(AnimeSeason).where(AnimeSeason.anime_id == anime_id))).scalars().all()
                episodes = (await db.execute(select(Episode).where(Episode.anime_id == anime_id))).scalars().all()
                by_season: dict[int, list[Episode]] = {}
                for ep in episodes:
                    by_season.setdefault(ep.season_number, []).append(ep)

                lines: list[str] = []
                skipped: list[str] = []
                filled = titled = 0
                season_cache: dict[int, dict] = {}

                async def tmdb_season(n: int) -> dict | None:
                    if n not in season_cache:
                        try:
                            season_cache[n] = await tmdb.get_season(anime.tmdb_id, n, db)
                        except httpx.HTTPStatusError:
                            season_cache[n] = {}
                    return season_cache[n] or None

                def fill(ep: Episode, info: dict | None) -> None:
                    nonlocal filled, titled
                    if not info:
                        return
                    if not ep.title or force:
                        if info.get("name") and not re.fullmatch(r"(?i)(épisode|episode)\s*\d+", info["name"].strip()):
                            if ep.title != info["name"][:255]:
                                ep.title = info["name"][:255]
                                titled += 1
                    own = bool(ep.thumb_msg_id)  # vignette tirée de notre vidéo : on la garde
                    if stills and info.get("still_path") and not own and (force or not ep.thumbnail_url):
                        ep.thumbnail_url = f"{TMDB_IMG}{info['still_path']}"
                        filled += 1

                # 1) « Saison N » : saison N de TMDB, épisode par épisode
                chain: list[dict] = []
                for season in sorted(seasons, key=lambda s: s.season_number):
                    key = season.api_season or ""
                    m = _SEASON_KEY.match(key)
                    if m:
                        data = await tmdb_season(int(m.group(1)))
                        if not data:
                            lines.append(f"• {season.label} : introuvable chez TMDB")
                            continue
                        by_num = {e.get("episode_number"): e for e in data.get("episodes") or []}
                        mine = by_season.get(season.season_number, [])
                        if not dry:
                            for ep in mine:
                                fill(ep, by_num.get(ep.episode_number))
                        lines.append(f"• {season.label} : {len(mine)} ép. ↔ TMDB S{m.group(1)}")
                    elif _CHAIN_KEY.match(key):
                        chain.append(
                            {
                                "season_number": season.season_number,
                                "label": season.label,
                                "numbers": {ep.episode_number for ep in by_season.get(season.season_number, [])},
                            }
                        )
                    else:
                        skipped.append(season.label)

                # 2) Sagas / arcs : alignés par numéro absolu
                warning = None
                if chain:
                    plan, warning = chain_plan(chain)
                    for entry in plan:
                        text, _aligned = describe(entry, ranges)
                        lines.append(f"• {entry['label']} : {text}")
                        if dry:
                            continue
                        for ep in by_season.get(entry["season_number"], []):
                            hit = locate(ranges, entry["base"] + ep.episode_number)
                            if not hit:
                                continue
                            data = await tmdb_season(hit[0]["n"])
                            if data:
                                info = next((e for e in data.get("episodes") or [] if e.get("episode_number") == hit[1]), None)
                                fill(ep, info)
                    done = {e["season_number"] for e in plan}
                    for c in chain:
                        if c["season_number"] not in done:
                            lines.append(f"• {c['label']} : non alignée")

                if not dry:
                    await db.commit()
                    httpcache.clear()

            head = (
                f"🔎 Vérification pour « {anime.title} » (rien n'est écrit) :"
                if dry
                else f"✅ « {anime.title} » : {titled} titre(s) ajouté(s)" + (f", {filled} vignette(s) TMDB" if stills else "")
            )
            text = head + "\n" + "\n".join(lines)
            if warning:
                text += "\n⚠️ " + warning
            if skipped:
                text += "\nIgnorés (films, OAV, spéciaux : pas de correspondance TMDB) : " + ", ".join(skipped[:8])
            if dry and not warning:
                text += f"\n\nSi ça te convient : /vignettes {anime_id}"
            await status.edit_text(text[:4000])
        except Exception as exc:  # noqa: BLE001
            logger.exception("/vignettes en échec")
            await status.edit_text(f"❌ Erreur : {exc}")
