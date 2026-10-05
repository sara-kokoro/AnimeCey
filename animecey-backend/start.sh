#!/bin/sh
# Lance AnimeSamaApi (en local, port 5000) puis le backend FastAPI sur $PORT.
# Le backend appelle l'API via TMCOOPER_API_URL (par défaut http://127.0.0.1:5000).
#
# ANIMESAMA_ENABLED=false : ne lance pas AnimeSamaApi du tout (aucun proxy, aucun crédit).
# Si AnimeSamaApi plante, la pause avant relance double à chaque échec (5 s, 10 s, 20 s ... 15 min) :
# une boucle de plantages ne doit pas saturer le petit serveur et bloquer le bot Telegram.

ANIMESAMA_DIR="${ANIMESAMA_DIR:-/opt/AnimeSamaApi}"

if [ "${ANIMESAMA_ENABLED:-true}" = "true" ]; then
  (
    cd "$ANIMESAMA_DIR" || exit 1
    delay=5
    while true; do
      started=$(date +%s)
      python /app/animesama_launcher.py
      code=$?
      ran=$(( $(date +%s) - started ))
      if [ "$ran" -gt 120 ]; then
        delay=5                       # elle tournait bien : on repart de zéro
      else
        delay=$(( delay * 2 ))
        [ "$delay" -gt 900 ] && delay=900
      fi
      echo "[start.sh] AnimeSamaApi s'est arrêtée (code $code) après ${ran}s, relance dans ${delay}s..." >&2
      sleep "$delay"
    done
  ) &
else
  echo "[start.sh] AnimeSamaApi désactivée (ANIMESAMA_ENABLED=false)." >&2
fi

exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
