from __future__ import annotations

import hashlib


SPLIT_RATIO_BUCKETS = {
    "80/20": 80,
    "90/10": 90,
    "70/30": 70,
}


def get_supported_split_ratios() -> list[str]:
    return list(SPLIT_RATIO_BUCKETS.keys())


def validate_split_ratio(split_ratio: str) -> str:
    if split_ratio not in SPLIT_RATIO_BUCKETS:
        raise ValueError(f"Unsupported split ratio: {split_ratio}")
    return split_ratio


def get_split_bucket(image_hash: str) -> int:
    # The split uses the stored image hash so the same image always resolves to
    # the same train/val bucket, even when later imports add more images.
    numeric_value = int(hashlib.sha256(image_hash.encode("utf-8")).hexdigest(), 16)
    return numeric_value % 100


def choose_split(image_hash: str, split_ratio: str) -> str:
    split_ratio = validate_split_ratio(split_ratio)
    return "train" if get_split_bucket(image_hash) < SPLIT_RATIO_BUCKETS[split_ratio] else "val"
