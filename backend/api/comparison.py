from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from backend.services.model_comparison_service import build_comparison_payload, get_best_model_download


router = APIRouter(prefix="/comparison", tags=["comparison"])


@router.get("/runs")
def compare_runs(
    project_id: int | None = Query(default=None),
    dataset_version_id: int | None = Query(default=None),
    yolo_version: str | None = Query(default=None),
    model_size: str | None = Query(default=None),
    sort_by: str = Query(default="started_at"),
    sort_order: str = Query(default="desc"),
) -> dict:
    return build_comparison_payload(
        project_id=project_id,
        dataset_version_id=dataset_version_id,
        yolo_version=yolo_version,
        model_size=model_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/runs/{run_id}/best-model")
def download_best_model(run_id: int) -> FileResponse:
    try:
        model_path, filename = get_best_model_download(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return FileResponse(
        model_path,
        media_type="application/octet-stream",
        filename=filename,
    )
