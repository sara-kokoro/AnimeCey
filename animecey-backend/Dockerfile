FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends git build-essential ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# ── AnimeSamaApi (TMCooper) ─────────────────────────────────
# Pour figer une version, remplace main par un hash de commit.
ARG ANIMESAMA_REF=main
RUN git clone https://github.com/TMCooper/AnimeSamaApi /opt/AnimeSamaApi \
    && cd /opt/AnimeSamaApi \
    && git checkout "$ANIMESAMA_REF" \
    && pip install -r requirements.txt

# ── Backend AnimeCey ────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
# Robuste si le zip a perdu le bit exécutable ou ajouté des fins de ligne Windows (CRLF)
RUN sed -i 's/\r$//' start.sh && chmod +x start.sh

ENV TMCOOPER_API_URL=http://127.0.0.1:5000

EXPOSE 8000
CMD ["sh", "start.sh"]
