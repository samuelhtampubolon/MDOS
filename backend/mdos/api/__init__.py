"""API routers mounted under /api/v1."""

from fastapi import APIRouter

from . import (
    analyses,
    approvals,
    auth,
    datasets,
    evidence,
    experiments,
    journey,
    projects,
    reports,
    research,
    strategy,
    tools,
)

router = APIRouter()
for module in (auth, projects, research, datasets, analyses, evidence, approvals, reports, strategy, journey, experiments, tools):
    router.include_router(module.router)
