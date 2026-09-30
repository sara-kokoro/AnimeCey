FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends git build-essential \
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

ENV TMCOOPER_API_URL=http://127.0.0.1:5000

EXPOSE 8000
CMD ["./start.sh"]
