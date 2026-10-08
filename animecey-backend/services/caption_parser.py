"""Comprend les légendes libres venues d'autres canaux Telegram.

Exemples compris :
  The Eminence in Shadow / Saison 1 — Épisode 2 [VF]
  Black Clover 01 Multi
  Les Carnets de l'Apothicaire S03E01 VOSTFR
  I'm Giving the Disgraced Noble Lady ... E10 VOSTFR VERSION CONVERTIE
  @AnimesZonePremium Kage no Jitsuryokusha ni Naritakute! Saison 02 10 VOSTFR
  Demon Slayer / Film - La Forteresse Infinie — Épisode 1 · VF
  One Piece / Saga 1 (East Blue) — Épisode 6 [VF]
  Naruto / Arc 3 (Pays des Vagues) — Épisode 5 [VF]

Chaque légende est ramenée à : titre, emplacement (saison2, saga1, arc3, film1, oav...), langue, épisode.

Emplacements reconnus (légende, nom de fichier et commande /anime) :
  saison / season / S + n°   (+ « partie / cour / p » + n°)      -> saison2, saison2partie1
  saga + n°                   (+ nom entre parenthèses, ignoré)   -> saga1
  arc + n°                    (+ nom entre parenthèses, ignoré)   -> arc3
  film / movie (+ n°)                                             -> film1, film3
  oav / ova / oad / ona                                           -> oav
  spécial / special / hors-série                                  -> special
  récap / résumé                                                  -> recap
  bonus / extra                                                   -> bonus
  « nom libre entre guillemets » (commande seulement)             -> x-nom-libre (type « autre »)
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, replace

# Un fichier « Multi » contient plusieurs pistes audio : on le range dans cette langue.
MULTI_AS = "VOSTFR"

_KINDS = ("saison", "saga", "arc", "film", "oav", "special", "recap", "bonus")
# Un emplacement libre (nommé par l'admin entre guillemets) commence par ce préfixe : type « autre ».
FREE_PREFIX = "x-"

_NOISE = re.compile(
    r"\b(version\s+convertie|convertie|2160p?|1080p?|720p?|480p?|4k|web[- ]?dl|web[- ]?rip|blu[- ]?ray|"
    r"bd[- ]?rip|br[- ]?rip|dvd[- ]?rip|hdtv|remux|bd|x26[45]|hevc|h\.?26[45]|aac|ac3|eac3|dts|ddp\d*|"
    r"10 ?bits?|fhd|uhd|multi[- ]?subs?|mkv|mp4|avi|webm|m4v)\b",
    re.I,
)
_LANG = re.compile(r"(?<![\w])(vostfr|vost|truefrench|french|vff|vfq|vfi|vf|multi)(?![\w])", re.I)

_SXXEYY = re.compile(r"(?<![A-Za-z])S(\d{1,2})(?:\s*(?:partie|part|pt|p)\s*(\d))?\s*E(\d{1,4})(?![\w])", re.I)
_SEASON = re.compile(r"(?<![\w])(?:saison|season)\s*(\d{1,2})(?![\w])|(?<![\w])S(\d{1,2})(?:(?![\w])|(?=P\d(?![\w])))", re.I)
_PART = re.compile(r"\s*[-–—·,]?\s*(?:partie|part|pt|cour|p)\s*(\d)(?![\w])", re.I)
_PART_AFTER = re.compile(r"(?<![\w])(?:partie|part|pt|cour)\s*(\d)(?![\w])", re.I)
_PART_AFTER_P = re.compile(r"(?<![\w])p\s*(\d)(?![\w])", re.I)
_SAGA = re.compile(r"(?<![\w])saga\s*(\d{1,2})(?![\w])(?:\s*\([^)]*\))?", re.I)
_ARC = re.compile(r"(?<![\w])arc\s*(\d{1,2})(?![\w])(?:\s*\([^)]*\))?", re.I)
_FILM = re.compile(r"(?<![\w])(?:films?|movies?)(?![\w])(?:\s*(\d{1,2})(?![\w]))?", re.I)
_OAV = re.compile(r"(?<![\w])(?:oav|ova|oad|ona)(?![\w])", re.I)
_SPECIAL = re.compile(r"(?<![\w])(?:specials?|spéciaux|spécial|speciaux|hors[\s-]*s[ée]rie)(?![\w])", re.I)
_RECAP = re.compile(r"(?<![\w])(?:r[ée]caps?|r[ée]capitulatif|r[ée]sum[ée])(?![\w])", re.I)
_BONUS = re.compile(r"(?<![\w])(?:bonus|extras?)(?![\w])", re.I)
_EP_WORD = re.compile(r"(?<![\w])(?:épisode|episode|ép|ep)\.?\s*(\d{1,4})(?![\w])", re.I)
_EP_E = re.compile(r"(?<![A-Za-z])E(\d{1,4})(?![\w])", re.I)
_NUMBER = re.compile(r"(?<![\w.])(\d{1,4})(?![\w])")


def season_key(name: str) -> str:
    """'Saison 2 Partie 1' -> 'saison2partie1' (même forme que routers/catalog._season_key)."""
    return re.sub(r"\s+", "", (name or "").strip().lower())


def kind_of(key: str) -> str:
    if key.startswith(FREE_PREFIX):
        return "autre"
    for kind in _KINDS:
        if key.startswith(kind):
            return kind
    return "autre"


def pretty_label(key: str) -> str:
    """'saison2partie1' -> 'Saison 2 Partie 1' ; 'oav' -> 'OAV' ; 'x-pays-des-vagues' -> 'Pays Des Vagues'."""
    if key.startswith(FREE_PREFIX):
        return " ".join(w.capitalize() for w in key[len(FREE_PREFIX):].split("-") if w) or key
    out = []
    for p in re.findall(r"[a-z]+|\d+", key.lower()):
        out.append("OAV" if p == "oav" else "Récap" if p == "recap" else p.capitalize() if p.isalpha() else p)
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
    t = re.sub(r"(?<=\w)\.(?=\w)", " ", t)   # Jujutsu.Kaisen.0.2021 -> Jujutsu Kaisen 0 2021
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
        slot = f"saison{int(m.group(1))}" + (f"partie{int(m.group(2))}" if m.group(2) else "")
        episode = int(m.group(3))
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
            pm = _PART.match(work, m.end())
            if pm:
                slot += f"partie{int(pm.group(1))}"; work = _blank(work, pm)
    if slot is None:
        m = _ARC.search(work)
        if m:
            slot = f"arc{int(m.group(1))}"; starts.append(m.start()); work = _blank(work, m)
            pm = _PART.match(work, m.end())
            if pm:
                slot += f"partie{int(pm.group(1))}"; work = _blank(work, pm)
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
    if slot is None:
        m = _RECAP.search(work)
        if m:
            slot = "recap"; starts.append(m.start()); work = _blank(work, m)
    if slot is None:
        m = _BONUS.search(work)
        if m:
            slot = "bonus"; starts.append(m.start()); work = _blank(work, m)

    if episode is None:
        m = _EP_WORD.search(work) or _EP_E.search(work)
        if m:
            episode = int(m.group(1)); starts.append(m.start()); work = _blank(work, m)
    # Partie notée APRÈS l'épisode : « S02 Ep01 part 2 », « S02E01 Partie 2 ».
    # (« p 2 » seul n'est accepté que si l'épisode a été écrit explicitement : Ep / E.)
    if slot and slot.startswith(("saison", "saga", "arc")) and "partie" not in slot:
        pm = _PART_AFTER.search(work) or (_PART_AFTER_P.search(work) if episode is not None else None)
        if pm:
            slot += f"partie{int(pm.group(1))}"; work = _blank(work, pm)

    if episode is None:
        nums = [n for n in _NUMBER.finditer(work) if not (1900 <= int(n.group(1)) <= 2099)]
        if nums:
            m = nums[-1]
            episode = int(m.group(1)); starts.append(m.start())

    key, defaulted = ("saison1", True) if slot is None else (slot, False)
    if defaulted and episode == 0:
        # « Jujutsu Kaisen 0 » : le 0 est le numéro du film, pas un épisode.
        key, defaulted, episode = "film0", False, 1
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


# ── Options de la commande /anime : « /anime 16 VF S01 », « /anime Naruto arc 3 remplacer » ──

_ARG_PAREN = r"(?:\s*\([^)]*\))?"                                  # « (East Blue) » : ignoré
_ARG_PART = r"(?:\s*[-–—·,]?\s*(?:partie|part|pt|cour|p)\s*(\d))?"   # « partie 2 » facultative

_ARG_LANG = re.compile(r"(?:^|\s)(vostfr|vost|vff|vfq|vf)$", re.I)
_ARG_REPLACE = re.compile(r"(?:^|\s)(?:remplacer|remplace|replace|[ée]craser)$", re.I)
_ARG_SEASON = re.compile(r"(?:^|\s)(?:saison|season|s)\s*(\d{1,2})" + _ARG_PART + r"$", re.I)
_ARG_SAGA = re.compile(r"(?:^|\s)saga\s*(\d{1,2})" + _ARG_PAREN + _ARG_PART + r"$", re.I)
_ARG_ARC = re.compile(r"(?:^|\s)arc\s*(\d{1,2})" + _ARG_PAREN + _ARG_PART + r"$", re.I)
_ARG_FILM = re.compile(r"(?:^|\s)(?:films?|movies?)(?:\s*(\d{1,2}))?$", re.I)
_ARG_OAV = re.compile(r"(?:^|\s)(?:oav|ova|oad|ona)$", re.I)
_ARG_SPECIAL = re.compile(r"(?:^|\s)(?:specials?|spéciaux|spécial|speciaux|hors[\s-]*s[ée]rie)$", re.I)
_ARG_RECAP = re.compile(r"(?:^|\s)(?:r[ée]caps?|r[ée]capitulatif|r[ée]sum[ée])$", re.I)
_ARG_BONUS = re.compile(r"(?:^|\s)(?:bonus|extras?)$", re.I)
_ARG_FREE = re.compile(r"(?:^|\s)[\"“«]\s*([^\"”»]{2,40}?)\s*[\"”»]$")   # « "Pays des Vagues" »


def command_args(text: str | None) -> str:
    """Texte brut après la commande : '/anime@bot 16 "Arc X"' -> '16 "Arc X"'.

    Pyrogram retire les guillemets de message.command ; il faut donc partir du texte du message.
    """
    t = (text or "").strip()
    if t[:1] in "/!.":
        parts = t.split(None, 1)
        return parts[1].strip() if len(parts) > 1 else ""
    return t


def free_slot_key(name: str) -> str | None:
    """'Pays des Vagues' -> 'x-pays-des-vagues' (None si rien d'utilisable)."""
    words = re.findall(r"[^\W_]+", unicodedata.normalize("NFC", name or "").lower())
    slug = "-".join(words)[:40].strip("-")
    return FREE_PREFIX + slug if slug else None


def _slot_from_match(kind: str, m: re.Match) -> str:
    if kind in ("saison", "saga", "arc"):
        return f"{kind}{int(m.group(1))}" + (f"partie{int(m.group(2))}" if m.lastindex and m.lastindex >= 2 and m.group(2) else "")
    if kind == "film":
        return f"film{int(m.group(1) or 1)}"
    return kind  # oav, special, recap, bonus


_ARG_SLOTS = (
    ("saison", _ARG_SEASON), ("saga", _ARG_SAGA), ("arc", _ARG_ARC), ("film", _ARG_FILM),
    ("oav", _ARG_OAV), ("special", _ARG_SPECIAL), ("recap", _ARG_RECAP), ("bonus", _ARG_BONUS),
)


def parse_anime_args_ex(arg: str) -> tuple[str, str | None, str | None, bool]:
    """'16 VF S01 remplacer' -> ('16', 'VF', 'saison1', True).

    Les options (langue, emplacement, mot « remplacer ») se lisent en fin de commande, dans
    n'importe quel ordre. Renvoie (animé : id ou titre, langue | None, clé d'emplacement | None,
    mode remplacer).
    """
    query = (arg or "").strip()
    lang: str | None = None
    slot: str | None = None
    replace_mode = False
    for _ in range(6):
        if lang is None:
            m = _ARG_LANG.search(query)
            if m:
                lang = "VOSTFR" if m.group(1).lower() in ("vostfr", "vost") else "VF"
                query = query[: m.start()].strip()
                continue
        if not replace_mode:
            m = _ARG_REPLACE.search(query)
            if m:
                replace_mode = True
                query = query[: m.start()].strip()
                continue
        if slot is None:
            found = None
            for kind, rx in _ARG_SLOTS:
                m = rx.search(query)
                if m:
                    found = (kind, m)
                    break
            if found is None:
                m = _ARG_FREE.search(query)
                if m and (key := free_slot_key(m.group(1))):
                    slot = key
                    query = query[: m.start()].strip()
                    continue
            else:
                slot = _slot_from_match(*found)
                query = query[: found[1].start()].strip()
                continue
        break
    return query, lang, slot, replace_mode


def parse_anime_args(arg: str) -> tuple[str, str | None, str | None]:
    """'16 VF S01' -> ('16', 'VF', 'saison1') ; 'Black Clover saga 2' -> ('Black Clover', None, 'saga2').

    Version sans le mot « remplacer » (utilisée par /delsaison). Voir parse_anime_args_ex.
    """
    query, lang, slot, _ = parse_anime_args_ex(arg)
    return query, lang, slot
