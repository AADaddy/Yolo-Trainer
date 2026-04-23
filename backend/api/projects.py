from __future__ import annotations

from datetime import datetime, timezone
import shutil

from fastapi import APIRouter, HTTPException

from backend.config import PROCESSED_STORAGE_DIR, PROJECTS_STORAGE_DIR
from backend.database import db_cursor
from backend.models import ProjectCreate
from backend.services.dataset_version_service import slugify


router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
def list_projects() -> list[dict]:
    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM projects ORDER BY created_at DESC")
        return cursor.fetchall()


@router.post("")
def create_project(payload: ProjectCreate) -> dict:
    created_at = datetime.now(timezone.utc).isoformat()
    try:
        with db_cursor(commit=True) as cursor:
            cursor.execute(
                """
                INSERT INTO projects (name, camera_name, description, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (payload.name, payload.camera_name, payload.description, created_at),
            )
            project_id = cursor.lastrowid
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        return cursor.fetchone()


@router.get("/{project_id}")
def get_project(project_id: int) -> dict:
    project = _get_project_or_404(project_id)
    return project


@router.put("/{project_id}")
def update_project(project_id: int, payload: ProjectCreate) -> dict:
    project = _get_project_or_404(project_id)
    try:
        with db_cursor(commit=True) as cursor:
            cursor.execute(
                """
                UPDATE projects
                SET name = ?, camera_name = ?, description = ?
                WHERE id = ?
                """,
                (payload.name, payload.camera_name, payload.description, project_id),
            )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _rename_project_storage_if_needed(project, payload.name)
    return _get_project_or_404(project_id)


@router.delete("/{project_id}")
def delete_project(project_id: int) -> dict:
    project = _get_project_or_404(project_id)
    project_storage_path = PROJECTS_STORAGE_DIR / f"{project_id}-{slugify(project['name'])}"
    processed_storage_path = PROCESSED_STORAGE_DIR / str(project_id)

    try:
        with db_cursor(commit=True) as cursor:
            cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if project_storage_path.exists():
        shutil.rmtree(project_storage_path, ignore_errors=True)
    if processed_storage_path.exists():
        shutil.rmtree(processed_storage_path, ignore_errors=True)

    return {"status": "deleted", "project_id": project_id}


def _get_project_or_404(project_id: int) -> dict:
    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        project = cursor.fetchone()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _rename_project_storage_if_needed(project: dict, new_name: str) -> None:
    old_path = PROJECTS_STORAGE_DIR / f"{project['id']}-{slugify(project['name'])}"
    new_path = PROJECTS_STORAGE_DIR / f"{project['id']}-{slugify(new_name)}"
    if old_path == new_path or not old_path.exists():
        return
    if new_path.exists():
        shutil.rmtree(new_path, ignore_errors=True)
    old_path.rename(new_path)
