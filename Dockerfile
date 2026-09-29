# syntax=docker/dockerfile:1.7
# Marketing Decision OS: cloud image. One process serves the API and the built web app.

# ---- 1. Build the React frontend ---------------------------------------------------------------
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
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
    PORT=8000
WORKDIR /app/backend

# Dependencies first, so source changes do not reinstall them.
COPY backend/pyproject.toml ./
RUN python -c "import tomllib; d = tomllib.load(open('pyproject.toml', 'rb'))['project']; \
print('\n'.join(d['dependencies'] + d['optional-dependencies']['postgres']))" > /tmp/requirements.txt \
    && pip install -r /tmp/requirements.txt "setuptools>=69"

COPY backend/ ./
COPY --from=frontend /app/backend/mdos/static ./mdos/static
RUN pip install --no-deps --no-build-isolation . \
    && useradd --create-home --uid 10001 mdos \
    && mkdir -p /data && chown mdos:mdos /data

USER mdos
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"
# Migrations run automatically at start-up. Put TLS in front (a load balancer or reverse proxy).
CMD ["sh", "-c", "exec uvicorn mdos.main:create_app --factory --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
