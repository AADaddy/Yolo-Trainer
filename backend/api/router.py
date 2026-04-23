from __future__ import annotations

from fastapi import APIRouter

from backend.api.comparison import router as comparison_router
from backend.api.datasets import router as datasets_router
from backend.api.projects import router as projects_router
from backend.api.tracking import router as tracking_router
from backend.api.training import router as training_router


api_router = APIRouter()
api_router.include_router(projects_router)
api_router.include_router(datasets_router)
api_router.include_router(training_router)
api_router.include_router(comparison_router)
api_router.include_router(tracking_router)
