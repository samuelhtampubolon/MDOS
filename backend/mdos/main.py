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
from .config import get_settings
from .db import configure
from .errors import install_handlers
from .migrations_runner import upgrade_database

logger = logging.getLogger("mdos")
STATIC_DIR = Path(__file__).parent / "static"


def create_app(*, run_migrations: bool = True) -> FastAPI:
    settings = get_settings()
    configure(settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        settings.resolved_secret_key()  # fail fast in cloud mode without a key
        if run_migrations:
            upgrade_database()
        yield

    app = FastAPI(
        title="Marketing Decision OS API",
        version=__version__,
        description="Research Lab, Strategy Simulator and Journey Designer. All numbers come from code.",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    install_handlers(app)

    if settings.is_local:
        # Defends the passwordless local mode against DNS-rebinding style attacks.
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
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
