from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml

from backend.config import PROCESSED_STORAGE_DIR
from .dataset_splitter import choose_split, validate_split_ratio
from .dataset_version_service import (
    get_dataset_version,
    get_project,
    get_project_dataset_dirs,
    list_cumulative_dataset_items,
)


def get_processed_dataset_dir(project_id: int) -> Path:
    return PROCESSED_STORAGE_DIR / str(project_id)


def rebuild_processed_dataset(project_id: int, dataset_version_id: int, split_ratio: str) -> dict:
    split_ratio = validate_split_ratio(split_ratio)
    dataset_version = get_dataset_version(dataset_version_id)
    if dataset_version["project_id"] != project_id:
        raise ValueError("Dataset version does not belong to the selected project.")

    project = get_project(project_id)
    processed_dir = get_processed_dataset_dir(project_id)

    # Only one processed dataset should exist per project. We clear the whole
    # folder on every start to guarantee a clean rebuild from the current config.
    if processed_dir.exists():
        shutil.rmtree(processed_dir, ignore_errors=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    return _build_processed_dataset(project, dataset_version, processed_dir, split_ratio)


def _build_processed_dataset(project: dict, dataset_version: dict, processed_dir: Path, split_ratio: str) -> dict:
    _, _, project_images_dir, project_labels_dir = get_project_dataset_dirs(project["id"], project["name"])
    image_records = list_cumulative_dataset_items(dataset_version["id"])
    if not image_records:
        raise ValueError("The selected dataset version does not contain any accepted images to train on.")

    split_dirs = {
        "train_images": processed_dir / "train" / "images",
        "train_labels": processed_dir / "train" / "labels",
        "val_images": processed_dir / "val" / "images",
        "val_labels": processed_dir / "val" / "labels",
    }
    for directory in split_dirs.values():
        directory.mkdir(parents=True, exist_ok=True)

    split_counts = {"train": 0, "val": 0}
    for record in image_records:
        split_name = choose_split(record["image_hash"], split_ratio)
        split_counts[split_name] += 1
        image_target_dir = split_dirs[f"{split_name}_images"]
        label_target_dir = split_dirs[f"{split_name}_labels"]
        shutil.copy2(project_images_dir / record["image_filename"], image_target_dir / record["image_filename"])
        shutil.copy2(project_labels_dir / record["label_filename"], label_target_dir / record["label_filename"])

    # Keep training viable for tiny datasets: if one side ended up empty because
    # of hashing, move the first item to the missing split without reshuffling the
    # rest of the dataset.
    _ensure_non_empty_split(image_records, split_counts, split_dirs)

    names = _build_class_name_map(project_labels_dir, image_records)
    data_yaml = {
        "path": str(processed_dir),
        "train": "train/images",
        "val": "val/images",
        "names": names,
        "nc": len(names),
    }
    data_yaml_path = processed_dir / "data.yaml"
    data_yaml_path.write_text(yaml.safe_dump(data_yaml, sort_keys=False), encoding="utf-8")

    metadata = {
        "project_id": project["id"],
        "dataset_version_id": dataset_version["id"],
        "dataset_version": dataset_version["version"],
        "split_ratio": split_ratio,
        "total_images": len(image_records),
        "split_counts": split_counts,
    }
    metadata_path = processed_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    return {
        "processed_dir": str(processed_dir),
        "data_yaml": str(data_yaml_path),
        "metadata": metadata,
        "metadata_path": str(metadata_path),
    }


def _ensure_non_empty_split(image_records: list[dict], split_counts: dict[str, int], split_dirs: dict[str, Path]) -> None:
    if not image_records:
        return
    if split_counts["train"] > 0 and split_counts["val"] > 0:
        return

    source_split = "train" if split_counts["train"] > 0 else "val"
    target_split = "val" if source_split == "train" else "train"
    first_record = image_records[0]
    source_image = split_dirs[f"{source_split}_images"] / first_record["image_filename"]
    source_label = split_dirs[f"{source_split}_labels"] / first_record["label_filename"]
    target_image = split_dirs[f"{target_split}_images"] / first_record["image_filename"]
    target_label = split_dirs[f"{target_split}_labels"] / first_record["label_filename"]

    if source_image.exists():
        shutil.move(str(source_image), str(target_image))
    if source_label.exists():
        shutil.move(str(source_label), str(target_label))
    split_counts[source_split] = max(0, split_counts[source_split] - 1)
    split_counts[target_split] += 1


def _build_class_name_map(project_labels_dir: Path, image_records: list[dict]) -> dict[int, str]:
    class_ids: set[int] = set()
    for record in image_records:
        label_path = project_labels_dir / record["label_filename"]
        for line in label_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            parts = line.split()
            if not parts:
                continue
            try:
                class_ids.add(int(float(parts[0])))
            except ValueError:
                continue

    if not class_ids:
        return {0: "class_0"}
    return {class_id: f"class_{class_id}" for class_id in sorted(class_ids)}
