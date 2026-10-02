"""Lance AnimeSamaApi (TMCooper) en local, avec deux garde-fous en plus.

  1. Si TMCooper ne trouve pas le domaine Anime-Sama au démarrage (BASE_URL vide),
     ce script affiche le code HTTP reçu pour chaque domaine candidat : on voit
     tout de suite si c'est un blocage Cloudflare (403), un timeout ou une
     redirection.
  2. Variable ANIMESAMA_URL (ex. https://anime-sama.xx) : si elle est définie,
     elle remplace le domaine détecté automatiquement.

Le code de TMCooper n'est pas modifié. Pas de mode debug, pas de reloader, et
pas de vérification git interactive (input()) qui planterait sans terminal.

Mettre ce fichier à la racine du backend (à côté de start.sh).
"""

import os
import re
import sys

ROOT = os.getenv("ANIMESAMA_DIR", "/opt/AnimeSamaApi")
PORT = int(os.getenv("ANIMESAMA_PORT", "5000"))
HOST = "127.0.0.1"

os.chdir(ROOT)
sys.path.insert(0, ROOT)

import src.backend as backend  # noqa: E402  (cherche le domaine au chargement)


def log(msg: str) -> None:
    print(f"[launcher] {msg}", flush=True)


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


override = os.getenv("ANIMESAMA_URL", "").strip().rstrip("/")
if override:
    backend.BASE_URL = override
    log(f"domaine forcé par ANIMESAMA_URL: {override}")
elif not backend.BASE_URL:
    log("TMCooper n'a trouvé aucun domaine Anime-Sama actif. Diagnostic :")
    diagnose()
    log("Définis ANIMESAMA_URL si tu connais le bon domaine.")
else:
    log(f"domaine Anime-Sama détecté: {backend.BASE_URL}")

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
