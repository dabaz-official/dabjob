# syntax=docker/dockerfile:1

# The frontend is built here and copied into the runtime image, so the
# container runs one process on one port — the same app `make dev` runs,
# minus the Vite server.

FROM node:24-slim AS web
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build


FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DABJOB_DATA_DIR=/data \
    DABJOB_STATIC_DIR=/app/frontend/dist

WORKDIR /app

COPY backend/ ./backend/
RUN pip install --no-cache-dir ./backend

COPY --from=web /app/frontend/dist ./frontend/dist

# Runs as root on purpose. /data is a bind mount owned by the host user,
# and a fixed container UID makes `docker compose up` fail to write on
# Linux. The process is reachable only through the loopback port mapping
# in compose.yml, and the bind policy refuses a public address unless
# DABJOB_ALLOW_REMOTE is set explicitly.
#
# 0.0.0.0 is required inside a container: it is the container's own
# network namespace, not the host's. compose.yml sets the opt-in and
# limits the published port to 127.0.0.1.
EXPOSE 8000
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"

CMD ["uvicorn", "dabjob.main:app", "--host", "0.0.0.0", "--port", "8000"]
