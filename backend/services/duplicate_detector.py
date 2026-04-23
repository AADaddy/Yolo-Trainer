from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import imagehash
from PIL import Image, UnidentifiedImageError


def detect_duplicates(image_paths: list[Path], max_distance: int = 0) -> list[list[str]]:
    hashes: list[tuple[Path, imagehash.ImageHash]] = []
    for image_path in image_paths:
        try:
            with Image.open(image_path) as image:
                hashes.append((image_path, imagehash.phash(image)))
        except (UnidentifiedImageError, OSError):
            continue

    exact_groups: defaultdict[str, list[str]] = defaultdict(list)
    if max_distance == 0:
        for image_path, image_hash in hashes:
            exact_groups[str(image_hash)].append(image_path.name)
        return [group for group in exact_groups.values() if len(group) > 1]

    groups: list[list[str]] = []
    visited: set[str] = set()
    for index, (current_path, current_hash) in enumerate(hashes):
        if str(current_path) in visited:
            continue
        group = [current_path.name]
        visited.add(str(current_path))
        for other_path, other_hash in hashes[index + 1 :]:
            if str(other_path) in visited:
                continue
            if current_hash - other_hash <= max_distance:
                group.append(other_path.name)
                visited.add(str(other_path))
        if len(group) > 1:
            groups.append(group)
    return groups
