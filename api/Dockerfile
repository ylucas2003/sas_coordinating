# syntax=docker/dockerfile:1

# Imagem do backend FastAPI do SAS.
#
# Dois alvos:
#   --target dev   → uvicorn com --reload; usado pelo docker-compose.yml
#   --target prod  → imagem imutável, usuário não-root; usada no deploy
#
# Build de produção:
#   docker build --target prod -t sas-api ./api


# ─── base: dependências ──────────────────────────────────────────────────
# Fica separada do código pra que editar um .py não invalide a camada de
# pip install (que é a cara do build).
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Todas as deps de api/requirements.txt têm wheel pronta pra linux/amd64 e
# arm64 (inclusive psycopg[binary] e cryptography) — por isso nenhum
# compilador ou libpq-dev precisa entrar aqui.
COPY requirements.txt ./
RUN pip install -r requirements.txt

EXPOSE 8000

# Sem curl na imagem (mantém ela enxuta): o healthcheck usa a própria stdlib.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,urllib.request as u; u.urlopen('http://127.0.0.1:' + os.environ.get('PORT','8000') + '/health').read()"


# ─── dev ─────────────────────────────────────────────────────────────────
# O compose monta ./api por cima de /app, então salvar um arquivo no host
# recarrega o uvicorn na hora. O COPY aqui é só pra imagem funcionar mesmo
# sem o mount (ex.: `docker run` avulso).
FROM base AS dev

COPY . .

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --reload"]


# ─── prod ────────────────────────────────────────────────────────────────
FROM base AS prod

COPY . .

# Não-root. O código fica read-only pro processo — a API só escreve em
# storage remoto (Supabase), nunca em disco local.
RUN useradd --create-home --uid 10001 sas
USER sas

# PORT é injetada por Render/Cloud Run/Fly; 8000 é o default local.
# 1 worker por default de propósito: o canvas_sync usa trava em banco e o
# chat streama SSE — suba UVICORN_WORKERS só depois de validar concorrência.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${UVICORN_WORKERS:-1}"]
