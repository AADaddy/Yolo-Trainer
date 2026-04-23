from __future__ import annotations

# Backward-compatible wrapper around the newer processed dataset builder.

from .processed_dataset_builder import get_processed_dataset_dir
from .processed_dataset_builder import rebuild_processed_dataset as _rebuild_processed_dataset
from .dataset_version_service import get_dataset_version


def get_processed_dataset(project_id: int, version_name: str):
    return get_processed_dataset_dir(project_id)


def prepare_processed_dataset(dataset_version_id: int) -> dict:
    dataset_version = get_dataset_version(dataset_version_id)
    return _rebuild_processed_dataset(dataset_version["project_id"], dataset_version_id, "80/20")
