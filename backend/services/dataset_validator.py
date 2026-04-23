from __future__ import annotations

from collections import Counter
import hashlib
from pathlib import Path

from PIL import Image, UnidentifiedImageError


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def validate_import_structure(images_dir: Path, labels_dir: Path) -> None:
    if not images_dir.exists() or not images_dir.is_dir():
        raise ValueError("Images folder does not exist.")
    if not labels_dir.exists() or not labels_dir.is_dir():
        raise ValueError("Labels folder does not exist.")


def scan_dataset_source(images_dir: Path, labels_dir: Path) -> dict:
    image_files = sorted(path for path in images_dir.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)
    label_files = sorted(path for path in labels_dir.iterdir() if path.is_file() and path.suffix.lower() == ".txt")
    label_lookup = {path.stem: path for path in label_files}
    image_lookup = {path.stem: path for path in image_files}

    matched_pairs = []
    missing_labels: list[str] = []
    for image_path in image_files:
        label_path = label_lookup.get(image_path.stem)
        if label_path is None:
            missing_labels.append(image_path.name)
            continue
        matched_pairs.append({"image_path": image_path, "label_path": label_path})

    orphan_labels = [label_path.name for stem, label_path in label_lookup.items() if stem not in image_lookup]

    return {
        "image_files": image_files,
        "label_files": label_files,
        "matched_pairs": matched_pairs,
        "missing_labels": missing_labels,
        "orphan_labels": orphan_labels,
        "images": len(image_files),
        "labels": len(label_files),
        "matched_pairs_count": len(matched_pairs),
    }


def read_image_metadata(image_path: Path) -> dict:
    try:
        with Image.open(image_path) as image:
            image.verify()
        with Image.open(image_path) as image:
            width, height = image.size
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError(f"Corrupt image: {image_path.name}") from exc
    return {"width": width, "height": height}


def validate_yolo_label_file(label_path: Path) -> dict:
    lines = label_path.read_text(encoding="utf-8").splitlines()
    non_empty_lines = [line.strip() for line in lines if line.strip()]
    if not non_empty_lines:
        return {
            "is_empty": True,
            "invalid_entries": [],
            "class_ids": set(),
            "class_counts": {},
            "object_count": 0,
            "very_small_boxes": [],
        }

    invalid_entries: list[dict] = []
    class_ids: set[int] = set()
    class_counts: Counter[int] = Counter()
    very_small_boxes: list[dict] = []

    for line_number, line in enumerate(non_empty_lines, start=1):
        parts = line.split()
        if len(parts) != 5:
            invalid_entries.append({"file": label_path.name, "line": line_number, "value": line, "reason": "wrong_format"})
            continue
        try:
            class_id = int(float(parts[0]))
            center_x, center_y, width, height = [float(value) for value in parts[1:]]
        except ValueError:
            invalid_entries.append({"file": label_path.name, "line": line_number, "value": line, "reason": "not_numeric"})
            continue
        if class_id < 0 or not all(0.0 <= value <= 1.0 for value in [center_x, center_y, width, height]):
            invalid_entries.append({"file": label_path.name, "line": line_number, "value": line, "reason": "out_of_range"})
            continue
        class_ids.add(class_id)
        class_counts[class_id] += 1
        if width * height < 0.0005:
            very_small_boxes.append({"file": label_path.name, "line": line_number, "area": width * height})

    return {
        "is_empty": False,
        "invalid_entries": invalid_entries,
        "class_ids": class_ids,
        "class_counts": dict(class_counts),
        "object_count": len(non_empty_lines) - len(invalid_entries),
        "very_small_boxes": very_small_boxes,
    }


def compute_file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
