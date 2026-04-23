from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.config import API_PREFIX
from .dataset_statistics_service import BBOX_AREA_THRESHOLDS
from .dataset_version_service import (
    get_dataset_version,
    get_project,
    get_project_dataset_dirs,
    list_cumulative_dataset_items,
)


PAGE_SIZE_MAX = 100


def get_inspection_filters(dataset_version_id: int) -> dict[str, Any]:
    context = _get_inspection_context(dataset_version_id)
    items = context["items"]
    labels_dir = context["labels_dir"]
    resolutions = sorted({f"{item['width']}x{item['height']}" for item in items})
    return {
        "dataset_version": context["dataset_version"],
        "total_images": len(items),
        "resolutions": resolutions,
        "area_buckets": _area_bucket_options(),
        "label_states": [
            {"value": "has_labels", "label": "Has labels"},
            {"value": "empty_label", "label": "Empty label"},
            {"value": "single_object", "label": "Single object"},
            {"value": "multiple_objects", "label": "Multiple objects"},
        ],
        "empty_label_count": sum(1 for item in items if _parse_label_file(labels_dir / item["label_filename"])["is_empty"]),
    }


def list_inspection_items(
    dataset_version_id: int,
    page: int = 1,
    page_size: int = 30,
    resolution: str | None = None,
    area_bucket: str | None = None,
    label_state: str | None = None,
    filename: str | None = None,
) -> dict[str, Any]:
    context = _get_inspection_context(dataset_version_id)
    labels_dir = context["labels_dir"]
    images_dir = context["images_dir"]
    page = max(1, int(page or 1))
    page_size = max(1, min(PAGE_SIZE_MAX, int(page_size or 30)))

    rows = []
    for item in context["items"]:
        parsed = _parse_label_file(labels_dir / item["label_filename"])
        metadata = _item_metadata(item, parsed, images_dir, dataset_version_id)
        if not _matches_filters(metadata, resolution, area_bucket, label_state, filename):
            continue
        rows.append(metadata)

    total = len(rows)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "dataset_version": context["dataset_version"],
        "project": context["project"],
        "summary": {
            "total_images": len(context["items"]),
            "filtered_images": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        },
        "items": rows[start:end],
        "filters": {
            "resolution": resolution or "",
            "area_bucket": area_bucket or "",
            "label_state": label_state or "",
            "filename": filename or "",
        },
    }


def get_inspection_preview(dataset_version_id: int, dataset_item_id: int) -> dict[str, Any]:
    context = _get_inspection_context(dataset_version_id)
    labels_dir = context["labels_dir"]
    images_dir = context["images_dir"]
    item = next((row for row in context["items"] if int(row["id"]) == int(dataset_item_id)), None)
    if not item:
        raise ValueError("Dataset item was not found in the selected cumulative version scope.")
    parsed = _parse_label_file(labels_dir / item["label_filename"])
    metadata = _item_metadata(item, parsed, images_dir, dataset_version_id)
    # Empty-label previews intentionally return an empty boxes list; the frontend
    # still shows the image and explains that it is a background sample.
    return {
        **metadata,
        "boxes": parsed["boxes"],
    }


def get_dataset_item_image_path(dataset_version_id: int, dataset_item_id: int) -> Path:
    context = _get_inspection_context(dataset_version_id)
    images_dir = context["images_dir"]
    item = next((row for row in context["items"] if int(row["id"]) == int(dataset_item_id)), None)
    if not item:
        raise ValueError("Dataset item was not found in the selected cumulative version scope.")
    image_path = images_dir / item["image_filename"]
    if not image_path.exists():
        raise ValueError("Image file was not found.")
    return image_path


def _get_inspection_context(dataset_version_id: int) -> dict[str, Any]:
    dataset_version = get_dataset_version(dataset_version_id)
    project = get_project(dataset_version["project_id"])
    _, _, images_dir, labels_dir = get_project_dataset_dirs(project["id"], project["name"])
    # Inspection follows training/dashboard semantics: selected version means all
    # items accumulated up to that version, not only the selected delta import.
    items = list_cumulative_dataset_items(dataset_version_id)
    return {
        "dataset_version": dataset_version,
        "project": project,
        "images_dir": images_dir,
        "labels_dir": labels_dir,
        "items": items,
    }


def _parse_label_file(label_path: Path) -> dict[str, Any]:
    boxes: list[dict[str, Any]] = []
    class_counts: dict[int, int] = {}
    if not label_path.exists():
        return {"boxes": boxes, "object_count": 0, "is_empty": True, "class_counts": class_counts, "area_buckets": []}
    for line_number, raw_line in enumerate(label_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue
        parts = raw_line.split()
        if len(parts) != 5:
            continue
        try:
            class_id = int(float(parts[0]))
            x_center, y_center, width, height = [float(value) for value in parts[1:]]
        except ValueError:
            continue
        area = width * height
        bucket = _bbox_area_bucket(area)
        class_counts[class_id] = class_counts.get(class_id, 0) + 1
        boxes.append(
            {
                "line": line_number,
                "class_id": class_id,
                "class_label": f"Class {class_id}",
                "x_center": x_center,
                "y_center": y_center,
                "width": width,
                "height": height,
                "area": area,
                "area_bucket": bucket,
            }
        )
    return {
        "boxes": boxes,
        "object_count": len(boxes),
        "is_empty": len(boxes) == 0,
        "class_counts": class_counts,
        "area_buckets": sorted({box["area_bucket"] for box in boxes}),
    }


def _item_metadata(item: dict[str, Any], parsed: dict[str, Any], images_dir: Path, scope_dataset_version_id: int) -> dict[str, Any]:
    label_state = _label_state(parsed["object_count"])
    return {
        "id": item["id"],
        "image_filename": item["image_filename"],
        "label_filename": item["label_filename"],
        "source_image_name": item.get("source_image_name") or item["image_filename"],
        "source_label_name": item.get("source_label_name") or item["label_filename"],
        "width": item["width"],
        "height": item["height"],
        "resolution": f"{item['width']}x{item['height']}",
        "object_count": parsed["object_count"],
        "is_empty_label": parsed["is_empty"],
        "label_state": label_state,
        "area_buckets": parsed["area_buckets"],
        "class_counts": {str(key): value for key, value in sorted(parsed["class_counts"].items())},
        "image_url": f"{API_PREFIX}/datasets/inspection/{scope_dataset_version_id}/items/{item['id']}/image",
        "thumbnail_url": f"{API_PREFIX}/datasets/inspection/{scope_dataset_version_id}/items/{item['id']}/image",
        "image_exists": (images_dir / item["image_filename"]).exists(),
    }


def _matches_filters(
    metadata: dict[str, Any],
    resolution: str | None,
    area_bucket: str | None,
    label_state: str | None,
    filename: str | None,
) -> bool:
    if filename:
        needle = filename.strip().casefold()
        stored_name = str(metadata["image_filename"]).casefold()
        source_name = str(metadata["source_image_name"]).casefold()
        # Filename search is intentionally partial and case-insensitive so a
        # reviewer can jump to a camera prefix or frame id without exact casing.
        if needle and needle not in stored_name and needle not in source_name:
            return False
    if resolution and metadata["resolution"] != resolution:
        return False
    if label_state:
        if label_state == "has_labels":
            if metadata["object_count"] <= 0:
                return False
        elif metadata["label_state"] != label_state:
            return False
    # Image-level box filters match if any box in the image belongs to the
    # selected bucket, which mirrors how users look for examples with at least
    # one problematic or interesting object.
    if area_bucket and area_bucket not in metadata["area_buckets"]:
        return False
    return True


def _label_state(object_count: int) -> str:
    if object_count == 0:
        return "empty_label"
    if object_count == 1:
        return "single_object"
    return "multiple_objects"


def _bbox_area_bucket(area: float) -> str:
    if area < BBOX_AREA_THRESHOLDS["tiny"]:
        return "tiny"
    if area < BBOX_AREA_THRESHOLDS["small"]:
        return "small"
    if area < BBOX_AREA_THRESHOLDS["medium"]:
        return "medium"
    return "large"


def _area_bucket_options() -> list[dict[str, str]]:
    return [
        {"value": "tiny", "label": "Tiny", "range": "area < 0.001"},
        {"value": "small", "label": "Small", "range": "0.001-0.01"},
        {"value": "medium", "label": "Medium", "range": "0.01-0.10"},
        {"value": "large", "label": "Large", "range": "area >= 0.10"},
    ]
