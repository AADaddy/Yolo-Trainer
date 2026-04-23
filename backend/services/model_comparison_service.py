from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .dataset_version_service import get_dataset_version
from .run_metrics_service import enrich_run_metrics
from .trainer import get_training_run, list_training_runs


SORTABLE_FIELDS = {
    "run_id": "id",
    "dataset_version": "dataset_version",
    "model": "model",
    "mAP50": "mAP50",
    "mAP50_95": "mAP50_95",
    "precision": "precision",
    "recall": "recall",
    "inference_time_ms": "inference_time_ms",
    "imgsz": "imgsz",
    "started_at": "started_at",
}


def build_comparison_payload(
    project_id: int | None = None,
    dataset_version_id: int | None = None,
    yolo_version: str | None = None,
    model_size: str | None = None,
    sort_by: str = "started_at",
    sort_order: str = "desc",
) -> dict[str, Any]:
    completed_runs = [run for run in list_training_runs(project_id=project_id) if run.get("status") == "completed"]
    all_rows = [_build_comparison_row(run) for run in completed_runs]

    filtered_rows = [
        row
        for row in all_rows
        if (dataset_version_id is None or row["dataset_version_id"] == dataset_version_id)
        and (not yolo_version or row["yolo_version"] == yolo_version)
        and (not model_size or row["model_size"] == model_size)
    ]

    sorted_rows = _sort_rows(filtered_rows, sort_by=sort_by, sort_order=sort_order)

    return {
        "rows": sorted_rows,
        "filters": build_filter_options(all_rows),
        "summaries": build_summary_cards(filtered_rows),
        "sort": {
            "sort_by": sort_by if sort_by in SORTABLE_FIELDS else "started_at",
            "sort_order": "asc" if str(sort_order).lower() == "asc" else "desc",
        },
        "counts": {
            "total_completed_runs": len(all_rows),
            "filtered_runs": len(filtered_rows),
            "scatter_points": len([row for row in filtered_rows if row["inference_time_ms"] is not None]),
        },
    }


def build_filter_options(rows: list[dict[str, Any]]) -> dict[str, Any]:
    dataset_versions = sorted(
        {(
            row["dataset_version_id"],
            row["dataset_version"],
        ) for row in rows},
        key=lambda item: item[1],
    )
    yolo_versions = sorted({row["yolo_version"] for row in rows if row["yolo_version"]})
    model_sizes = sorted({row["model_size"] for row in rows if row["model_size"]})
    return {
        "dataset_versions": [{"id": dataset_id, "label": label} for dataset_id, label in dataset_versions],
        "yolo_versions": yolo_versions,
        "model_sizes": model_sizes,
    }


def build_summary_cards(rows: list[dict[str, Any]]) -> dict[str, Any]:
    best_accuracy = max(rows, key=lambda row: row["mAP50_95"], default=None)

    speed_candidates = [row for row in rows if row["inference_time_ms"] is not None]
    best_speed = min(speed_candidates, key=lambda row: row["inference_time_ms"], default=None)

    balanced_candidates = _rows_with_balanced_score(rows)
    best_balanced = max(balanced_candidates, key=lambda row: row["balanced_score"], default=None)

    return {
        "best_accuracy": _summary_payload(
            best_accuracy,
            reason_template="Highest mAP50-95 at {value:.4f}.",
            value_key="mAP50_95",
        ),
        "best_speed": _summary_payload(
            best_speed,
            reason_template="Lowest inference time at {value:.2f} ms/image.",
            value_key="inference_time_ms",
        ),
        "best_balanced": _summary_payload(
            best_balanced,
            reason_template="Best weighted balance score at {value:.3f}.",
            value_key="balanced_score",
        ),
    }


def _build_comparison_row(run: dict[str, Any]) -> dict[str, Any]:
    metrics = enrich_run_metrics(run)
    dataset_version = get_dataset_version(run["dataset_version_id"])
    parameters = run.get("parameters_json") or {}
    return {
        "id": run["id"],
        "run_name": run["run_name"],
        "dataset_version_id": run["dataset_version_id"],
        "dataset_version": dataset_version["version"],
        "yolo_version": run["yolo_version"],
        "model_size": run["model_size"],
        "model": run["model_name"],
        "mAP50": _to_float(metrics.get("mAP50")),
        "mAP50_95": _to_float(metrics.get("mAP50_95")),
        "precision": _to_float(metrics.get("precision")),
        "recall": _to_float(metrics.get("recall")),
        "inference_time_ms": _to_optional_float(metrics.get("inference_time_ms")),
        "model_file_size_mb": _to_optional_float(metrics.get("model_file_size_mb")),
        "imgsz": _to_optional_int(parameters.get("imgsz")),
        "started_at": run["created_at"],
        "mosaic_enabled": bool(parameters.get("mosaic_enabled", True)),
        "multiscale_enabled": bool(parameters.get("multiscale_enabled", False)),
        "parameters": parameters,
        "has_best_model_artifact": resolve_best_model_artifact(run) is not None,
    }


def get_best_model_download(run_id: int) -> tuple[Path, str]:
    run = get_training_run(run_id)
    best_model_path = resolve_best_model_artifact(run)
    if best_model_path is None:
        raise FileNotFoundError(f"best.pt was not found for training run {run_id}.")
    return best_model_path, build_model_download_filename(run)


def resolve_best_model_artifact(run: dict[str, Any]) -> Path | None:
    run_path = Path(run["run_path"])
    candidates = [
        run_path / "best.pt",
        run_path / "artifacts" / "weights" / "best.pt",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def build_model_download_filename(run: dict[str, Any]) -> str:
    parameters = run.get("parameters_json") or {}
    metrics = enrich_run_metrics(run)
    dataset_version = parameters.get("dataset_version")
    if not dataset_version:
        dataset_version = get_dataset_version(run["dataset_version_id"])["version"]

    parts = [
        f"run_{run['id']:03d}",
        dataset_version,
        parameters.get("model_name") or run.get("model_name"),
        f"img{parameters.get('imgsz') or run.get('imgsz') or 'unknown'}",
    ]
    map50 = _to_optional_float(metrics.get("mAP50"))
    if map50 is not None:
        parts.append(f"map50-{map50:.2f}")

    # The browser-visible filename is generated from saved run metadata, not
    # current form defaults, and each part is scrubbed so Windows-safe downloads
    # remain readable even when users name dataset versions freely.
    stem = "_".join(_sanitize_filename_part(part) for part in parts if part)
    fallback_stem = f"run_{run['id']:03d}_best"
    return f"{stem[:120] or fallback_stem}.pt"


def _sanitize_filename_part(value: Any) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value).strip())
    cleaned = cleaned.strip("._-")
    return cleaned or "unknown"


def _rows_with_balanced_score(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scored_rows = [dict(row) for row in rows if row["inference_time_ms"] is not None]
    if not scored_rows:
        return []

    accuracies = [row["mAP50_95"] for row in scored_rows]
    latencies = [row["inference_time_ms"] for row in scored_rows]
    accuracy_min, accuracy_max = min(accuracies), max(accuracies)
    latency_min, latency_max = min(latencies), max(latencies)

    for row in scored_rows:
        accuracy_score = _normalize(row["mAP50_95"], accuracy_min, accuracy_max, invert=False)
        latency_score = _normalize(row["inference_time_ms"], latency_min, latency_max, invert=True)
        # Best balanced choice intentionally prefers stricter accuracy first and then
        # rewards lower latency, which helps compare realistic deployability tradeoffs.
        row["balanced_score"] = round((accuracy_score * 0.65) + (latency_score * 0.35), 4)
    return scored_rows


def _sort_rows(rows: list[dict[str, Any]], sort_by: str, sort_order: str) -> list[dict[str, Any]]:
    field = SORTABLE_FIELDS.get(sort_by, "started_at")
    reverse = str(sort_order).lower() != "asc"
    populated = [row for row in rows if row.get(field) is not None]
    missing = [row for row in rows if row.get(field) is None]

    def sort_key(row: dict[str, Any]) -> Any:
        value = row.get(field)
        if isinstance(value, str):
            return value.lower()
        return value

    return sorted(populated, key=sort_key, reverse=reverse) + missing


def _summary_payload(row: dict[str, Any] | None, reason_template: str, value_key: str) -> dict[str, Any] | None:
    if not row:
        return None
    value = row.get(value_key)
    return {
        "run_id": row["id"],
        "model": row["model"],
        "dataset_version": row["dataset_version"],
        "reason": reason_template.format(value=value if value is not None else 0),
    }


def _normalize(value: float, minimum: float, maximum: float, invert: bool) -> float:
    if maximum == minimum:
        return 1.0
    ratio = (value - minimum) / (maximum - minimum)
    return 1 - ratio if invert else ratio


def _to_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _to_optional_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_optional_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
