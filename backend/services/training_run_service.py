from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import PROJECT_ROOT
from backend.database import db_cursor
from .dataset_version_service import PROJECTS_ROOT, get_dataset_version, get_project, slugify


MAP50_COLOR_THRESHOLDS = {
    "high": 0.7,
    "medium": 0.5,
}


def build_model_name(yolo_version: str, model_size: str) -> str:
    supported_yolo_versions = {"YOLO8": "yolov8", "YOLO11": "yolo11", "YOLO26": "yolo26"}
    supported_model_sizes = {"n", "s", "m", "l", "x"}
    if yolo_version not in supported_yolo_versions:
        raise ValueError(f"Unsupported YOLO version: {yolo_version}")
    if model_size not in supported_model_sizes:
        raise ValueError(f"Unsupported model size: {model_size}")
    return f"{supported_yolo_versions[yolo_version]}{model_size}"


def get_model_weight_path(model_name: str) -> Path:
    return PROJECT_ROOT / f"{model_name}.pt"


def validate_model_weight_available(model_name: str) -> Path:
    weight_path = get_model_weight_path(model_name)
    if weight_path.exists():
        return weight_path
    if model_name.startswith("yolo26"):
        raise ValueError(
            f"Model weights were not found for {model_name}. YOLO26 is a future placeholder; "
            f"add {weight_path.name} to {PROJECT_ROOT} before training with it."
        )
    raise ValueError(f"Model weights were not found: {weight_path}")


def create_run_record(project_id: int, dataset_version_id: int, parameters: dict[str, Any]) -> dict:
    project = get_project(project_id)
    dataset_version = get_dataset_version(dataset_version_id)
    created_at = datetime.now(timezone.utc).isoformat()
    run_name = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_root = PROJECTS_ROOT / f"{project['id']}-{slugify(project['name'])}" / "runs" / run_name
    model_name = build_model_name(parameters["yolo_version"], parameters["model_size"])
    validate_model_weight_available(model_name)
    run_root.mkdir(parents=True, exist_ok=True)

    stored_parameters = {
        **parameters,
        "project_id": project_id,
        "dataset_version_id": dataset_version_id,
        "dataset_version": dataset_version["version"],
        "model_name": model_name,
    }

    with db_cursor(commit=True) as cursor:
        cursor.execute(
            """
            INSERT INTO training_runs (
                project_id, dataset_version_id, run_name, yolo_version, model_size, model_name,
                split_ratio, epochs, imgsz, batch, workers, cache, rect, optimizer, lr0, momentum,
                device, amp, status, created_at, updated_at, run_path, metrics_json, parameters_json, error_message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                dataset_version_id,
                run_name,
                parameters["yolo_version"],
                parameters["model_size"],
                model_name,
                parameters["split_ratio"],
                parameters["epochs"],
                parameters["imgsz"],
                parameters["batch"],
                parameters["workers"],
                1 if parameters["cache"] else 0,
                1 if parameters["rect"] else 0,
                parameters["optimizer"],
                parameters["lr0"],
                parameters["momentum"],
                parameters["device"],
                1 if parameters["amp"] else 0,
                "queued",
                created_at,
                created_at,
                str(run_root),
                json.dumps({}),
                json.dumps(stored_parameters),
                "",
            ),
        )
        run_id = cursor.lastrowid

    run = get_training_run(run_id)
    (Path(run["run_path"]) / "parameters.json").write_text(json.dumps(run["parameters_json"], indent=2), encoding="utf-8")
    return run


def update_run_status(run_id: int, status: str, metrics_json: dict[str, Any] | None = None, error_message: str = "") -> None:
    updated_at = datetime.now(timezone.utc).isoformat()
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            """
            UPDATE training_runs
            SET status = ?, updated_at = ?, metrics_json = COALESCE(?, metrics_json), error_message = ?
            WHERE id = ?
            """,
            (
                status,
                updated_at,
                json.dumps(metrics_json) if metrics_json is not None else None,
                error_message,
                run_id,
            ),
        )


def get_training_run(run_id: int) -> dict:
    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM training_runs WHERE id = ?", (run_id,))
        row = cursor.fetchone()
    if not row:
        raise ValueError(f"Training run {run_id} was not found.")
    return _decode_training_row(row)


def list_training_runs(project_id: int | None = None) -> list[dict]:
    query = "SELECT * FROM training_runs"
    params: tuple[Any, ...] = ()
    if project_id is not None:
        query += " WHERE project_id = ?"
        params = (project_id,)
    query += " ORDER BY created_at DESC, id DESC"
    with db_cursor() as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()
    return [_decode_training_row(row) for row in rows]


def get_next_queued_run() -> dict | None:
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT *
            FROM training_runs
            WHERE status = 'queued'
            ORDER BY created_at ASC, id ASC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
    return _decode_training_row(row) if row else None


def has_running_run() -> bool:
    with db_cursor() as cursor:
        cursor.execute("SELECT 1 FROM training_runs WHERE status = 'running' LIMIT 1")
        return cursor.fetchone() is not None


def reset_inflight_runs_for_startup() -> None:
    # Training runs execute in-process, so any "running" row left behind after a
    # backend restart is stale and should return to the queue.
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            """
            UPDATE training_runs
            SET status = 'queued', error_message = ''
            WHERE status = 'running'
            """
        )


def delete_training_run(run_id: int, confirmation: str) -> dict:
    if confirmation != "DELETE":
        raise ValueError("Deletion requires exact confirmation: DELETE")
    run = get_training_run(run_id)
    run_path = Path(run["run_path"])
    with db_cursor(commit=True) as cursor:
        cursor.execute("DELETE FROM training_runs WHERE id = ?", (run_id,))
    if run_path.exists():
        shutil.rmtree(run_path, ignore_errors=True)
    return {"status": "deleted", "run_id": run_id}


def color_for_map50(value: float) -> str:
    # Thresholds are centralized so UI rendering and future policy changes stay aligned.
    if value > MAP50_COLOR_THRESHOLDS["high"]:
        return "high"
    if value >= MAP50_COLOR_THRESHOLDS["medium"]:
        return "medium"
    return "low"


def _decode_training_row(row: dict) -> dict:
    row["metrics_json"] = json.loads(row["metrics_json"] or "{}")
    row["parameters_json"] = json.loads(row["parameters_json"] or "{}")
    row["cache"] = bool(row.get("cache"))
    row["rect"] = bool(row.get("rect"))
    row["amp"] = bool(row.get("amp"))
    row["map50_color"] = color_for_map50(float(row["metrics_json"].get("mAP50", 0.0)))
    return row
