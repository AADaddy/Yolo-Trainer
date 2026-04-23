from __future__ import annotations


WARNING_THRESHOLDS = {
    "class_imbalance": 0.80,
    "low_class_coverage": 0.30,
    "tiny_or_small_boxes": 0.70,
    "too_small_pixel_height": 0.20,
    "low_pixel_visibility": 0.45,
    "high_duplicate_rate": 0.15,
    "inconsistent_resolution": 0.80,
}


def build_dataset_warnings(stats: dict) -> list[str]:
    warnings: list[str] = []

    class_balance = stats.get("class_balance", [])
    for row in class_balance:
        percentage = float(row.get("percentage", 0.0))
        if percentage > WARNING_THRESHOLDS["class_imbalance"]:
            warnings.append(f"Class imbalance detected: {row.get('class_name', 'Unknown')} exceeds 80% of objects.")

    class_coverage = stats.get("class_coverage", [])
    for row in class_coverage:
        image_ratio = float(row.get("image_ratio", 0.0))
        if image_ratio < WARNING_THRESHOLDS["low_class_coverage"]:
            warnings.append(f"Low class coverage: {row.get('class_name', 'Unknown')} appears in under 30% of images.")

    bbox_distribution = stats.get("bounding_box_distribution", {})
    tiny_or_small_ratio = float(bbox_distribution.get("tiny_or_small_percentage", 0.0))
    if tiny_or_small_ratio > WARNING_THRESHOLDS["tiny_or_small_boxes"]:
        warnings.append("Too many tiny/small boxes: more than 70% of boxes are below 1% normalized area.")

    too_small_pixel_ratio = float(bbox_distribution.get("too_small_pixel_percentage", 0.0))
    low_visibility_ratio = float(bbox_distribution.get("low_visibility_percentage", 0.0))
    if too_small_pixel_ratio > WARNING_THRESHOLDS["too_small_pixel_height"]:
        warnings.append("Low object visibility: more than 20% of boxes are under 15 px tall.")
    elif low_visibility_ratio > WARNING_THRESHOLDS["low_pixel_visibility"]:
        warnings.append("Borderline object visibility: many boxes are under 30 px tall.")

    cleanse_summary = stats.get("current_import_cleanse_summary", {})
    imported_count = int(cleanse_summary.get("imported_count", 0))
    duplicate_count = int(cleanse_summary.get("duplicate_count", 0))
    duplicate_rate = (duplicate_count / imported_count) if imported_count > 0 else 0.0
    if duplicate_rate > WARNING_THRESHOLDS["high_duplicate_rate"]:
        warnings.append("High duplicate rate detected: duplicates exceeded 15% of the latest import.")

    resolution_summary = stats.get("resolution_summary", {})
    dominant_ratio = float(resolution_summary.get("dominant_ratio", 0.0))
    if dominant_ratio < WARNING_THRESHOLDS["inconsistent_resolution"] and int(stats.get("total_images", 0)) > 0:
        warnings.append("Inconsistent resolution mix: dominant resolution is below 80% of images.")

    return warnings
