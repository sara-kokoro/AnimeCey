"""Lance AnimeSamaApi (TMCooper) en local, avec trois ajouts.

  1. Proxy Fixie (IP fixe) : si FIXIE_URL est défini, les requêtes vers
     Anime-Sama passent par Fixie. Les autres (hébergeurs vidéo : Sibnet,
     Vidmoly...) restent directes, car leurs liens sont souvent liés à l'IP
     qui les a demandés : un lien obtenu via Fixie ne marcherait pas chez
     l'utilisateur.
  2. Si TMCooper ne trouve pas le domaine Anime-Sama au démarrage (BASE_URL vide),
     le code HTTP reçu pour chaque domaine candidat est affiché dans les logs.
  3. Variable ANIMESAMA_URL (ex. https://anime-sama.xx) : si elle est définie,
     elle remplace le domaine détecté automatiquement.

Variables d'environnement :
  FIXIE_URL               http://fixie:TOKEN@xxxx.usefixie.com:80  (fournie par Fixie)
  ANIMESAMA_PROXY_MODE    auto (défaut) : au démarrage, un test DIRECT (sans proxy,
                          donc gratuit) est fait sur Anime-Sama ; s'il passe (HTTP 200),
                          le proxy est désactivé et ne consomme aucune requête.
                          always : le proxy est toujours utilisé.
  ANIMESAMA_PROXY_HOSTS   morceaux de noms d'hôtes à passer par le proxy,
                          séparés par des virgules (défaut : anime-sama).
                          "*" = tout passe par le proxy.
  ANIMESAMA_URL           domaine Anime-Sama à forcer (optionnel)
  ANIMESAMA_DIR / ANIMESAMA_PORT

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


def install_proxy() -> None:
    original = requests.Session.request

    def request(self, method, url, *args, **kwargs):
        if _proxy_enabled and kwargs.get("proxies") is None and _use_proxy(url):
            kwargs["proxies"] = {"http": PROXY_URL, "https": PROXY_URL}
        return original(self, method, url, *args, **kwargs)

    requests.Session.request = request


if PROXY_URL:
    install_proxy()
    shown = PROXY_URL.split("@")[-1]  # sans identifiants
    log(f"proxy Fixie actif ({shown}) pour: {', '.join(PROXY_HOSTS)}")
else:
    log("pas de proxy (FIXIE_URL non défini)")
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

if PROXY_URL and PROXY_MODE != "always" and backend.BASE_URL:
    code = probe_direct(backend.BASE_URL)
    if code == 200:
        _proxy_enabled = False
        log(f"test direct sur {backend.BASE_URL}: HTTP 200, accès sans proxy possible : "
            "proxy désactivé (aucune requête Fixie consommée).")
    else:
        log(f"test direct sur {backend.BASE_URL}: HTTP {code}, accès bloqué : le proxy reste actif.")

from src.api import Yui  # noqa: E402
from src.utils.config import Config  # noqa: E402

Config.IP, Config.PORT = HOST, PORT

try:
    from waitress import serve

    log(f"API sur http://{HOST}:{PORT} (waitress)")
    serve(Yui.app, host=HOST, port=PORT, threads=8)
except ImportError:
    log(f"API sur http://{HOST}:{PORT} (Flask)")
    Yui.app.run(host=HOST, port=PORT, debug=False, use_reloader=False, threaded=True)
