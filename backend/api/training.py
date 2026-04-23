from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.models import TrainingRunCreate
from backend.services.training_config_service import get_training_config
from backend.services.trainer import create_training_run, delete_training_run, get_training_run, list_training_runs


router = APIRouter(prefix="/training", tags=["training"])


@router.post("/runs")
def start_training(payload: TrainingRunCreate) -> dict:
    try:
        return create_training_run(payload.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/runs")
def get_training_runs(project_id: int | None = Query(default=None)) -> list[dict]:
    return list_training_runs(project_id=project_id)


@router.get("/runs/{run_id}")
def get_run(run_id: int) -> dict:
    try:
        return get_training_run(run_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/runs/{run_id}")
def remove_run(run_id: int, payload: dict) -> dict:
    try:
        return delete_training_run(run_id, payload.get("confirmation", ""))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/config/{project_id}")
def load_training_config(project_id: int) -> dict:
    try:
        return get_training_config(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
