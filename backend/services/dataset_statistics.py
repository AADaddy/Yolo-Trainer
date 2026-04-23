from __future__ import annotations

import base64
import io
from collections import Counter
from pathlib import Path

import matplotlib
import numpy as np
from PIL import Image, UnidentifiedImageError

from .dataset_validator import IMAGE_EXTENSIONS


matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _chart_to_base64() -> str:
    buffer = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buffer, format="png", dpi=120)
    plt.close()
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def compute_dataset_statistics(dataset_path: str) -> dict:
    dataset_dir = Path(dataset_path)
    images_dir = dataset_dir / "images"
    labels_dir = dataset_dir / "labels"
    return compute_dataset_statistics_subset(images_dir, labels_dir)


def compute_dataset_statistics_subset(
    images_dir: Path,
    labels_dir: Path,
    image_records: list[dict] | None = None,
) -> dict:
    if image_records is None:
        image_files = sorted(path for path in images_dir.iterdir() if path.suffix.lower() in IMAGE_EXTENSIONS) if images_dir.exists() else []
        label_files = sorted(path for path in labels_dir.iterdir() if path.suffix.lower() == ".txt") if labels_dir.exists() else []
    else:
        image_files = [images_dir / record["image_relative_path"] for record in image_records]
        label_files = [labels_dir / record["label_relative_path"] for record in image_records]

    objects_per_class: Counter[int] = Counter()
    objects_per_image: dict[str, int] = {}
    bbox_areas: list[float] = []
    resolution_counts: Counter[str] = Counter()

    for image_path in image_files:
        try:
            with Image.open(image_path) as image:
                resolution_counts[f"{image.width}x{image.height}"] += 1
        except (UnidentifiedImageError, OSError):
            resolution_counts["corrupt_or_unreadable"] += 1

    total_objects = 0
    for label_path in label_files:
        image_objects = 0
        for line in label_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) != 5:
                continue
            try:
                class_id = int(float(parts[0]))
                width = float(parts[3])
                height = float(parts[4])
            except ValueError:
                continue
            objects_per_class[class_id] += 1
            bbox_areas.append(width * height)
            image_objects += 1
        objects_per_image[label_path.stem] = image_objects
        total_objects += image_objects

    class_labels = [str(class_id) for class_id in sorted(objects_per_class.keys())]
    class_counts = [objects_per_class[int(class_id)] for class_id in class_labels]

    plt.figure(figsize=(6, 3))
    plt.bar(class_labels or ["0"], class_counts or [0], color="#2563eb")
    plt.title("Objects per Class")
    plt.xlabel("Class")
    plt.ylabel("Count")
    class_distribution_chart = _chart_to_base64()

    histogram_values = bbox_areas if bbox_areas else [0.0]
    counts, bins = np.histogram(histogram_values, bins=min(10, max(1, len(histogram_values))))

    plt.figure(figsize=(6, 3))
    plt.hist(histogram_values, bins=min(10, max(1, len(histogram_values))), color="#059669")
    plt.title("Bounding Box Area Distribution")
    plt.xlabel("Normalized area")
    plt.ylabel("Frequency")
    bbox_chart = _chart_to_base64()

    return {
        "total_images": len(image_files),
        "total_labels": len(label_files),
        "total_objects": total_objects,
        "number_of_classes": len(objects_per_class),
        "objects_per_class": {str(key): value for key, value in sorted(objects_per_class.items())},
        "objects_per_image": objects_per_image,
        "bounding_box_size_distribution": {
            "bins": [float(value) for value in bins.tolist()],
            "counts": [float(value) for value in counts.tolist()],
        },
        "image_resolution_distribution": dict(sorted(resolution_counts.items())),
        "chart_images": {
            "class_distribution": class_distribution_chart,
            "bounding_box_sizes": bbox_chart,
        },
    }
