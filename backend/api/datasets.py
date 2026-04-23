from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from backend.models import DatasetVersionCreate, DatasetVersionDeleteRequest
from backend.services.dataset_browser import browse_directories, open_folder_dialog
from backend.services.dataset_cache_manager import prepare_processed_dataset
from backend.services.dataset_import_service import start_dataset_import
from backend.services.dataset_inspection_service import (
    get_dataset_item_image_path,
    get_inspection_filters,
    get_inspection_preview,
    list_inspection_items,
)
from backend.services.dataset_statistics_service import get_dashboard_statistics
from backend.services.dataset_version_service import (
    delete_dataset_version,
    get_dataset_version,
    list_dataset_versions,
)


router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.post("/projects/{project_id}")
def import_dataset(project_id: int, payload: DatasetVersionCreate) -> dict:
    # Dataset import is intentionally async so the UI can show cleanse progress
    # without blocking the request or mixing this workflow into training.
    try:
        return start_dataset_import(project_id, payload.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/projects/{project_id}")
def get_project_datasets(project_id: int) -> list[dict]:
    return list_dataset_versions(project_id)


@router.get("/browse")
def browse_dataset_directories(path: str | None = Query(default=None)) -> dict:
    try:
        return browse_directories(path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/browse-dialog")
def browse_dataset_dialog(path: str | None = Query(default=None)) -> dict:
    try:
        return open_folder_dialog(path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{dataset_version_id}")
def get_dataset(dataset_version_id: int) -> dict:
    try:
        return get_dataset_version(dataset_version_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{dataset_version_id}/validation")
def get_validation_report(dataset_version_id: int) -> dict:
    return get_dataset_version(dataset_version_id)["validation_report"]


@router.get("/{dataset_version_id}/statistics")
def get_statistics(dataset_version_id: int) -> dict:
    return get_dashboard_statistics(dataset_version_id)


@router.get("/{dataset_version_id}/cleaning")
def get_cleaning_report(dataset_version_id: int) -> dict:
    return get_dataset_version(dataset_version_id)["cleaning_report"]


@router.get("/{dataset_version_id}/dashboard")
def get_dataset_dashboard(dataset_version_id: int) -> dict:
    try:
        return get_dashboard_statistics(dataset_version_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/inspection/{dataset_version_id}/filters")
def get_dataset_inspection_filters(dataset_version_id: int) -> dict:
    try:
        return get_inspection_filters(dataset_version_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/inspection/{dataset_version_id}/items")
def get_dataset_inspection_items(
    dataset_version_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    resolution: str | None = Query(default=None),
    area_bucket: str | None = Query(default=None),
    label_state: str | None = Query(default=None),
    filename: str | None = Query(default=None),
) -> dict:
    try:
        return list_inspection_items(
            dataset_version_id=dataset_version_id,
            page=page,
            page_size=page_size,
            resolution=resolution,
            area_bucket=area_bucket,
            label_state=label_state,
            filename=filename,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/inspection/{dataset_version_id}/items/{dataset_item_id}")
def get_dataset_inspection_item(dataset_version_id: int, dataset_item_id: int) -> dict:
    try:
        return get_inspection_preview(dataset_version_id, dataset_item_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/inspection/{dataset_version_id}/items/{dataset_item_id}/image")
def get_dataset_inspection_image(dataset_version_id: int, dataset_item_id: int) -> FileResponse:
    try:
        image_path = get_dataset_item_image_path(dataset_version_id, dataset_item_id)
        return FileResponse(image_path)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{dataset_version_id}/progress")
def get_dataset_progress(dataset_version_id: int) -> dict:
    return get_dataset_version(dataset_version_id)["progress_json"]


@router.delete("/{dataset_version_id}")
def remove_dataset_version(dataset_version_id: int, payload: DatasetVersionDeleteRequest) -> dict:
    try:
        return delete_dataset_version(dataset_version_id, payload.confirmation)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{dataset_version_id}/prepare-cache")
def prepare_dataset_cache(dataset_version_id: int) -> dict:
    try:
        return prepare_processed_dataset(dataset_version_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
