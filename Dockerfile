# syntax=docker/dockerfile:1.7
# Marketing Decision OS: cloud image. One process serves the API and the built web app.

# ---- 1. Build the React frontend ---------------------------------------------------------------
FROM node:24-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
# Exact versions from the lockfile; package install scripts never run.
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY frontend/ ./
# Vite writes the build into ../backend/mdos/static
RUN npm run build

# ---- 2. Python runtime ------------------------------------------------------------------------------
FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MDOS_MODE=cloud \
    MDOS_DATA_DIR=/data \
    PORT=8000 \
    FORWARDED_ALLOW_IPS=127.0.0.1
WORKDIR /app/backend

# Dependencies first, so source changes do not reinstall them. Every package is pinned with its hash in
# requirements.txt and installed from prebuilt wheels only, so no package build script runs.
COPY backend/requirements.txt ./
RUN pip install --require-hashes --only-binary=:all: -r requirements.txt

# The app runs from source (uvicorn imports mdos from this folder); tests and tooling stay out of the image.
COPY backend/mdos ./mdos
COPY --from=frontend /app/backend/mdos/static ./mdos/static
RUN useradd --create-home --uid 10001 mdos \
    && mkdir -p /data && chown mdos:mdos /data && chmod 700 /data

USER mdos
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"
# Migrations run automatically at start-up. Put TLS in front (a load balancer or reverse proxy).
# 0.0.0.0 is inside the container only; docker-compose publishes the port on the host's 127.0.0.1.
# Client IP and https headers are trusted only from FORWARDED_ALLOW_IPS: set it to your reverse proxy's address.
CMD ["sh", "-c", "exec uvicorn mdos.main:create_app --factory --host 0.0.0.0 --port \"${PORT}\" --proxy-headers --forwarded-allow-ips=\"${FORWARDED_ALLOW_IPS}\" --no-server-header"]
