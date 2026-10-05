"""Lance AnimeSamaApi (TMCooper) en local, avec trois ajouts.

  1. Accès à Anime-Sama via ZenRows (recommandé) ou Fixie (ancien) :
     - ZENROWS_API_KEY défini : les requêtes GET vers Anime-Sama passent par l'API ZenRows
       (https://api.zenrows.com/v1/). Chaque requête consomme des crédits ZenRows.
     - sinon, si FIXIE_URL est défini : proxy Fixie comme avant.
     Anime-Sama est le seul site concerné. Les autres (hébergeurs vidéo : Sibnet,
     Vidmoly...) restent directes, car leurs liens sont souvent liés à l'IP
     qui les a demandés : un lien obtenu via Fixie ne marcherait pas chez
     l'utilisateur.
  2. Si TMCooper ne trouve pas le domaine Anime-Sama au démarrage (BASE_URL vide),
     le code HTTP reçu pour chaque domaine candidat est affiché dans les logs.
  3. Variable ANIMESAMA_URL (ex. https://anime-sama.xx) : si elle est définie,
     elle remplace le domaine détecté automatiquement.

Variables d'environnement :
  ZENROWS_API_KEY         clé d'API ZenRows (tableau de bord ZenRows)
  ZENROWS_PARAMS          options ZenRows, au format URL (défaut : premium_proxy=true&proxy_country=fr).
                          Si Anime-Sama bloque encore : premium_proxy=true&js_render=true&antibot=true
                          (plus cher en crédits).
  FIXIE_URL               http://fixie:TOKEN@xxxx.usefixie.com:80  (ancien, facultatif)
  ANIMESAMA_PROXY_MODE    auto (défaut) : au démarrage, un test DIRECT (sans proxy,
                          donc gratuit) est fait sur Anime-Sama ; s'il passe (HTTP 200),
                          le proxy est désactivé et ne consomme aucune requête.
                          always : le proxy est toujours utilisé.
  ANIMESAMA_PROXY_HOSTS   morceaux de noms d'hôtes à passer par le proxy,
                          séparés par des virgules (défaut : anime-sama).
                          "*" = tout passe par le proxy.
  ANIMESAMA_URL           domaine Anime-Sama à forcer (optionnel)
  ANIMESAMA_DIR / ANIMESAMA_PORT

  4. Route supplémentaire /api/getAnimeServers : renvoie TOUS les lecteurs d'Anime-Sama
     pour une saison (TMCooper n'en garde qu'un par épisode). Elle réutilise les
     fonctions de TMCooper et ne coûte que 2 requêtes par saison et version.

Le code de TMCooper n'est pas modifié. Pas de mode debug, pas de reloader, et
pas de vérification git interactive (input()) qui planterait sans terminal.

Mettre ce fichier à la racine du backend (à côté de start.sh).
"""

import os
import re
import sys
from urllib.parse import urlparse

ROOT = os.getenv("ANIMESAMA_DIR", "/opt/AnimeSamaApi")
PORT = int(os.getenv("ANIMESAMA_PORT", "5000"))
HOST = "127.0.0.1"

os.chdir(ROOT)
sys.path.insert(0, ROOT)


def log(msg: str) -> None:
    print(f"[launcher] {msg}", flush=True)


# --- proxy begin ---------------------------------------------------------
# À installer AVANT d'importer TMCooper : il cherche déjà le domaine à l'import.
import requests  # noqa: E402

PROXY_URL = (os.getenv("FIXIE_URL") or os.getenv("ANIMESAMA_PROXY") or "").strip()
ZENROWS_KEY = os.getenv("ZENROWS_API_KEY", "").strip()
ZENROWS_PARAMS = os.getenv("ZENROWS_PARAMS", "premium_proxy=true&proxy_country=fr").strip()
ZENROWS_URL = "https://api.zenrows.com/v1/"
PROXY_MODE = os.getenv("ANIMESAMA_PROXY_MODE", "auto").strip().lower()
_proxy_enabled = True
PROXY_HOSTS = [
    h.strip().lower()
    for h in os.getenv("ANIMESAMA_PROXY_HOSTS", "anime-sama").split(",")
    if h.strip()
]


def _use_proxy(url: str) -> bool:
    if "*" in PROXY_HOSTS:
        return True
    host = (urlparse(str(url)).hostname or "").lower()
    return any(part in host for part in PROXY_HOSTS)


def zenrows_args(url: str, kwargs: dict) -> tuple[str, dict]:
    """Transforme une requête GET vers Anime-Sama en requête vers l'API ZenRows."""
    from urllib.parse import parse_qsl, urlencode

    kwargs = dict(kwargs)
    target = str(url)
    extra = kwargs.pop("params", None)
    if extra:
        target += ("&" if "?" in target else "?") + urlencode(extra, doseq=True)
    params = {"apikey": ZENROWS_KEY, "url": target}
    params.update(dict(parse_qsl(ZENROWS_PARAMS)))
    kwargs["params"] = params
    kwargs.pop("proxies", None)
    kwargs["timeout"] = max(float(kwargs.get("timeout") or 0), 90.0)  # ZenRows peut être lent
    return ZENROWS_URL, kwargs


def install_proxy() -> None:
    original = requests.Session.request

    def request(self, method, url, *args, **kwargs):
        if _proxy_enabled and kwargs.get("proxies") is None and _use_proxy(url):
            if ZENROWS_KEY:
                if str(method).upper() == "GET":
                    url, kwargs = zenrows_args(url, kwargs)
            elif PROXY_URL:
                kwargs["proxies"] = {"http": PROXY_URL, "https": PROXY_URL}
        return original(self, method, url, *args, **kwargs)

    requests.Session.request = request


if ZENROWS_KEY:
    install_proxy()
    log(f"ZenRows actif (options : {ZENROWS_PARAMS}) pour: {', '.join(PROXY_HOSTS)}")
elif PROXY_URL:
    install_proxy()
    shown = PROXY_URL.split("@")[-1]  # sans identifiants
    log(f"proxy Fixie actif ({shown}) pour: {', '.join(PROXY_HOSTS)}")
else:
    log("pas de proxy (ni ZENROWS_API_KEY ni FIXIE_URL)")
# --- proxy end -----------------------------------------------------------

override = os.getenv("ANIMESAMA_URL", "").strip().rstrip("/")
if override:
    # Domaine connu : on saute la détection automatique (économise des requêtes proxy
    # à chaque démarrage) en remplaçant la fonction de TMCooper avant son import.
    import src.utils.utils as _tm_utils  # noqa: E402

    _tm_utils.Utils.findLink = lambda *args, **kwargs: override

import src.backend as backend  # noqa: E402  (cherche le domaine au chargement)


def diagnose() -> None:
    """Affiche le code HTTP de chaque domaine candidat."""
    try:
        import cloudscraper
        from src.utils.utils import URL_PW

        scraper = cloudscraper.create_scraper()
        page = scraper.get(URL_PW, timeout=15)
        log(f"page des domaines {URL_PW}: HTTP {page.status_code}")
        match = re.search(r"const domains = \[(.*?)\];", page.text, re.DOTALL)
        if not match:
            log("liste 'const domains' introuvable dans la page (HTML différent ou page de blocage)")
            return
        for domain in re.findall(r"name: '([^']+)'", match.group(1)):
            try:
                r = scraper.get(f"https://{domain}", timeout=8, allow_redirects=False)
                where = r.headers.get("Location", "")
                log(f"  {domain}: HTTP {r.status_code} {where}")
            except Exception as exc:  # noqa: BLE001
                log(f"  {domain}: erreur {type(exc).__name__}")
    except Exception as exc:  # noqa: BLE001
        log(f"diagnostic impossible: {exc!r}")


def probe_direct(base_url: str) -> int | None:
    """Code HTTP d'Anime-Sama SANS proxy (proxies={} = aucun proxy, aucune requête Fixie)."""
    try:
        import cloudscraper

        return cloudscraper.create_scraper().get(base_url, timeout=15, proxies={}).status_code
    except Exception as exc:  # noqa: BLE001
        log(f"test direct impossible: {type(exc).__name__}")
        return None


if override:
    backend.BASE_URL = override
    log(f"domaine forcé par ANIMESAMA_URL (détection automatique sautée): {override}")
elif not backend.BASE_URL:
    log("TMCooper n'a trouvé aucun domaine Anime-Sama actif. Diagnostic :")
    diagnose()
    log("Définis ANIMESAMA_URL si tu connais le bon domaine.")
else:
    log(f"domaine Anime-Sama détecté: {backend.BASE_URL}")

if (ZENROWS_KEY or PROXY_URL) and PROXY_MODE != "always" and backend.BASE_URL:
    code = probe_direct(backend.BASE_URL)
    if code == 200:
        _proxy_enabled = False
        log(f"test direct sur {backend.BASE_URL}: HTTP 200, accès sans proxy possible : "
            "accès direct, proxy désactivé (aucun crédit consommé).")
    else:
        log(f"test direct sur {backend.BASE_URL}: HTTP {code}, accès bloqué : le proxy / ZenRows reste actif.")

from src.api import Yui  # noqa: E402
from src.utils.config import Config  # noqa: E402


# --- route /api/getAnimeServers -------------------------------------------
import time  # noqa: E402

_INFO_CACHE: dict = {}  # nom -> (horodatage, saisons) ; évite de relire la page de l'animé


def _norm(text) -> str:
    return (text or "").strip().lower().replace(" ", "")


def pick_season(info, saison):
    """Comme getSpecificAnime, mais sans retomber sur la 1re saison si le nom ne correspond pas."""
    wanted = _norm(saison)
    for item in info or []:
        if isinstance(item, dict) and _norm(item.get("Saison")) == wanted:
            return item
    if wanted in ("oav", "oavs"):
        for item in info or []:
            if isinstance(item, dict) and "oav" in _norm(item.get("Saison")):
                return item
    return None


def build_link(url: str, saison: str, version: str) -> str:
    """Même construction d'URL que getAnimeLink."""
    key = _norm(saison)
    version = _norm(version)
    if key == "film":
        base = url.lower().replace("//film", "/film")
    elif key in ("oav", "oavs"):
        base = url.lower().replace("//oav", "/oav")
    else:
        base = url
    base = re.sub(r"/(?:vostfr|vf)/?$", "", base, flags=re.IGNORECASE)
    return f"{base}/{version}"


def extract_servers(js_text: str) -> list:
    """episodes.js -> [{"name": "eps1", "urls": [url_ep1, url_ep2, ...]}, ...].

    Les entrées vides sont conservées (chaîne vide) pour que la position
    corresponde bien au numéro d'épisode.
    """
    servers = []
    for name, content in re.findall(r"var\s+(eps\w+)\s*=\s*\[(.*?)\];", js_text or "", re.DOTALL):
        urls = [m[1].strip() for m in re.findall(r"""(['"])(.*?)\1""", content)]
        urls = [u if u.startswith(("http://", "https://")) else "" for u in urls]
        if any(urls):
            servers.append({"name": name, "urls": urls})
    return servers


def get_anime_servers():
    from bs4 import BeautifulSoup
    import cloudscraper
    from flask import jsonify, request

    nom = (request.args.get("n") or "").strip()
    saison = request.args.get("s") or "saison1"
    version = request.args.get("v") or "vostfr"
    if not nom:
        return jsonify({"error": "paramètre n manquant"}), 400
    try:
        now = time.time()
        cached = _INFO_CACHE.get(nom)
        if cached and now - cached[0] < 600:
            info = cached[1]
        else:
            info = backend.Cardinal.getInfoAnime(nom)
            info = info if isinstance(info, list) else []
            if info:
                _INFO_CACHE[nom] = (now, info)

        item = pick_season(info, saison)
        if item is None or not item.get("url"):
            return jsonify({"servers": [], "reason": "saison introuvable"})

        link = build_link(item["url"], saison, version)
        scraper = cloudscraper.create_scraper()
        page = scraper.get(link)
        soup = BeautifulSoup(page.text, "html.parser")
        tag = soup.find("script", src=lambda s: s and "episodes.js" in s)
        if not tag:
            return jsonify({"servers": [], "reason": "episodes.js introuvable", "http": page.status_code})
        js_link = tag.get("src", "").split('"')[0].split("'")[0]
        js_text = scraper.get(f"{link.rstrip('/')}/{js_link.lstrip('/')}").text
        return jsonify({"link": link, "servers": extract_servers(js_text)})
    except Exception as exc:  # noqa: BLE001
        log(f"getAnimeServers: {type(exc).__name__}: {exc}")
        return jsonify({"error": f"{type(exc).__name__}: {exc}"}), 502


Yui.app.add_url_rule("/api/getAnimeServers", "getAnimeServers", get_anime_servers)

Config.IP, Config.PORT = HOST, PORT

try:
    from waitress import serve

    log(f"API sur http://{HOST}:{PORT} (waitress)")
    serve(Yui.app, host=HOST, port=PORT, threads=8)
except ImportError:
    log(f"API sur http://{HOST}:{PORT} (Flask)")
    Yui.app.run(host=HOST, port=PORT, debug=False, use_reloader=False, threaded=True)
