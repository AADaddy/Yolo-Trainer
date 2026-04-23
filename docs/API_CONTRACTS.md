# YOLO Trainer API Contracts

Base API prefix: `/api`.

This document captures stable frontend/backend contracts and semantics. Keep it current when changing response shapes.

## Dataset Versions List

### `GET /api/datasets/projects/{project_id}`

Purpose: list dataset versions for a project.

Response: array of dataset version objects.

Key fields:

- `id`: dataset version id.
- `project_id`: owning project id.
- `version_name` / `version`: user-facing version name.
- `status`: `queued`, `running`, `completed`, or `failed`.
- `added_image_count`: delta count accepted by this version.
- `cumulative_image_count`: total accepted images up to this version.
- `class_count`: class count from import stats.
- `progress_json`: import progress payload.
- `validation_report`, `cleaning_report`, `stats_report`, `import_summary_json`: JSON reports.
- `error_message`: failure detail.

Semantic rules:

- `added_image_count` is delta-only.
- `cumulative_image_count` is the number shown as total dataset size.
- Versions are additive deltas, not snapshots.

## Dataset Import

### `POST /api/datasets/projects/{project_id}`

Purpose: start async dataset import.

Request body:

- `version`: required version name.
- `note`: optional string.
- `import_mode`: `combined` or `labelstudio`.
- `dataset_path`: used by `combined`; must contain `images/` and `labels/`.
- `visual_dup_threshold`: `-1` off, otherwise `0` through `8`.

Response: newly created dataset version record with queued progress.

Semantic rules:

- Empty label files are accepted as valid background images.
- Label Studio returns an error because it is Coming Soon.
- Import does not build train/val splits or `data.yaml`.

## Dataset Dashboard Stats

### `GET /api/datasets/{dataset_version_id}/dashboard`

Purpose: return cumulative dataset analytics up to selected version.

Response sections:

- Overview:
  - `dataset_version_id`, `project_id`, `selected_version_name`
  - `total_images`, `total_labels`, `total_objects`
  - `number_of_classes`, `avg_objects_per_image`, `accepted_rate`
- Class analysis:
  - `objects_per_class`
  - `images_per_class`
  - `class_balance[]`: `class_id`, `class_name`, `object_count`, `image_count`, `percentage`
  - `class_coverage[]`: `class_id`, `class_name`, `image_count`, `image_ratio`
- Density:
  - `objects_per_image_distribution[]`: bucket rows for `0_objects`, `1_2_objects`, `3_5_objects`, `gt_5_objects`
- Bounding boxes:
  - `bounding_box_distribution.total_boxes`
  - `area_distribution[]`: Tiny, Small, Medium, Large normalized area buckets
  - `height_distribution[]`: Very Short, Short, Medium, Tall normalized height buckets
  - `pixel_visibility_distribution[]`: Too Small, Borderline, Good Visibility pixel-height buckets
  - `aspect_ratio_distribution[]`: support metric
  - ratio fields such as `tiny_or_small_percentage`, `low_height_percentage`, `too_small_pixel_percentage`
- Resolution:
  - `resolution_summary.most_common_resolution`
  - `dominant_ratio`
  - `unique_resolution_count`
  - `top_resolutions[]`
- Growth:
  - `dataset_growth[]`
  - `current_import_cleanse_summary`
  - `version_import_cleanse_summary`
- `warnings[]`: backend-generated warning strings.

Semantic rules:

- All stats are cumulative up to the selected version.
- Most numeric percentages are raw ratios from `0.0` to `1.0`.
- Color-coded conclusions are frontend interpretations, not stored backend truth.

## Dataset Inspection

### `GET /api/datasets/inspection/{dataset_version_id}/filters`

Purpose: return filter options for cumulative inspection scope.

Response:

- `dataset_version`: selected version object.
- `total_images`: cumulative image count.
- `resolutions[]`: available `WIDTHxHEIGHT` strings.
- `area_buckets[]`: `value`, `label`, `range`.
- `label_states[]`: `has_labels`, `empty_label`, `single_object`, `multiple_objects`.
- `empty_label_count`: count in cumulative scope.

### `GET /api/datasets/inspection/{dataset_version_id}/items`

Purpose: return paginated inspection items in cumulative scope.

Query params:

- `page`: 1-based page, default `1`.
- `page_size`: default `30`, max `100`.
- `resolution`: optional `WIDTHxHEIGHT`.
- `area_bucket`: optional `tiny`, `small`, `medium`, or `large`.
- `label_state`: optional `has_labels`, `empty_label`, `single_object`, or `multiple_objects`.
- `filename`: optional partial image filename search, matched case-insensitively.

Response:

- `dataset_version`: selected version object.
- `project`: project object.
- `summary`: `total_images`, `filtered_images`, `page`, `page_size`, `total_pages`.
- `items[]`:
  - `id`
  - `image_filename`, `label_filename`
  - `source_image_name`, `source_label_name`
  - `width`, `height`, `resolution`
  - `object_count`
  - `is_empty_label`
  - `label_state`
  - `area_buckets[]`
  - `class_counts`
  - `image_url`, `thumbnail_url`
  - `image_exists`
- `filters`: echo of active filters.

Semantic rules:

- Scope is cumulative up to selected version.
- Box filters include an image if any box matches the selected bucket.
- Filename search is applied before pagination and combines with the other filters.
- Empty-label images are valid results.

### `GET /api/datasets/inspection/{dataset_version_id}/items/{dataset_item_id}`

Purpose: return preview metadata and overlay boxes.

Response: inspection item metadata plus:

- `boxes[]`:
  - `line`
  - `class_id`, `class_label`
  - `x_center`, `y_center`, `width`, `height`
  - `area`
  - `area_bucket`

Semantic rules:

- YOLO box coordinates are normalized.
- Empty-label images return `boxes: []`.

### `GET /api/datasets/inspection/{dataset_version_id}/items/{dataset_item_id}/image`

Purpose: serve the image file for thumbnails and preview.

Response: file response.

## Training Configuration

### `GET /api/training/config/{project_id}`

Purpose: load last saved project training config.

Response fields include:

- `dataset_version_id`
- `split_ratio`: `80/20`, `90/10`, or `70/30`
- `yolo_version`
- `model_size`
- `epochs`, `imgsz`, `batch`, `workers`
- `cache`, `rect`, `optimizer`, `lr0`, `momentum`
- `device`, `amp`
- `mosaic_enabled`
- `multiscale_enabled`

Semantic rules:

- Config is per project.
- Defaults are merged with stored JSON, so new fields get defaults for older configs.
- Config is saved only by starting training.

## Start Training

### `POST /api/training/runs`

Purpose: save config, create queued run, and start queue processing.

Request body:

- `project_id`
- `dataset_version_id`
- all fields from training config above

Response: created training run object.

Run object key fields:

- ids: `id`, `project_id`, `dataset_version_id`
- model: `yolo_version`, `model_size`, `model_name`
- config: `split_ratio`, `epochs`, `imgsz`, `batch`, `workers`, `cache`, `rect`, `optimizer`, `lr0`, `momentum`, `device`, `amp`
- advanced config: `mosaic_enabled`, `multiscale_enabled`
- status: `queued`, `running`, `completed`, or `failed`
- paths and JSON: `run_path`, `metrics_json`, `parameters_json`, `error_message`

Semantic rules:

- Training uses cumulative dataset items up to `dataset_version_id`.
- Processed dataset rebuild happens when the queued run becomes active.
- `parameters_json` and `parameters.json` must preserve the exact run context.

## Training Runs List

### `GET /api/training/runs?project_id={project_id}`

Purpose: list training runs, optionally by project.

Response: array of training run objects.

Displayed metrics:

- `metrics_json.mAP50`: primary quick score in the runs table.
- `map50_color`: backend-derived `high`, `medium`, or `low` display hint.

Semantic rules:

- Failed runs may have empty metrics and useful `error_message`.
- Historical runs may lack newer fields inside old `parameters_json`; defaults should be handled defensively.

## Model Comparison

### `GET /api/comparison/runs`

Purpose: compare completed runs.

Query params:

- `project_id`
- `dataset_version_id`
- `yolo_version`
- `model_size`
- `sort_by`
- `sort_order`: `asc` or `desc`

Response:

- `rows[]`:
  - `id`, `run_name`
  - `dataset_version_id`, `dataset_version`
  - `yolo_version`, `model_size`, `model`
  - `mAP50`, `mAP50_95`, `precision`, `recall`
  - `inference_time_ms`, `imgsz`, `model_file_size_mb`
  - `started_at`
  - `mosaic_enabled`, `multiscale_enabled`
  - `parameters`
- `filters`:
  - `dataset_versions[]`
  - `yolo_versions[]`
  - `model_sizes[]`
- `summaries`:
  - `best_accuracy`
  - `best_speed`
  - `best_balanced`
- `sort`: normalized sort state.
- `counts`: completed, filtered, and scatter-point counts.

Semantic rules:

- Only completed runs are compared.
- Best accuracy uses `mAP50_95`.
- Best speed requires `inference_time_ms`.
- Best balanced score is computed from normalized mAP50-95 and inverse latency.
- The comparison table displays `imgsz` as Image Size from saved run parameters instead of model artifact size.
- The frontend run-details drawer should use each row's saved `parameters` object as the source of truth for applied training settings.
