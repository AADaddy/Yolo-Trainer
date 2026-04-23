from __future__ import annotations

import json
from datetime import datetime, timezone

from backend.database import db_cursor
from .dataset_splitter import validate_split_ratio
from .dataset_version_service import get_project


DEFAULT_TRAINING_CONFIG = {
    "dataset_version_id": "",
    "split_ratio": "80/20",
    "yolo_version": "YOLO11",
    "model_size": "s",
    "epochs": 100,
    "imgsz": 1280,
    "batch": -1,
    "workers": 2,
    "cache": True,
    "rect": True,
    "optimizer": "AdamW",
    "lr0": 0.001,
    "momentum": 0.9,
    "device": "cuda",
    "amp": True,
    # Advanced options use conservative product defaults: mosaic stays on
    # because Ultralytics defaults to it for generalization, while multi-scale
    # starts off to keep first comparisons more controlled.
    "mosaic_enabled": True,
    "multiscale_enabled": False,
}


def get_training_config(project_id: int) -> dict:
    get_project(project_id)
    with db_cursor() as cursor:
        cursor.execute("SELECT config_json FROM training_configs WHERE project_id = ?", (project_id,))
        row = cursor.fetchone()
    if not row:
        return DEFAULT_TRAINING_CONFIG.copy()
    stored = json.loads(row["config_json"] or "{}")
    return DEFAULT_TRAINING_CONFIG | stored


def save_training_config(project_id: int, config: dict) -> dict:
    get_project(project_id)
    normalized = normalize_training_config(config)
    saved_at = datetime.now(timezone.utc).isoformat()
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            """
            INSERT INTO training_configs (project_id, config_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(project_id) DO UPDATE
            SET config_json = excluded.config_json, updated_at = excluded.updated_at
            """,
            (project_id, json.dumps(normalized), saved_at),
        )
    return normalized


def normalize_training_config(config: dict) -> dict:
    normalized = DEFAULT_TRAINING_CONFIG | config
    normalized["split_ratio"] = validate_split_ratio(str(normalized["split_ratio"]))
    normalized["epochs"] = int(normalized["epochs"])
    normalized["imgsz"] = int(normalized["imgsz"])
    normalized["batch"] = int(normalized["batch"])
    normalized["workers"] = int(normalized["workers"])
    normalized["cache"] = _to_bool(normalized["cache"])
    normalized["rect"] = _to_bool(normalized["rect"])
    normalized["lr0"] = float(normalized["lr0"])
    normalized["momentum"] = float(normalized["momentum"])
    normalized["amp"] = _to_bool(normalized["amp"])
    normalized["mosaic_enabled"] = _to_bool(normalized["mosaic_enabled"])
    normalized["multiscale_enabled"] = _to_bool(normalized["multiscale_enabled"])
    normalized["dataset_version_id"] = int(normalized["dataset_version_id"]) if str(normalized["dataset_version_id"]).strip() else ""
    normalized["device"] = str(normalized["device"])
    normalized["optimizer"] = str(normalized["optimizer"])
    normalized["yolo_version"] = str(normalized["yolo_version"])
    normalized["model_size"] = str(normalized["model_size"])
    return normalized


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)
