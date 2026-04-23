from __future__ import annotations

from pathlib import Path

from .duplicate_detector import detect_duplicates


def detect_similar_frames(image_paths: list[Path], threshold: int = 4) -> list[list[str]]:
    return detect_duplicates(image_paths, max_distance=threshold)
