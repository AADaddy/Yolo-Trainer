from __future__ import annotations

# Compatibility wrapper around the newer training services.

import os
import threading
import traceback
import json
from pathlib import Path

from .processed_dataset_builder import rebuild_processed_dataset
from .run_metrics_service import extract_runtime_metrics
from .training_config_service import normalize_training_config, save_training_config
from .training_run_service import (
    create_run_record,
    delete_training_run,
    get_model_weight_path,
    get_training_run,
    get_next_queued_run,
    has_running_run,
    list_training_runs,
    reset_inflight_runs_for_startup,
    update_run_status,
)


TRAINING_TASKS: dict[int, threading.Thread] = {}
TRAINING_SCHEDULER_LOCK = threading.Lock()


def _get_training_runtime_options(device: str, workers: int, cache: bool, amp: bool) -> dict[str, object]:
    is_windows = os.name == "nt"
    use_cuda = str(device).lower() in {"cuda", "0", "cuda:0"}
    return {
        "workers": 0 if is_windows and workers > 0 else workers,
        "cache": cache,
        "amp": amp and use_cuda,
    }


def _get_augmentation_runtime_options(mosaic_enabled: bool, multiscale_enabled: bool) -> dict[str, object]:
    from ultralytics.cfg import DEFAULT_CFG

    # Store simple booleans in run metadata, but pass Ultralytics-native values:
    # mosaic is a probability, and newer multi_scale accepts a scale amount while
    # older installed versions accept a boolean. Keeping this translation here
    # preserves trustworthy comparisons without leaking library quirks into the UI.
    multi_scale_default = getattr(DEFAULT_CFG, "multi_scale", False)
    return {
        "mosaic": 1.0 if mosaic_enabled else 0.0,
        "multi_scale": bool(multiscale_enabled) if isinstance(multi_scale_default, bool) else (0.5 if multiscale_enabled else 0.0),
    }


def create_training_run(payload: dict) -> dict:
    if not payload.get("project_id"):
        raise ValueError("project_id is required.")
    if not payload.get("dataset_version_id"):
        raise ValueError("dataset_version_id is required.")

    normalized = normalize_training_config(payload)
    if not normalized["dataset_version_id"]:
        raise ValueError("A dataset version must be selected before training starts.")

    # Save only on start so unsaved edits are discarded when the user leaves the page.
    save_training_config(int(payload["project_id"]), normalized)

    run = create_run_record(
        project_id=int(payload["project_id"]),
        dataset_version_id=int(normalized["dataset_version_id"]),
        parameters=normalized,
    )
    start_next_queued_training()
    return get_training_run(run["id"])


def run_training_sync(run_id: int) -> None:
    try:
        from ultralytics import YOLO

        run = get_training_run(run_id)
        run_path = Path(run["run_path"])
        update_run_status(run_id, "running")
        run = get_training_run(run_id)
        parameters = dict(run["parameters_json"])

        # Processed training data is rebuilt only when the job actually starts running.
        # This prevents queued submissions from clearing the processed folder used by
        # the active run and guarantees a true one-at-a-time training queue.
        processed_dataset = rebuild_processed_dataset(
            project_id=int(run["project_id"]),
            dataset_version_id=int(run["dataset_version_id"]),
            split_ratio=str(parameters["split_ratio"]),
        )
        parameters["processed_dataset"] = processed_dataset
        _persist_run_parameters(run_id, run_path, parameters)
        data_yaml_path = Path(processed_dataset["data_yaml"])

        model = YOLO(str(get_model_weight_path(run["model_name"])))
        runtime_options = _get_training_runtime_options(
            parameters["device"],
            int(parameters["workers"]),
            bool(parameters["cache"]),
            bool(parameters["amp"]),
        )
        augmentation_options = _get_augmentation_runtime_options(
            bool(parameters.get("mosaic_enabled", True)),
            bool(parameters.get("multiscale_enabled", False)),
        )
        results = model.train(
            data=str(data_yaml_path),
            epochs=int(parameters["epochs"]),
            imgsz=int(parameters["imgsz"]),
            batch=int(parameters["batch"]),
            workers=int(runtime_options["workers"]),
            cache=bool(runtime_options["cache"]),
            rect=bool(parameters["rect"]),
            optimizer=str(parameters["optimizer"]),
            lr0=float(parameters["lr0"]),
            momentum=float(parameters["momentum"]),
            device=parameters["device"],
            amp=bool(runtime_options["amp"]),
            mosaic=augmentation_options["mosaic"],
            multi_scale=augmentation_options["multi_scale"],
            project=str(run_path),
            name="artifacts",
            exist_ok=True,
        )

        metrics = extract_runtime_metrics(results, run_path)
        metrics_path = run_path / "metrics.json"
        metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

        weights_dir = Path(results.save_dir) / "weights"
        for filename in ["best.pt", "last.pt"]:
            source = weights_dir / filename
            if source.exists():
                (run_path / filename).write_bytes(source.read_bytes())

        # Refresh model file size after top-level weights are copied into the run folder.
        metrics = extract_runtime_metrics(results, run_path)
        metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        update_run_status(run_id, "completed", metrics_json=metrics)
    except Exception as exc:  # pragma: no cover
        update_run_status(run_id, "failed", error_message=f"{exc}\n\n{traceback.format_exc()}")
    finally:
        TRAINING_TASKS.pop(run_id, None)
        start_next_queued_training()


def start_next_queued_training() -> None:
    with TRAINING_SCHEDULER_LOCK:
        _prune_finished_threads()
        if TRAINING_TASKS or has_running_run():
            return

        next_run = get_next_queued_run()
        if not next_run:
            return

        worker = threading.Thread(target=run_training_sync, args=(next_run["id"],), daemon=True)
        TRAINING_TASKS[next_run["id"]] = worker
        worker.start()


def _prune_finished_threads() -> None:
    finished_run_ids = [run_id for run_id, worker in TRAINING_TASKS.items() if not worker.is_alive()]
    for run_id in finished_run_ids:
        TRAINING_TASKS.pop(run_id, None)


def _persist_run_parameters(run_id: int, run_path: Path, parameters: dict) -> None:
    from backend.database import db_cursor

    with db_cursor(commit=True) as cursor:
        cursor.execute(
            "UPDATE training_runs SET parameters_json = ? WHERE id = ?",
            (json.dumps(parameters), run_id),
        )
    (run_path / "parameters.json").write_text(json.dumps(parameters, indent=2), encoding="utf-8")


def resume_training_queue() -> None:
    reset_inflight_runs_for_startup()
    start_next_queued_training()

__all__ = [
    "create_training_run",
    "delete_training_run",
    "get_training_run",
    "list_training_runs",
    "resume_training_queue",
]
