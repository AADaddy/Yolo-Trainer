from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import PROCESSED_STORAGE_DIR, PROJECTS_STORAGE_DIR
from backend.database import db_cursor
from .dataset_progress_service import make_progress_payload


PROJECTS_ROOT = PROJECTS_STORAGE_DIR


def slugify(value: str) -> str:
    return "".join(character.lower() if character.isalnum() else "-" for character in value).strip("-")


def get_project(project_id: int) -> dict:
    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        project = cursor.fetchone()
    if not project:
        raise ValueError(f"Project {project_id} was not found.")
    return project


def get_project_dataset_dirs(project_id: int, project_name: str) -> tuple[Path, Path, Path, Path]:
    project_root = PROJECTS_ROOT / f"{project_id}-{slugify(project_name)}"
    dataset_root = project_root / "dataset"
    images_dir = dataset_root / "images"
    labels_dir = dataset_root / "labels"
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)
    return project_root, dataset_root, images_dir, labels_dir


def create_dataset_version_record(project_id: int, version_name: str, note: str) -> dict:
    get_project(project_id)
    created_at = datetime.now(timezone.utc).isoformat()
    progress = make_progress_payload("queued", 0, "Import queued.", "validating_dataset")
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            """
            INSERT INTO dataset_versions (
                project_id, version_name, note, created_at, status, progress_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (project_id, version_name, note, created_at, "queued", json.dumps(progress)),
        )
        dataset_version_id = cursor.lastrowid
    return get_dataset_version(dataset_version_id)


def complete_dataset_version_import(
    dataset_version_id: int,
    accepted_items: list[dict],
    validation_report: dict,
    cleaning_report: dict,
    stats_report: dict,
    import_summary_json: dict,
) -> dict:
    class_count = int(stats_report.get("number_of_classes", 0))
    with db_cursor(commit=True) as cursor:
        for item in accepted_items:
            cursor.execute(
                """
                INSERT INTO dataset_items (
                    project_id, dataset_version_id, image_filename, label_filename, image_hash, label_hash,
                    width, height, created_at, source_image_name, source_label_name
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["project_id"],
                    dataset_version_id,
                    item["stored_image_filename"],
                    item["stored_label_filename"],
                    item["image_hash"],
                    item["label_hash"],
                    item["width"],
                    item["height"],
                    item["created_at"],
                    item["source_image_name"],
                    item["source_label_name"],
                ),
            )
        cursor.execute(
            """
            UPDATE dataset_versions
            SET status = ?, added_image_count = ?, class_count = ?, progress_json = ?,
                validation_report = ?, cleaning_report = ?, stats_report = ?, import_summary_json = ?,
                error_message = ''
            WHERE id = ?
            """,
            (
                "completed",
                len(accepted_items),
                class_count,
                json.dumps(make_progress_payload("completed", 100, "Dataset import complete.", "completed")),
                json.dumps(validation_report),
                json.dumps(cleaning_report),
                json.dumps(stats_report),
                json.dumps(import_summary_json),
                dataset_version_id,
            ),
        )
    dataset_version = get_dataset_version(dataset_version_id)
    refresh_dataset_version_rollups(dataset_version["project_id"])
    clear_processed_cache(dataset_version["project_id"])
    return get_dataset_version(dataset_version_id)


def fail_dataset_version_import(dataset_version_id: int, error_message: str) -> None:
    payload = make_progress_payload("failed", 100, "Dataset import failed.", "completed")
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            """
            UPDATE dataset_versions
            SET status = ?, progress_json = ?, error_message = ?
            WHERE id = ?
            """,
            ("failed", json.dumps(payload), error_message, dataset_version_id),
        )


def list_dataset_versions(project_id: int) -> list[dict]:
    with db_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM dataset_versions WHERE project_id = ? ORDER BY created_at DESC, id DESC",
            (project_id,),
        )
        rows = cursor.fetchall()
    return [_decode_dataset_row(row) for row in rows]


def get_dataset_version(dataset_version_id: int) -> dict:
    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM dataset_versions WHERE id = ?", (dataset_version_id,))
        row = cursor.fetchone()
    if not row:
        raise ValueError(f"Dataset version {dataset_version_id} was not found.")
    return _decode_dataset_row(row)


def get_existing_project_hashes(project_id: int) -> set[str]:
    with db_cursor() as cursor:
        cursor.execute("SELECT image_hash FROM dataset_items WHERE project_id = ?", (project_id,))
        return {row["image_hash"] for row in cursor.fetchall()}


def list_dataset_items_for_version(dataset_version_id: int) -> list[dict]:
    with db_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM dataset_items WHERE dataset_version_id = ? ORDER BY id ASC",
            (dataset_version_id,),
        )
        rows = cursor.fetchall()
    return [_decode_dataset_item(row) for row in rows]


def list_cumulative_dataset_items(dataset_version_id: int) -> list[dict]:
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT di.*
            FROM dataset_items di
            INNER JOIN dataset_versions version_scope ON version_scope.id = di.dataset_version_id
            INNER JOIN dataset_versions selected ON selected.id = ?
            WHERE version_scope.project_id = selected.project_id
              AND (
                    version_scope.created_at < selected.created_at
                    OR (version_scope.created_at = selected.created_at AND version_scope.id <= selected.id)
              )
            ORDER BY version_scope.created_at ASC, version_scope.id ASC, di.id ASC
            """,
            (dataset_version_id,),
        )
        rows = cursor.fetchall()
    return [_decode_dataset_item(row) for row in rows]


def refresh_dataset_version_rollups(project_id: int) -> None:
    # Delta versions store only what that import accepted, while rollups cache the
    # cumulative totals/fingerprint needed for list views and later training prep.
    with db_cursor() as cursor:
        cursor.execute(
            "SELECT id FROM dataset_versions WHERE project_id = ? ORDER BY created_at ASC, id ASC",
            (project_id,),
        )
        version_ids = [row["id"] for row in cursor.fetchall()]

    cumulative_hashes: list[str] = []
    for dataset_version_id in version_ids:
        items = list_dataset_items_for_version(dataset_version_id)
        cumulative_hashes.extend(item["image_hash"] for item in items)
        fingerprint = hashlib.sha256(json.dumps(cumulative_hashes, sort_keys=False).encode("utf-8")).hexdigest()
        with db_cursor(commit=True) as cursor:
            cursor.execute(
                """
                UPDATE dataset_versions
                SET cumulative_image_count = ?, cumulative_fingerprint = ?
                WHERE id = ?
                """,
                (len(cumulative_hashes), fingerprint, dataset_version_id),
            )


def delete_dataset_version(dataset_version_id: int, confirmation: str) -> dict:
    if confirmation != "DELETE":
        raise ValueError("Deletion requires exact confirmation: DELETE")

    dataset_version = get_dataset_version(dataset_version_id)
    project = get_project(dataset_version["project_id"])
    project_root, _, images_dir, labels_dir = get_project_dataset_dirs(project["id"], project["name"])
    items = list_dataset_items_for_version(dataset_version_id)

    with db_cursor() as cursor:
        cursor.execute(
            "SELECT run_path FROM training_runs WHERE dataset_version_id = ?",
            (dataset_version_id,),
        )
        run_paths = [Path(row["run_path"]) for row in cursor.fetchall()]

    with db_cursor(commit=True) as cursor:
        cursor.execute("DELETE FROM training_runs WHERE dataset_version_id = ?", (dataset_version_id,))
        cursor.execute("DELETE FROM dataset_versions WHERE id = ?", (dataset_version_id,))

    # Files are safe to remove because each stored dataset item belongs to exactly
    # one dataset version and duplicates are rejected before insert.
    for item in items:
        image_path = images_dir / item["image_filename"]
        label_path = labels_dir / item["label_filename"]
        if image_path.exists():
            image_path.unlink()
        if label_path.exists():
            label_path.unlink()

    for run_path in run_paths:
        if run_path.exists():
            shutil.rmtree(run_path, ignore_errors=True)

    clear_processed_cache(dataset_version["project_id"])
    refresh_dataset_version_rollups(project["id"])

    if project_root.exists():
        _remove_empty_dirs(project_root / "dataset")

    return {"status": "deleted", "dataset_version_id": dataset_version_id}


def clear_processed_cache(project_id: int) -> None:
    processed_dir = PROCESSED_STORAGE_DIR / str(project_id)
    if processed_dir.exists():
        shutil.rmtree(processed_dir, ignore_errors=True)


def _remove_empty_dirs(root: Path) -> None:
    for directory in [root / "images", root / "labels", root]:
        if directory.exists() and not any(directory.iterdir()):
            directory.rmdir()


def _decode_dataset_item(row: dict[str, Any]) -> dict[str, Any]:
    row["image_relative_path"] = row["image_filename"]
    row["label_relative_path"] = row["label_filename"]
    row["image_name"] = row["image_filename"]
    row["label_name"] = row["label_filename"]
    return row


def _decode_dataset_row(row: dict[str, Any]) -> dict[str, Any]:
    row["progress_json"] = json.loads(row.get("progress_json") or "{}")
    row["validation_report"] = json.loads(row.get("validation_report") or "{}")
    row["cleaning_report"] = json.loads(row.get("cleaning_report") or "{}")
    row["stats_report"] = json.loads(row.get("stats_report") or "{}")
    row["import_summary_json"] = json.loads(row.get("import_summary_json") or "{}")
    row["version"] = row["version_name"]
    row["image_count"] = row["cumulative_image_count"]
    row["fingerprint"] = row["cumulative_fingerprint"]
    return row
