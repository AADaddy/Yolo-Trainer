from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.database import db_cursor


def enrich_run_metrics(run: dict[str, Any]) -> dict[str, Any]:
    """
    Build a comparison-friendly metrics payload for a run.

    Historical runs may only have accuracy metrics, while newer runs can also store
    inference time and artifact size. We derive what we can from the run folder and
    persist safe backfills so future reads stay cheap.
    """

    run_path = Path(run["run_path"])
    metrics = dict(run.get("metrics_json") or {})
    changed = False

    file_metrics = _read_json(run_path / "metrics.json")
    if file_metrics:
        for key, value in file_metrics.items():
            if metrics.get(key) != value:
                metrics[key] = value
                changed = True

    if metrics.get("model_file_size_mb") is None:
        model_file_size_mb = derive_model_file_size_mb(run_path)
        if model_file_size_mb is not None:
            metrics["model_file_size_mb"] = model_file_size_mb
            changed = True

    metrics.setdefault("inference_time_ms", None)
    metrics.setdefault("model_file_size_mb", None)

    if changed:
        _persist_run_metrics(run["id"], run_path, metrics)

    return metrics


def extract_runtime_metrics(results, run_path: Path) -> dict[str, float | None]:
    box_metrics = getattr(results, "results_dict", None) or {}
    speed_metrics = getattr(results, "speed", None) or {}

    return {
        "mAP50": _safe_float(box_metrics.get("metrics/mAP50(B)", 0.0)),
        "mAP50_95": _safe_float(box_metrics.get("metrics/mAP50-95(B)", 0.0)),
        "precision": _safe_float(box_metrics.get("metrics/precision(B)", 0.0)),
        "recall": _safe_float(box_metrics.get("metrics/recall(B)", 0.0)),
        # Ultralytics reports per-image stage timings in milliseconds when available.
        # We use inference time as the main deployment-speed signal because it is the
        # most practical latency metric for model comparison.
        "inference_time_ms": _safe_float(speed_metrics.get("inference"), default=None),
        "model_file_size_mb": derive_model_file_size_mb(run_path),
    }


def derive_model_file_size_mb(run_path: Path) -> float | None:
    for candidate in [run_path / "best.pt", run_path / "last.pt"]:
        if candidate.exists():
            return round(candidate.stat().st_size / (1024 * 1024), 2)
    return None


def _persist_run_metrics(run_id: int, run_path: Path, metrics: dict[str, Any]) -> None:
    serialized = json.dumps(metrics)
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            "UPDATE training_runs SET metrics_json = ? WHERE id = ?",
            (serialized, run_id),
        )
    (run_path / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _safe_float(value: Any, default: float | None = 0.0) -> float | None:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default
