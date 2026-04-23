from __future__ import annotations

import json
from datetime import datetime, timezone

from backend.database import db_cursor


IMPORT_STEPS = [
    "validating_dataset",
    "checking_image_label_pairs",
    "detecting_duplicates",
    "validating_labels",
    "saving_accepted_files",
    "creating_dataset_version",
    "completed",
]


def make_progress_payload(status: str, percent: int, message: str, current_step: str | None = None) -> dict:
    return {
        "status": status,
        "percent": percent,
        "message": message,
        "current_step": current_step,
        "steps": IMPORT_STEPS,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def update_dataset_progress(dataset_version_id: int, status: str, percent: int, message: str, current_step: str) -> None:
    # Import progress lives on the dataset version so the UI can poll one stable
    # resource from the moment the import starts until the delta version commits.
    payload = json.dumps(make_progress_payload(status, percent, message, current_step))
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            "UPDATE dataset_versions SET status = ?, progress_json = ? WHERE id = ?",
            (status, payload, dataset_version_id),
        )
