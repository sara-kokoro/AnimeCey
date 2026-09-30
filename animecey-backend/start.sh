#!/bin/sh
# Lance AnimeSamaApi (en local, port 5000) puis le backend FastAPI sur $PORT.
# Le backend appelle l'API via TMCOOPER_API_URL (par défaut http://127.0.0.1:5000).

ANIMESAMA_DIR="${ANIMESAMA_DIR:-/opt/AnimeSamaApi}"

(
  cd "$ANIMESAMA_DIR" || exit 1
  # Relance l'API si elle plante, sans jamais bloquer le backend.
  while true; do
    python main.py
    echo "[start.sh] AnimeSamaApi s'est arrêtée (code $?), relance dans 5 s..." >&2
    sleep 5
  done
) &

exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
