from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1)
    camera_name: str = Field(min_length=1)
    description: str = ""


class ProjectRead(ProjectCreate):
    id: int
    created_at: datetime


class DatasetVersionCreate(BaseModel):
    version: str = Field(min_length=1)
    note: str = ""
    import_mode: str = "combined"
    dataset_path: str = ""
    visual_dup_threshold: int = Field(default=-1, ge=-1, le=8)


class DatasetVersionRead(BaseModel):
    id: int
    project_id: int
    version_name: str
    note: str
    created_at: datetime
    status: str
    added_image_count: int
    cumulative_image_count: int
    class_count: int
    progress_json: dict[str, Any]
    validation_report: dict[str, Any]
    cleaning_report: dict[str, Any]
    stats_report: dict[str, Any]
    import_summary_json: dict[str, Any]
    error_message: str = ""


class DatasetVersionDeleteRequest(BaseModel):
    confirmation: str


class ValidationReport(BaseModel):
    images: int
    labels: int
    matched_pairs: int
    missing_labels: list[str]
    orphan_labels: list[str]
    invalid_labels: list[dict[str, Any]]
    corrupt_images: list[str]


class DatasetStats(BaseModel):
    total_images: int
    total_labels: int
    total_objects: int
    number_of_classes: int
    objects_per_class: dict[str, int]
    objects_per_image: dict[str, int]
    bounding_box_size_distribution: dict[str, list[float]]
    image_resolution_distribution: dict[str, int]
    chart_images: dict[str, str]


class CleaningReport(BaseModel):
    duplicates: list[list[str]]
    corrupt_images: list[str]
    missing_labels: list[str]
    empty_labels: list[str]
    invalid_bounding_boxes: list[dict[str, Any]]
    very_small_bounding_boxes: list[dict[str, Any]]
    similar_frame_clusters: list[list[str]]


class TrainingRunCreate(BaseModel):
    project_id: int
    dataset_version_id: int
    split_ratio: str = "80/20"
    yolo_version: str
    model_size: str
    epochs: int = 100
    imgsz: int = 1280
    batch: int = -1
    workers: int = 2
    cache: bool = True
    rect: bool = True
    optimizer: str = "AdamW"
    lr0: float = 0.001
    momentum: float = 0.9
    device: str = "cuda"
    amp: bool = True
    mosaic_enabled: bool = True
    multiscale_enabled: bool = False


class TrainingRunRead(BaseModel):
    id: int
    project_id: int
    dataset_version_id: int
    run_name: str
    yolo_version: str
    model_size: str
    model_name: str
    split_ratio: str
    epochs: int
    imgsz: int
    batch: int
    workers: int
    cache: bool
    rect: bool
    optimizer: str
    lr0: float
    momentum: float
    device: str
    amp: bool
    mosaic_enabled: bool = True
    multiscale_enabled: bool = False
    status: str
    created_at: datetime
    updated_at: datetime
    run_path: str
    metrics_json: dict[str, Any]
    parameters_json: dict[str, Any]
    error_message: str = ""


class ComparisonRow(BaseModel):
    run: str
    model: str
    dataset_version: str
    mAP50: float
    mAP50_95: float
    precision: float
    recall: float
    status: str
