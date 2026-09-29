"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import __version__
from .bodylimit import MB, BodySizeLimitMiddleware
from .config import get_settings
from .db import configure
from .errors import install_handlers
from .migrations_runner import upgrade_database

logger = logging.getLogger("mdos")
STATIC_DIR = Path(__file__).parent / "static"


# The single-page app: everything from this origin, no inline scripts, no third-party requests.
APP_CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; font-src 'self' data:; "
           "connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
# FastAPI's interactive docs page (opt-in) loads Swagger UI from a CDN and runs one inline script.
DOCS_CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com; "
            "connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'")
PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"


def create_app(*, run_migrations: bool = True) -> FastAPI:
    settings = get_settings()
    configure(settings)
    if "*" in settings.cors_origin_list:
        raise RuntimeError("CORS_ORIGINS cannot be '*'. List the exact origins that may call the API.")

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        settings.resolved_secret_key()  # fail fast in cloud mode without a key
        if not settings.is_local and settings.allowed_hosts.strip() == "*":
            logger.warning("ALLOWED_HOSTS is '*': the host check is off. Set your public domain instead.")
        if run_migrations:
            upgrade_database()
        yield

    docs = settings.api_docs_enabled
    app = FastAPI(
        title="Marketing Decision OS API",
        version=__version__,
        description="Research Lab, Strategy Simulator and Journey Designer. All numbers come from code.",
        lifespan=lifespan,
        docs_url="/api/docs" if docs else None,
        openapi_url="/api/openapi.json" if docs else None,
        redoc_url=None,
    )
    install_handlers(app)
    # Innermost middleware, so a refused request still gets the security headers below.
    app.add_middleware(BodySizeLimitMiddleware, json_limit=settings.max_json_mb * MB,
                       upload_limit=(settings.max_upload_mb + 1) * MB)

    if settings.is_local:
        # Defends the passwordless local mode against DNS-rebinding style attacks.
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
    elif settings.allowed_hosts.strip() != "*":
        # Loopback names stay allowed for the container health check; browsers cannot be steered to them remotely.
        hosts = {h.strip() for h in settings.allowed_hosts.split(",") if h.strip()} | {"127.0.0.1", "localhost"}
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=sorted(hosts))

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        path = request.url.path
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "no-referrer")
        headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        headers.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        headers.setdefault("Content-Security-Policy", DOCS_CSP if docs and path == "/api/docs" else APP_CSP)
        if path.startswith("/api/"):
            headers.setdefault("Cache-Control", "no-store")  # account data never lands in shared or disk caches
        if not settings.is_local and request.url.scheme == "https":
            headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        return response
    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=False,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
        )

    from .api import router as api_router

    app.include_router(api_router, prefix="/api/v1")

    @app.get("/api/health", include_in_schema=False)
    def health() -> dict:
        return {"status": "ok", "version": __version__, "mode": settings.mdos_mode}

    _mount_spa(app)
    return app


def _mount_spa(app: FastAPI) -> None:
    """Serve the built React app, falling back to index.html for client-side routes."""
    index = STATIC_DIR / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse({"error": {"code": "not_found", "message": "Not found."}}, status_code=404)
        candidate = (STATIC_DIR / full_path).resolve()
        if full_path and STATIC_DIR.resolve() in candidate.parents and candidate.is_file():
            return FileResponse(candidate)
        if index.exists():
            return FileResponse(index)
        return JSONResponse(
            {"message": "Frontend not built. Run `make frontend` or use the Vite dev server on :5173."},
            status_code=200,
        )
