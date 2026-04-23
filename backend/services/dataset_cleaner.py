from __future__ import annotations

from collections import Counter


def build_import_reports(scan_report: dict, evaluation: dict) -> dict:
    accepted_items = evaluation["accepted_items"]
    objects_per_class: Counter[int] = Counter()
    total_objects = 0
    for item in accepted_items:
        objects_per_class.update(item["class_counts"])
        total_objects += item["object_count"]

    validation_report = {
        "images": scan_report["images"],
        "labels": scan_report["labels"],
        "matched_pairs": scan_report["matched_pairs_count"],
        "missing_labels": scan_report["missing_labels"],
        "orphan_labels": scan_report["orphan_labels"],
        "invalid_labels": evaluation["invalid_labels"],
        "corrupt_images": evaluation["corrupt_images"],
    }

    cleaning_report = {
        "duplicates": evaluation["duplicates_skipped"],
        "exact_duplicates_skipped": evaluation.get("exact_duplicates_skipped", []),
        "perceptual_duplicate_groups": evaluation.get("perceptual_duplicate_groups", []),
        "perceptual_duplicates_skipped": evaluation.get("perceptual_duplicates_skipped", []),
        "corrupt_images": evaluation["corrupt_images"],
        "missing_labels": scan_report["missing_labels"],
        "empty_labels": evaluation["empty_labels"],
        "invalid_bounding_boxes": evaluation["invalid_labels"],
        "very_small_bounding_boxes": evaluation["very_small_boxes"],
        "similar_frame_clusters": [],
    }

    stats_report = {
        "total_images": len(accepted_items),
        "total_labels": len(accepted_items),
        "total_objects": total_objects,
        "number_of_classes": len(objects_per_class),
        "objects_per_class": {str(key): value for key, value in sorted(objects_per_class.items())},
        "objects_per_image": {
            item["stored_image_filename"]: item["object_count"] for item in accepted_items
        },
        "bounding_box_size_distribution": {"bins": [], "counts": []},
        "image_resolution_distribution": _resolution_distribution(accepted_items),
        "chart_images": {},
    }

    import_summary = {
        "imported_files_count": scan_report["images"],
        "accepted_new_images_count": len(accepted_items),
        "duplicates_skipped": len(evaluation["duplicates_skipped"]),
        "exact_duplicates_skipped": len(evaluation.get("exact_duplicates_skipped", [])),
        "perceptual_duplicates_skipped": len(evaluation.get("perceptual_duplicates_skipped", [])),
        "visual_dup_threshold": evaluation.get("visual_dup_threshold", 0),
        "corrupt_images_skipped": len(evaluation["corrupt_images"]),
        "invalid_labels_skipped": len(evaluation["invalid_labels"]),
        "empty_labels_skipped": 0,
        "empty_labels_accepted": len(evaluation["empty_labels"]),
        "missing_labels_skipped": len(scan_report["missing_labels"]),
        "orphan_labels_skipped": len(scan_report["orphan_labels"]),
    }

    return {
        "validation_report": validation_report,
        "cleaning_report": cleaning_report,
        "stats_report": stats_report,
        "import_summary_json": import_summary,
    }


def _resolution_distribution(accepted_items: list[dict]) -> dict[str, int]:
    distribution: Counter[str] = Counter()
    for item in accepted_items:
        distribution[f"{item['width']}x{item['height']}"] += 1
    return dict(sorted(distribution.items()))
