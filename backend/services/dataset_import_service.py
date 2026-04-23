from __future__ import annotations

import shutil
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .dataset_cleaner import build_import_reports
from .duplicate_detector import detect_duplicates
from .dataset_progress_service import update_dataset_progress
from .dataset_validator import (
    compute_file_sha256,
    read_image_metadata,
    scan_dataset_source,
    validate_import_structure,
    validate_yolo_label_file,
)
from .dataset_version_service import (
    complete_dataset_version_import,
    create_dataset_version_record,
    get_dataset_version,
    get_existing_project_hashes,
    get_project,
    get_project_dataset_dirs,
    fail_dataset_version_import,
)


IMPORT_TASKS: dict[int, threading.Thread] = {}
VISUAL_DUP_THRESHOLD_OFF = -1
DEFAULT_VISUAL_DUP_THRESHOLD = VISUAL_DUP_THRESHOLD_OFF


def start_dataset_import(project_id: int, payload: dict[str, Any]) -> dict:
    version_name = (payload.get("version") or "").strip()
    if not version_name:
        raise ValueError("Version name is required.")
    if (payload.get("import_mode") or "").lower() == "labelstudio":
        raise ValueError("Label Studio import is Coming Soon.")
    payload["visual_dup_threshold"] = _normalize_visual_dup_threshold(payload.get("visual_dup_threshold"))

    dataset_version = create_dataset_version_record(project_id, version_name, (payload.get("note") or "").strip())
    worker = threading.Thread(target=run_dataset_import_sync, args=(dataset_version["id"], payload), daemon=True)
    worker.start()
    IMPORT_TASKS[dataset_version["id"]] = worker
    return dataset_version


def run_dataset_import_sync(dataset_version_id: int, payload: dict[str, Any]) -> None:
    copied_paths: list[Path] = []
    try:
        dataset_version = get_dataset_version(dataset_version_id)
        project = get_project(dataset_version["project_id"])
        _, _, project_images_dir, project_labels_dir = get_project_dataset_dirs(project["id"], project["name"])
        images_dir, labels_dir = resolve_import_source(payload)

        update_dataset_progress(dataset_version_id, "running", 10, "Validating dataset structure.", "validating_dataset")
        validate_import_structure(images_dir, labels_dir)

        update_dataset_progress(
            dataset_version_id,
            "running",
            25,
            "Checking image and label pairs.",
            "checking_image_label_pairs",
        )
        scan_report = scan_dataset_source(images_dir, labels_dir)

        update_dataset_progress(dataset_version_id, "running", 45, "Detecting duplicates.", "detecting_duplicates")
        evaluation = evaluate_import_candidates(
            dataset_version["project_id"],
            scan_report["matched_pairs"],
            visual_dup_threshold=payload["visual_dup_threshold"],
        )

        update_dataset_progress(dataset_version_id, "running", 65, "Validating YOLO labels.", "validating_labels")
        reports = build_import_reports(scan_report, evaluation)

        update_dataset_progress(dataset_version_id, "running", 82, "Saving accepted files.", "saving_accepted_files")
        copied_paths = copy_accepted_items_to_project_storage(project_images_dir, project_labels_dir, evaluation["accepted_items"])

        update_dataset_progress(dataset_version_id, "running", 95, "Creating dataset version metadata.", "creating_dataset_version")
        complete_dataset_version_import(
            dataset_version_id=dataset_version_id,
            accepted_items=evaluation["accepted_items"],
            validation_report=reports["validation_report"],
            cleaning_report=reports["cleaning_report"],
            stats_report=reports["stats_report"],
            import_summary_json=reports["import_summary_json"],
        )
    except Exception as exc:  # pragma: no cover
        for copied_path in copied_paths:
            if copied_path.exists():
                copied_path.unlink()
        fail_dataset_version_import(dataset_version_id, f"{exc}\n\n{traceback.format_exc()}")
    finally:
        IMPORT_TASKS.pop(dataset_version_id, None)


def resolve_import_source(import_payload: dict[str, Any]) -> tuple[Path, Path]:
    import_mode = (import_payload.get("import_mode") or "combined").lower()
    if import_mode == "combined":
        dataset_path = Path(import_payload.get("dataset_path") or "")
        return dataset_path / "images", dataset_path / "labels"
    raise ValueError("Unsupported import mode.")


def evaluate_import_candidates(project_id: int, matched_pairs: list[dict], visual_dup_threshold: int = DEFAULT_VISUAL_DUP_THRESHOLD) -> dict:
    existing_hashes = get_existing_project_hashes(project_id)
    seen_import_hashes: set[str] = set()
    provisional_items: list[dict] = []
    exact_duplicates_skipped: list[str] = []
    corrupt_images: list[str] = []
    invalid_labels: list[dict] = []
    empty_labels: list[str] = []
    very_small_boxes: list[dict] = []

    for pair in matched_pairs:
        image_path = pair["image_path"]
        label_path = pair["label_path"]

        try:
            image_metadata = read_image_metadata(image_path)
        except ValueError:
            corrupt_images.append(image_path.name)
            continue

        image_hash = compute_file_sha256(image_path)
        if image_hash in existing_hashes or image_hash in seen_import_hashes:
            exact_duplicates_skipped.append(image_path.name)
            continue

        label_validation = validate_yolo_label_file(label_path)
        if label_validation["is_empty"]:
            # Empty labels are intentional background images. Preserve them as
            # valid dataset items so YOLO can learn negative/background context.
            empty_labels.append(label_path.name)
        if label_validation["invalid_entries"]:
            invalid_labels.extend(label_validation["invalid_entries"])
            continue

        label_hash = compute_file_sha256(label_path)
        stored_image_filename = f"{image_hash}{image_path.suffix.lower()}"
        stored_label_filename = f"{image_hash}.txt"
        provisional_items.append(
            {
                "project_id": project_id,
                "image_path": image_path,
                "label_path": label_path,
                "stored_image_filename": stored_image_filename,
                "stored_label_filename": stored_label_filename,
                "image_hash": image_hash,
                "label_hash": label_hash,
                "width": image_metadata["width"],
                "height": image_metadata["height"],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "source_image_name": image_path.name,
                "source_label_name": label_path.name,
                "class_ids": sorted(label_validation["class_ids"]),
                "class_counts": label_validation["class_counts"],
                "object_count": label_validation["object_count"],
            }
        )
        very_small_boxes.extend(label_validation["very_small_boxes"])
        seen_import_hashes.add(image_hash)

    accepted_items, perceptual_duplicate_groups, perceptual_duplicates_skipped = _split_perceptual_duplicates(
        provisional_items,
        visual_dup_threshold=visual_dup_threshold,
    )
    duplicates_skipped = exact_duplicates_skipped + perceptual_duplicates_skipped

    return {
        "accepted_items": accepted_items,
        "duplicates_skipped": duplicates_skipped,
        "exact_duplicates_skipped": exact_duplicates_skipped,
        "perceptual_duplicate_groups": perceptual_duplicate_groups,
        "perceptual_duplicates_skipped": perceptual_duplicates_skipped,
        "corrupt_images": corrupt_images,
        "invalid_labels": invalid_labels,
        "empty_labels": empty_labels,
        "very_small_boxes": very_small_boxes,
        "visual_dup_threshold": visual_dup_threshold,
    }


def copy_accepted_items_to_project_storage(project_images_dir: Path, project_labels_dir: Path, accepted_items: list[dict]) -> list[Path]:
    copied_paths: list[Path] = []
    for item in accepted_items:
        image_target = project_images_dir / item["stored_image_filename"]
        label_target = project_labels_dir / item["stored_label_filename"]
        if not image_target.exists():
            shutil.copy2(item["image_path"], image_target)
            copied_paths.append(image_target)
        if not label_target.exists():
            shutil.copy2(item["label_path"], label_target)
            copied_paths.append(label_target)
    return copied_paths


def _split_perceptual_duplicates(
    provisional_items: list[dict],
    visual_dup_threshold: int = DEFAULT_VISUAL_DUP_THRESHOLD,
) -> tuple[list[dict], list[list[str]], list[str]]:
    if len(provisional_items) < 2:
        return provisional_items, [], []

    # We keep exact SHA256 dedup for storage correctness, then run perceptual
    # dedup inside the import batch so visually duplicated images from the same
    # dataset are still surfaced and skipped like the older cleanse flow did.
    if visual_dup_threshold == VISUAL_DUP_THRESHOLD_OFF:
        return provisional_items, [], []
    if visual_dup_threshold < 0:
        visual_dup_threshold = DEFAULT_VISUAL_DUP_THRESHOLD

    perceptual_duplicate_groups = detect_duplicates(
        [item["image_path"] for item in provisional_items],
        max_distance=visual_dup_threshold,
    )
    skipped_names: set[str] = set()
    for group in perceptual_duplicate_groups:
        for duplicate_name in group[1:]:
            skipped_names.add(duplicate_name)

    accepted_items = [item for item in provisional_items if item["image_path"].name not in skipped_names]
    perceptual_duplicates_skipped = sorted(skipped_names)
    return accepted_items, perceptual_duplicate_groups, perceptual_duplicates_skipped


def _normalize_visual_dup_threshold(value: Any) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return DEFAULT_VISUAL_DUP_THRESHOLD
    if normalized == VISUAL_DUP_THRESHOLD_OFF:
        return VISUAL_DUP_THRESHOLD_OFF
    return max(0, min(8, normalized))
