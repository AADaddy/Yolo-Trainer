# YOLO Trainer Context

This is the concise current-state source of truth for future patch work. It is not a changelog.

## Product Purpose

YOLO Trainer is a local web app for managing YOLO-style camera datasets, training YOLO models, and comparing completed runs. It uses FastAPI, SQLite, local disk storage, React, and Vite.

## Current Module Behavior

### Dataset Import

- Imports are async and show progress on the Datasets page.
- Supported import modes:
  - combined folder containing `images/` and `labels/`
  - Label Studio placeholder, visible as Coming Soon only
- Exact SHA256 duplicate detection is always active.
- Optional perceptual duplicate cleanup applies only inside the current import batch.
- Empty label files are accepted and preserved as intentional background images.
- Invalid labels, corrupt images, missing labels, and orphan labels are not accepted.
- Dataset import does not create train/val splits, processed datasets, or `data.yaml`.

### Dataset Versioning

- Dataset versions are additive delta imports.
- A version owns only the new accepted files from that import.
- All accepted files share the project dataset pool on disk.
- Each dataset item belongs to exactly one dataset version.
- Cumulative totals are calculated by version creation order and id.

### Dataset Dashboard

- Dashboard stats are computed on demand from cumulative dataset items up to the selected version.
- The dashboard is optimized for compact 2-class dataset review.
- Charts stay visually neutral; conclusion boxes carry green/yellow/red interpretation.
- Bounding-box analytics include normalized area, normalized height, pixel-height visibility, and a lightweight aspect-ratio support check.
- Resolution analysis is summarized rather than shown as a heavy chart.

### Dataset Inspection

- `View Dataset` opens a separate Dataset Inspection page.
- Inspection scope is cumulative up to the selected dataset version, not delta-only.
- Filters include file name search, resolution, bounding-box area bucket, and label state.
- Box filters match an image if any box in that image matches the selected bucket.
- Empty-label images must be inspectable and shown as background samples.
- Preview supports toggleable bounding-box overlays, previous/next navigation within the current filtered page, outside-click dismissal, and empty labels with no boxes.

### Training

- Training uses the cumulative dataset up to the selected version.
- The processed dataset is rebuilt only when a run starts.
- Only one processed dataset exists per project at a time.
- Train/val split is deterministic and hash-based.
- Supported split ratios are `80/20`, `90/10`, and `70/30`.
- Saved training config is per project and saved only on `Start Training`.
- Advanced options:
  - `mosaic_enabled`, default `true`
  - `multiscale_enabled`, default `false`
- Run metadata stores all training parameters in `parameters_json` and `parameters.json`.

### Model Comparison

- Comparison uses completed runs only.
- Filters include dataset version, YOLO version, and model size.
- Rows include mAP50, mAP50-95, precision, recall, inference time, image size, started time, and run parameters.
- Clicking a comparison table row opens a right-side drawer that displays the saved applied run parameters and metric summary.
- Summary cards select Best Accuracy, Best Speed, and Best Balanced Choice.
- Best balanced score weights mAP50-95 at 65% and inverse inference time at 35%.

## Important Design Decisions

- Dataset import and training preparation are separate workflows.
- Empty-label images are valid background training data, not cleanup failures.
- Dashboard, inspection, and training all share cumulative-by-version semantics.
- Dataset files live on disk; SQLite stores metadata, ownership, reports, and run records.
- The UI keeps Label Studio visible as a future integration point without implementing it.
- YOLO26 is a placeholder and should fail early unless matching weights are available.

## Removed / Forbidden Features

Do not reintroduce:

- Snapshot-style dataset versions.
- Separate image-folder + label-folder import.
- Train/val splitting during dataset import.
- Import-time `data.yaml` generation.
- Empty-label rejection during import.
- Delta-only dashboard, inspection, or training scope.
- SQLite image/label blob storage.
- Global/permanent perceptual duplicate matching across old versions.
- A working Label Studio flow unless explicitly requested.
- YOLO26 training without available `yolo26*.pt` weights and support.

## Navigation Expectations

- Breadcrumbs appear across major pages.
- Users should be able to navigate back to Projects easily.
- Dataset Inspection also provides a visible Back button to Datasets.

## Shared UI Expectations

- Help tooltips use the shared portal-based `Tooltip` component so they can render outside tables, cards, drawers, and other overflow containers.

## Keep This File Concise

Update this file when current behavior changes. Do not turn it into a historical changelog.
