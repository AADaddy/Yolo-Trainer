from __future__ import annotations

from fastapi import APIRouter

from backend.services.tracking_parameters import get_tracking_module_status


router = APIRouter(prefix="/tracking", tags=["tracking"])


@router.get("/status")
def tracking_status() -> dict:
    return get_tracking_module_status()
