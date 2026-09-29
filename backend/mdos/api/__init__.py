"""API routers mounted under /api/v1."""

from fastapi import APIRouter

from . import auth, projects

router = APIRouter()
router.include_router(auth.router)
router.include_router(projects.router)
