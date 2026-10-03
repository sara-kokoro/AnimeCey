"""Comprend les légendes libres venues d'autres canaux Telegram.

Exemples compris :
  The Eminence in Shadow / Saison 1 — Épisode 2 [VF]
  Black Clover 01 Multi
  Les Carnets de l'Apothicaire S03E01 VOSTFR
  I'm Giving the Disgraced Noble Lady ... E10 VOSTFR VERSION CONVERTIE
  @AnimesZonePremium Kage no Jitsuryokusha ni Naritakute! Saison 02 10 VOSTFR
  Demon Slayer / Film - La Forteresse Infinie — Épisode 1 · VF
  One Piece / Saga 1 (East Blue) — Épisode 6 [VF]

Chaque légende est ramenée à : titre, emplacement (saison2, saga1, film1, oav...), langue, épisode.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, replace

# Un fichier « Multi » contient plusieurs pistes audio : on le range dans cette langue.
MULTI_AS = "VOSTFR"

_KINDS = ("saison", "saga", "film", "oav", "special")

_NOISE = re.compile(
    r"\b(version\s+convertie|convertie|2160p|1080p|720p|480p|4k|web[- ]?dl|web[- ]?rip|blu[- ]?ray|"
    r"x26[45]|hevc|h\.?26[45]|aac|fhd|uhd)\b",
    re.I,
)
_LANG = re.compile(r"(?<![\w])(vostfr|vost|vff|vfi|vf|multi)(?![\w])", re.I)

_SXXEYY = re.compile(r"(?<![A-Za-z])S(\d{1,2})\s*E(\d{1,4})(?![\w])", re.I)
_SEASON = re.compile(r"(?<![\w])(?:saison|season)\s*(\d{1,2})(?![\w])|(?<![\w])S(\d{1,2})(?![\w])", re.I)
_PART = re.compile(r"\s*[-–—·,]?\s*(?:partie|part|cour)\s*(\d)(?![\w])", re.I)
_SAGA = re.compile(r"(?<![\w])saga\s*(\d{1,2})(?![\w])(?:\s*\([^)]*\))?", re.I)
_FILM = re.compile(r"(?<![\w])films?(?![\w])(?:\s*(\d{1,2})(?![\w]))?", re.I)
_OAV = re.compile(r"(?<![\w])(?:oav|ova|oad)(?![\w])", re.I)
_SPECIAL = re.compile(r"(?<![\w])(?:specials?|spéciaux|spécial|speciaux)(?![\w])", re.I)
_EP_WORD = re.compile(r"(?<![\w])(?:épisode|episode|ép|ep)\.?\s*(\d{1,4})(?![\w])", re.I)
_EP_E = re.compile(r"(?<![A-Za-z])E(\d{1,4})(?![\w])", re.I)
_NUMBER = re.compile(r"(?<![\w.])(\d{1,4})(?![\w])")


def season_key(name: str) -> str:
    """'Saison 2 Partie 1' -> 'saison2partie1' (même forme que routers/catalog._season_key)."""
    return re.sub(r"\s+", "", (name or "").strip().lower())


def kind_of(key: str) -> str:
    for kind in _KINDS:
        if key.startswith(kind):
            return kind
    return "autre"


def pretty_label(key: str) -> str:
    """'saison2partie1' -> 'Saison 2 Partie 1' ; 'oav' -> 'OAV'."""
    out = []
    for p in re.findall(r"[a-z]+|\d+", key.lower()):
        out.append("OAV" if p == "oav" else p.capitalize() if p.isalpha() else p)
    return " ".join(out) or key


def norm(s: str | None) -> str:
    """Pour comparer des titres : sans accents, sans ponctuation, en minuscules."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", s.lower())


@dataclass(frozen=True)
class Parsed:
    title: str | None = None
    slot_key: str = "saison1"
    slot_defaulted: bool = True   # aucun emplacement trouvé dans la légende -> saison 1
    episode: int | None = None
    lang: str | None = None       # "VF" | "VOSTFR" | None
    multi: bool = False

    @property
    def kind(self) -> str:
        return kind_of(self.slot_key)


def merge_missing(a: Parsed, b: Parsed) -> Parsed:
    """Complète a avec ce que b a trouvé (ex. légende + nom du fichier)."""
    return replace(
        a,
        title=a.title or b.title,
        episode=a.episode if a.episode is not None else b.episode,
        lang=a.lang or b.lang,
        multi=a.multi or (b.multi and a.lang is None),
        slot_key=a.slot_key if not a.slot_defaulted else b.slot_key,
        slot_defaulted=a.slot_defaulted and b.slot_defaulted,
    )


def _clean(text: str, is_filename: bool) -> str:
    t = text or ""
    t = re.sub(r"https?://\S+|t\.me/\S+", " ", t)
    t = re.sub(r"[@#]\w+", " ", t)                                   # @canaux, #hashtags
    if is_filename:
        t = t.replace("_", " ").replace(".", " ")
    t = re.sub(r"[^\w\s\-–—·|:.,!?'’()\[\]/&+]", " ", t)             # emojis, flèches...
    t = t.replace("_", " ")
    return re.sub(r"[\[\(]\s*[\]\)]", " ", t)                        # crochets vides


def _blank(text: str, m: re.Match) -> str:
    return text[: m.start()] + " " * (m.end() - m.start()) + text[m.end():]


def parse_caption(text: str, is_filename: bool = False) -> Parsed:
    t = _clean(text, is_filename)
    work = t                      # copie dont on « efface » les marqueurs trouvés
    starts: list[int] = []        # position du premier marqueur (fin du titre)

    # ── langue ──
    lang, multi = None, False
    m = _LANG.search(work)
    if m:
        w = m.group(1).lower()
        if w == "multi":
            lang, multi = MULTI_AS, True
        elif w in ("vostfr", "vost"):
            lang = "VOSTFR"
        else:
            lang = "VF"
    work = _LANG.sub(lambda x: " " * len(x.group(0)), work)
    work = _NOISE.sub(lambda x: " " * len(x.group(0)), work)

    # ── emplacement + épisode ──
    slot, episode = None, None
    m = _SXXEYY.search(work)
    if m:
        slot, episode = f"saison{int(m.group(1))}", int(m.group(2))
        starts.append(m.start()); work = _blank(work, m)
    if slot is None:
        m = _SEASON.search(work)
        if m:
            n = int(m.group(1) or m.group(2))
            slot = f"saison{n}"
            starts.append(m.start()); work = _blank(work, m)
            pm = _PART.match(work, m.end())
            if pm:
                slot += f"partie{int(pm.group(1))}"; work = _blank(work, pm)
    if slot is None:
        m = _SAGA.search(work)
        if m:
            slot = f"saga{int(m.group(1))}"; starts.append(m.start()); work = _blank(work, m)
    if slot is None:
        m = _FILM.search(work)
        if m:
            slot = f"film{int(m.group(1) or 1)}"; starts.append(m.start()); work = _blank(work, m)
    if slot is None:
        m = _OAV.search(work)
        if m:
            slot = "oav"; starts.append(m.start()); work = _blank(work, m)
    if slot is None:
        m = _SPECIAL.search(work)
        if m:
            slot = "special"; starts.append(m.start()); work = _blank(work, m)

    if episode is None:
        m = _EP_WORD.search(work) or _EP_E.search(work)
        if m:
            episode = int(m.group(1)); starts.append(m.start()); work = _blank(work, m)
    if episode is None:
        nums = list(_NUMBER.finditer(work))
        if nums:
            m = nums[-1]
            episode = int(m.group(1)); starts.append(m.start())

    key, defaulted = ("saison1", True) if slot is None else (slot, False)
    if kind_of(key) == "film" and episode is None:
        episode = 1

    # ── titre : ce qui précède le premier marqueur (dernière ligne non vide) ──
    cut = min(starts) if starts else len(t)
    before = t[:cut]
    before = _LANG.sub(" ", before)
    before = _NOISE.sub(" ", before)
    lines = [ln.strip(" \t-–—·|:,[]()") for ln in before.splitlines()]
    lines = [ln for ln in lines if re.search(r"\w", ln)]
    title = re.sub(r"\s+", " ", lines[-1]).strip() if lines else None
    if title and len(title) < 2:
        title = None

    return Parsed(title=title, slot_key=key, slot_defaulted=defaulted, episode=episode, lang=lang, multi=multi)
