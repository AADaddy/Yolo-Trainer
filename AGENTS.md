# YOLO Trainer Agent Guide

## Project Overview

YOLO Trainer is a local FastAPI + React app for camera dataset management, YOLO training, and model comparison.

Major modules:

- Projects: create, select, edit, and delete project containers.
- Datasets: import YOLO datasets, cleanse them, and manage additive dataset versions.
- Dataset Dashboard: inspect cumulative dataset quality and training usefulness.
- Dataset Inspection: visually inspect cumulative images, labels, empty-label backgrounds, and box overlays.
- Training: configure and run queued YOLO jobs from selected dataset versions.
- Model Comparison: compare completed runs by accuracy, speed, and deployability tradeoffs.

## Working Rules For Codex

- Read [docs/YOLO_TRAINER_CONTEXT.md](docs/YOLO_TRAINER_CONTEXT.md) before changing behavior.
- Read [docs/API_CONTRACTS.md](docs/API_CONTRACTS.md) before changing API shapes or frontend/backend contracts.
- Prefer incremental patches over broad rewrites.
- Preserve dataset versioning, training, dashboard, and inspection semantics unless the user explicitly asks to change them.
- Keep business logic in services. Route handlers should stay thin.
- Update README and docs when behavior changes.
- Add comments only for important decisions or non-obvious logic.

## Do Not Reintroduce These

- Do NOT switch dataset versions from additive deltas back to snapshot copies.
- Do NOT split train/val during dataset import.
- Do NOT generate `data.yaml` during dataset import.
- Do NOT remove empty-label images during dataset import; they are valid background samples.
- Do NOT reintroduce separate image-folder + label-folder import.
- Do NOT break cumulative-by-version semantics for dashboard stats, inspection, or training.
- Do NOT store accepted images/labels as SQLite blobs.
- Do NOT compare visual duplicates against older project versions; perceptual duplicate cleanup is import-batch scoped.
- Do NOT make Label Studio look implemented; it is a visible Coming Soon placeholder.
- Do NOT enable YOLO26 as trainable unless matching `yolo26*.pt` weights and support are added.

## Key Expectations

- Dataset import stores accepted files in `backend/storage/projects/{project_id}-{slug}/dataset/`.
- Dataset items belong to exactly one dataset version.
- Training rebuilds the processed dataset when a run starts, not during import.
- Only one processed dataset exists per project at a time.
- Saved training config is per project and saved only when `Start Training` is clicked.
- Breadcrumb navigation should keep major pages easy to reach from Projects.

## Reference Docs

- Current product truth: [docs/YOLO_TRAINER_CONTEXT.md](docs/YOLO_TRAINER_CONTEXT.md)
- API/frontend contracts: [docs/API_CONTRACTS.md](docs/API_CONTRACTS.md)
- Dataset module details: [docs/dataset-module-spec.md](docs/dataset-module-spec.md)
