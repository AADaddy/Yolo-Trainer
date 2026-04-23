from __future__ import annotations

from collections import Counter
from pathlib import Path

from .dataset_version_service import (
    get_dataset_version,
    get_project,
    get_project_dataset_dirs,
    list_cumulative_dataset_items,
    list_dataset_items_for_version,
    list_dataset_versions,
)
from .dataset_warning_service import build_dataset_warnings


BBOX_AREA_THRESHOLDS = {
    "tiny": 0.001,
    "small": 0.01,
    "medium": 0.10,
}

BBOX_HEIGHT_THRESHOLDS = {
    "very_short": 0.05,
    "short": 0.10,
    "medium": 0.20,
}

BBOX_PIXEL_HEIGHT_THRESHOLDS = {
    "too_small": 15,
    "borderline": 30,
}

BBOX_ASPECT_RATIO_THRESHOLDS = {
    "very_narrow": 0.20,
    "very_wide": 1.20,
}


def get_dashboard_statistics(dataset_version_id: int) -> dict:
    dataset_version = get_dataset_version(dataset_version_id)
    project = get_project(dataset_version["project_id"])
    _, _, _, project_labels_dir = get_project_dataset_dirs(project["id"], project["name"])

    # The dashboard always uses the cumulative dataset up to the selected version.
    # This keeps version-to-version comparisons stable and matches training behavior.
    cumulative_items = list_cumulative_dataset_items(dataset_version_id)
    class_counts: Counter[int] = Counter()
    image_counts_per_class: Counter[int] = Counter()
    objects_per_image_counts = []
    object_bucket_counts = {"0_objects": 0, "1_2_objects": 0, "3_5_objects": 0, "gt_5_objects": 0}
    bbox_area_counts = {"tiny": 0, "small": 0, "medium": 0, "large": 0}
    bbox_height_counts = {"very_short": 0, "short": 0, "medium": 0, "tall": 0}
    bbox_visibility_counts = {"too_small": 0, "borderline": 0, "good": 0}
    bbox_aspect_counts = {"very_narrow": 0, "typical": 0, "very_wide": 0}
    resolution_counts: Counter[str] = Counter()
    total_objects = 0

    for item in cumulative_items:
        label_path = project_labels_dir / item["label_filename"]
        parsed = _parse_label_file(label_path, int(item["width"]), int(item["height"]))
        object_count = parsed["object_count"]
        objects_per_image_counts.append(object_count)
        total_objects += object_count

        for class_id, count in parsed["class_counts"].items():
            class_counts[class_id] += count
            image_counts_per_class[class_id] += 1

        for box in parsed["boxes"]:
            _increment_bbox_area_bucket(bbox_area_counts, box["area"])
            _increment_bbox_height_bucket(bbox_height_counts, box["height"])
            _increment_bbox_visibility_bucket(bbox_visibility_counts, box["pixel_height"])
            _increment_bbox_aspect_bucket(bbox_aspect_counts, box["aspect_ratio"])

        resolution_counts[f"{item['width']}x{item['height']}"] += 1
        _increment_object_bucket(object_bucket_counts, object_count)

    total_images = len(cumulative_items)
    total_labels = len(cumulative_items)
    avg_objects_per_image = (total_objects / total_images) if total_images else 0.0
    class_balance = _build_class_balance(class_counts, image_counts_per_class, total_objects)
    class_coverage = _build_class_coverage(image_counts_per_class, total_images)
    resolution_summary = _build_resolution_summary(resolution_counts, total_images)
    objects_per_image_distribution = _build_objects_per_image_distribution(object_bucket_counts, total_images)
    # Bounding-box analytics are generated from cumulative items here, not from
    # import-time stats, so selecting a version preserves the same cumulative
    # scope that training uses.
    bounding_box_distribution = _build_bounding_box_distribution(
        bbox_area_counts,
        bbox_height_counts,
        bbox_visibility_counts,
        bbox_aspect_counts,
    )
    dataset_growth = _build_dataset_growth(project["id"], project_labels_dir)
    current_import_cleanse_summary = _build_current_import_summary(dataset_version)
    accepted_rate = (
        current_import_cleanse_summary["accepted_count"] / current_import_cleanse_summary["imported_count"]
        if current_import_cleanse_summary["imported_count"] > 0
        else 0.0
    )

    payload = {
        "dataset_version_id": dataset_version["id"],
        "project_id": project["id"],
        "selected_version_name": dataset_version["version"],
        "total_images": total_images,
        "total_labels": total_labels,
        "total_objects": total_objects,
        "number_of_classes": len(class_counts),
        "avg_objects_per_image": avg_objects_per_image,
        "accepted_rate": accepted_rate,
        "objects_per_class": {str(key): value for key, value in sorted(class_counts.items())},
        "images_per_class": {str(key): value for key, value in sorted(image_counts_per_class.items())},
        "class_balance": class_balance,
        "class_coverage": class_coverage,
        "objects_per_image_distribution": objects_per_image_distribution,
        "bounding_box_distribution": bounding_box_distribution,
        "resolution_summary": resolution_summary,
        "dataset_growth": dataset_growth,
        "current_import_cleanse_summary": current_import_cleanse_summary,
        "version_import_cleanse_summary": [entry["import_cleanse_summary"] for entry in dataset_growth],
    }
    payload["warnings"] = build_dataset_warnings(payload)
    return payload


def _parse_label_file(label_path: Path, image_width: int = 0, image_height: int = 0) -> dict:
    class_counts: Counter[int] = Counter()
    boxes: list[dict] = []
    object_count = 0
    if not label_path.exists():
        return {"class_counts": class_counts, "boxes": boxes, "object_count": 0}

    for raw_line in label_path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        parts = raw_line.split()
        if len(parts) != 5:
            continue
        try:
            class_id = int(float(parts[0]))
            width = float(parts[3])
            height = float(parts[4])
        except ValueError:
            continue
        if width <= 0 or height <= 0:
            continue
        class_counts[class_id] += 1
        # Normalized area remains useful for comparing annotation scale across
        # mixed camera resolutions, while pixel height captures practical
        # visibility after the image has real dimensions.
        boxes.append(
            {
                "width": width,
                "height": height,
                "area": width * height,
                "pixel_width": width * image_width if image_width > 0 else 0.0,
                "pixel_height": height * image_height if image_height > 0 else 0.0,
                "aspect_ratio": width / height,
            }
        )
        object_count += 1
    return {"class_counts": class_counts, "boxes": boxes, "object_count": object_count}


def _increment_bbox_area_bucket(bucket_counts: dict[str, int], area: float) -> None:
    # COCO-style normalized area buckets give a more familiar scale audit while
    # still remaining resolution independent for dataset-level review.
    if area < BBOX_AREA_THRESHOLDS["tiny"]:
        bucket_counts["tiny"] += 1
    elif area < BBOX_AREA_THRESHOLDS["small"]:
        bucket_counts["small"] += 1
    elif area < BBOX_AREA_THRESHOLDS["medium"]:
        bucket_counts["medium"] += 1
    else:
        bucket_counts["large"] += 1


def _increment_bbox_height_bucket(bucket_counts: dict[str, int], height: float) -> None:
    # In people-oriented datasets, box height often better represents usable
    # visual detail than area because people can be tall and thin.
    if height < BBOX_HEIGHT_THRESHOLDS["very_short"]:
        bucket_counts["very_short"] += 1
    elif height < BBOX_HEIGHT_THRESHOLDS["short"]:
        bucket_counts["short"] += 1
    elif height < BBOX_HEIGHT_THRESHOLDS["medium"]:
        bucket_counts["medium"] += 1
    else:
        bucket_counts["tall"] += 1


def _increment_bbox_visibility_bucket(bucket_counts: dict[str, int], pixel_height: float) -> None:
    # YOLO ultimately learns from pixels after resizing, so very low pixel
    # height is a practical learnability risk even when normalized metrics look acceptable.
    if pixel_height < BBOX_PIXEL_HEIGHT_THRESHOLDS["too_small"]:
        bucket_counts["too_small"] += 1
    elif pixel_height < BBOX_PIXEL_HEIGHT_THRESHOLDS["borderline"]:
        bucket_counts["borderline"] += 1
    else:
        bucket_counts["good"] += 1


def _increment_bbox_aspect_bucket(bucket_counts: dict[str, int], aspect_ratio: float) -> None:
    if aspect_ratio < BBOX_ASPECT_RATIO_THRESHOLDS["very_narrow"]:
        bucket_counts["very_narrow"] += 1
    elif aspect_ratio > BBOX_ASPECT_RATIO_THRESHOLDS["very_wide"]:
        bucket_counts["very_wide"] += 1
    else:
        bucket_counts["typical"] += 1


def _increment_object_bucket(bucket_counts: dict[str, int], object_count: int) -> None:
    # These coarse buckets are easier to read than a dense histogram and work
    # well for spotting empty or overly crowded frames on the dashboard.
    if object_count == 0:
        bucket_counts["0_objects"] += 1
    elif object_count <= 2:
        bucket_counts["1_2_objects"] += 1
    elif object_count <= 5:
        bucket_counts["3_5_objects"] += 1
    else:
        bucket_counts["gt_5_objects"] += 1


def _build_class_balance(class_counts: Counter[int], image_counts_per_class: Counter[int], total_objects: int) -> list[dict]:
    rows = []
    for class_id in sorted(class_counts.keys() | image_counts_per_class.keys()):
        object_count = int(class_counts.get(class_id, 0))
        rows.append(
            {
                "class_id": class_id,
                "class_name": f"Class {class_id}",
                "object_count": object_count,
                "image_count": int(image_counts_per_class.get(class_id, 0)),
                "percentage": (object_count / total_objects) if total_objects else 0.0,
            }
        )
    return rows


def _build_class_coverage(image_counts_per_class: Counter[int], total_images: int) -> list[dict]:
    rows = []
    for class_id in sorted(image_counts_per_class.keys()):
        image_count = int(image_counts_per_class[class_id])
        rows.append(
            {
                "class_id": class_id,
                "class_name": f"Class {class_id}",
                "image_count": image_count,
                "image_ratio": (image_count / total_images) if total_images else 0.0,
            }
        )
    return rows


def _build_objects_per_image_distribution(bucket_counts: dict[str, int], total_images: int) -> list[dict]:
    labels = {
        "0_objects": "0 objects",
        "1_2_objects": "1-2 objects",
        "3_5_objects": "3-5 objects",
        "gt_5_objects": ">5 objects",
    }
    return [
        {
            "bucket": key,
            "label": labels[key],
            "count": int(bucket_counts[key]),
            "percentage": (bucket_counts[key] / total_images) if total_images else 0.0,
        }
        for key in ["0_objects", "1_2_objects", "3_5_objects", "gt_5_objects"]
    ]


def _build_bounding_box_distribution(
    area_counts: dict[str, int],
    height_counts: dict[str, int],
    visibility_counts: dict[str, int],
    aspect_counts: dict[str, int],
) -> dict:
    total_boxes = sum(area_counts.values())
    area_distribution = _build_bucket_rows(
        area_counts,
        total_boxes,
        [
            ("tiny", "Tiny", "area < 0.001"),
            ("small", "Small", "0.001-0.01"),
            ("medium", "Medium", "0.01-0.10"),
            ("large", "Large", "area >= 0.10"),
        ],
    )
    height_distribution = _build_bucket_rows(
        height_counts,
        total_boxes,
        [
            ("very_short", "Very Short", "h < 0.05"),
            ("short", "Short", "0.05-0.10"),
            ("medium", "Medium", "0.10-0.20"),
            ("tall", "Tall", "h >= 0.20"),
        ],
    )
    visibility_distribution = _build_bucket_rows(
        visibility_counts,
        total_boxes,
        [
            ("too_small", "Too Small", "<15 px"),
            ("borderline", "Borderline", "15-29 px"),
            ("good", "Good Visibility", ">=30 px"),
        ],
    )
    aspect_distribution = _build_bucket_rows(
        aspect_counts,
        total_boxes,
        [
            ("very_narrow", "Very Narrow", "w/h < 0.20"),
            ("typical", "Typical", "0.20-1.20"),
            ("very_wide", "Very Wide", "w/h > 1.20"),
        ],
    )
    tiny_or_small = area_counts["tiny"] + area_counts["small"]
    low_height = height_counts["very_short"] + height_counts["short"]
    low_visibility = visibility_counts["too_small"] + visibility_counts["borderline"]
    return {
        "total_boxes": total_boxes,
        "area_distribution": area_distribution,
        "height_distribution": height_distribution,
        "pixel_visibility_distribution": visibility_distribution,
        "aspect_ratio_distribution": aspect_distribution,
        "area_thresholds": BBOX_AREA_THRESHOLDS,
        "height_thresholds": BBOX_HEIGHT_THRESHOLDS,
        "pixel_height_thresholds": BBOX_PIXEL_HEIGHT_THRESHOLDS,
        "aspect_ratio_thresholds": BBOX_ASPECT_RATIO_THRESHOLDS,
        "tiny_percentage": (area_counts["tiny"] / total_boxes) if total_boxes else 0.0,
        "small_percentage": (area_counts["small"] / total_boxes) if total_boxes else 0.0,
        "medium_percentage": (area_counts["medium"] / total_boxes) if total_boxes else 0.0,
        "large_percentage": (area_counts["large"] / total_boxes) if total_boxes else 0.0,
        "tiny_or_small_percentage": (tiny_or_small / total_boxes) if total_boxes else 0.0,
        "very_short_percentage": (height_counts["very_short"] / total_boxes) if total_boxes else 0.0,
        "short_percentage": (height_counts["short"] / total_boxes) if total_boxes else 0.0,
        "low_height_percentage": (low_height / total_boxes) if total_boxes else 0.0,
        "too_small_pixel_percentage": (visibility_counts["too_small"] / total_boxes) if total_boxes else 0.0,
        "borderline_pixel_percentage": (visibility_counts["borderline"] / total_boxes) if total_boxes else 0.0,
        "low_visibility_percentage": (low_visibility / total_boxes) if total_boxes else 0.0,
        "good_visibility_percentage": (visibility_counts["good"] / total_boxes) if total_boxes else 0.0,
        "very_narrow_percentage": (aspect_counts["very_narrow"] / total_boxes) if total_boxes else 0.0,
        "very_wide_percentage": (aspect_counts["very_wide"] / total_boxes) if total_boxes else 0.0,
    }


def _build_bucket_rows(counts: dict[str, int], total: int, definitions: list[tuple[str, str, str]]) -> list[dict]:
    return [
        {
            "bucket": key,
            "label": label,
            "range": bucket_range,
            "count": int(counts[key]),
            "percentage": (counts[key] / total) if total else 0.0,
        }
        for key, label, bucket_range in definitions
    ]


def _build_resolution_summary(resolution_counts: Counter[str], total_images: int) -> dict:
    # Resolution is intentionally summarized instead of charted because the
    # signal we care about is consistency, not a heavy visual distribution.
    if not resolution_counts:
        return {
            "most_common_resolution": "N/A",
            "dominant_ratio": 0.0,
            "unique_resolution_count": 0,
            "top_resolutions": [],
        }
    resolution, count = resolution_counts.most_common(1)[0]
    return {
        "most_common_resolution": resolution,
        "dominant_ratio": (count / total_images) if total_images else 0.0,
        "unique_resolution_count": len(resolution_counts),
        "top_resolutions": [
            {
                "resolution": name,
                "count": item_count,
                "ratio": (item_count / total_images) if total_images else 0.0,
            }
            for name, item_count in resolution_counts.most_common(3)
        ],
    }


def _build_dataset_growth(project_id: int, project_labels_dir: Path) -> list[dict]:
    growth_rows = []
    for version in sorted(list_dataset_versions(project_id), key=lambda row: (row["created_at"], row["id"])):
        version_items = list_dataset_items_for_version(version["id"])
        objects_added = 0
        for item in version_items:
            objects_added += _parse_label_file(project_labels_dir / item["label_filename"])["object_count"]
        growth_rows.append(
            {
                "version_name": version["version"],
                "images_added": int(version.get("added_image_count", 0)),
                "cumulative_total_images": int(version.get("cumulative_image_count", 0)),
                "objects_added": objects_added,
                "created_at": version["created_at"],
                "import_cleanse_summary": {
                    "version_name": version["version"],
                    "imported_count": int(version.get("import_summary_json", {}).get("imported_files_count", 0)),
                    "accepted_count": int(version.get("import_summary_json", {}).get("accepted_new_images_count", 0)),
                    "duplicate_count": int(version.get("import_summary_json", {}).get("duplicates_skipped", 0)),
                    "invalid_count": int(version.get("import_summary_json", {}).get("invalid_labels_skipped", 0)),
                    "corrupt_count": int(version.get("import_summary_json", {}).get("corrupt_images_skipped", 0)),
                },
            }
        )
    return growth_rows


def _build_current_import_summary(dataset_version: dict) -> dict:
    summary = dataset_version.get("import_summary_json", {})
    return {
        "imported_count": int(summary.get("imported_files_count", 0)),
        "accepted_count": int(summary.get("accepted_new_images_count", 0)),
        "duplicate_count": int(summary.get("duplicates_skipped", 0)),
        "invalid_count": int(summary.get("invalid_labels_skipped", 0)),
        "corrupt_count": int(summary.get("corrupt_images_skipped", 0)),
    }
