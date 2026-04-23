# Yolo Trainer

Yolo Trainer is a local desktop-friendly web application for managing camera training projects, additive YOLO dataset imports, async training runs, and run comparison.

## Overview

![Dataset Import](./docs/Screenshots/Dataset%20Import.png)

![Training Page](./docs/Screenshots/Training%20Page.png)

## Stack

- Backend: Python 3.12, FastAPI, SQLite, Pydantic, Ultralytics YOLO
- Frontend: React, TailwindCSS, Vite
- Dataset tooling: Pillow, ImageHash, NumPy, Matplotlib

## Project Structure

```text
Yolo Trainer/
  backend/
  docs/
  frontend/
  requirements.txt
  README.md
```

## Specs

Persistent docs for future Codex work:

- [Agent Guide](./AGENTS.md)
- [YOLO Trainer Context](./docs/YOLO_TRAINER_CONTEXT.md)
- [API Contracts](./docs/API_CONTRACTS.md)
- [Dataset Module Spec](./docs/dataset-module-spec.md)

Use these as the source of truth for current behavior, API shapes, dataset import, versioning, storage ownership, dedup rules, deletion behavior, and the boundary between import and training preparation.

## Backend Setup

Use a per-project virtual environment for `Yolo Trainer` instead of reusing one from another folder. This keeps dependencies isolated and avoids version conflicts between projects.

1. From the project root, create and activate a Python 3.12 virtual environment:

```bash
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

This creates the virtual environment inside your local project checkout:

```text
<project-root>/.venv
```

2. Install Python dependencies:

```bash
pip install -r requirements.txt
```

3. Start the backend from the project root:

```bash
uvicorn backend.main:app --reload
```

The API will run on `http://127.0.0.1:8000`.

## VS Code Interpreter Setup

After creating the virtual environment, set VS Code to use it for this project:

1. Open the `Yolo Trainer` folder in VS Code.
2. Press `Ctrl+Shift+P`.
3. Run `Python: Select Interpreter`.
4. Choose the interpreter from this project's virtual environment.

```text
Windows: <project-root>\.venv\Scripts\python.exe
macOS/Linux: <project-root>/.venv/bin/python
```

If it does not appear in the list:

1. Press `Ctrl+Shift+P`.
2. Run `Python: Select Interpreter`.
3. Choose `Enter interpreter path`.
4. Choose `Find...`.
5. Select the interpreter from this project's virtual environment:

```text
Windows: <project-root>\.venv\Scripts\python.exe
macOS/Linux: <project-root>/.venv/bin/python
```

Once selected, VS Code will use the project environment for imports, linting, debugging, and terminal Python commands in this workspace.

## Frontend Setup

1. Open a second terminal in `frontend/`.
2. Install frontend dependencies:

```bash
npm install
```

3. Start the Vite development server:

```bash
npm run dev
```

The UI will run on `http://127.0.0.1:5173`.

## Modular Architecture

The project is structured so training, dataset management, and future tracking features can evolve independently.

- `backend/main.py` only creates the app and bootstraps shared middleware.
- `backend/api/router.py` is the central place where feature routers are registered.
- `backend/api/` contains HTTP-facing modules grouped by feature.
- `backend/services/` contains business logic and feature workflows.
- `backend/config.py` holds shared paths and app configuration to avoid hard-coded values across modules.
- `backend/api/tracking.py` and `backend/services/tracking_parameters.py` are reserved for the future tracking-parameter collaboration module.
- `backend/storage/projects/` keeps project training artifacts separate from future tracking storage.
- Frontend help tooltips use a shared portal-based component so long help text is not clipped by tables, cards, or scrolling panels.

When you merge the tracking tool later, the cleanest pattern is:

1. Put its HTTP endpoints under `backend/api/tracking.py` or additional tracking API modules.
2. Put its business logic under `backend/services/tracking_*.py`.
3. Give it dedicated storage under `backend/storage/tracking/`.
4. Keep shared concepts in isolated helper modules instead of mixing training and tracking logic together.

## How To Add Projects

1. Open the `Projects` page.
2. Create a project with a name, camera name, and optional description.

Example:

- Name: `Parking Camera`
- Camera Name: `CAM_12`

## Dataset Import Workflow

The Datasets page is split into two sections:

- Top: dataset import + cleanse
- Bottom: dataset versions list

Each dataset version is an additive delta import:

- one version = one import event
- a version stores only the accepted new files from that import
- junk files are not preserved
- failed raw imports are not preserved
- duplicate images that already exist in the project dataset pool are skipped
- visually duplicate images within the same import batch are also detected during cleanse
- empty label files are preserved as valid background images for training

Files are stored on disk, not in SQLite:

```text
backend/storage/projects/{project}/dataset/
  images/
  labels/
```

All accepted files from all imports live in those shared folders, and each stored image/label is associated with exactly one dataset version in the database.

### Supported Import Methods

Direct Import:

- select one folder that contains `images/` and `labels/`

Label Studio:

- connect to self-hosted Label Studio
- currently shown in the UI as `Coming Soon`
- not implemented yet

### What Happens When You Press Import

Import immediately runs the dataset cleanse workflow. It does not wait for training.

The cleanse flow:

1. validates the dataset structure
2. checks image/label pairs
3. detects duplicates against the existing project dataset pool
4. detects perceptual duplicate images inside the current import batch
5. detects corrupt images
6. preserves empty-label images as background samples
7. detects invalid YOLO labels
8. accepts only valid new images and valid empty-label background images
9. stores only accepted files into the project dataset folders
10. creates a dataset version containing metadata for only those accepted files

Duplicate handling now works in two layers:

- Exact duplicate detection: SHA256 file hashes prevent re-importing images already stored in the project dataset pool and also catch exact duplicate files repeated inside the same import.
- Perceptual duplicate detection: image perceptual hashing is used inside the current import batch to catch visually duplicated images even when the files are not byte-identical. These are reported in the cleanse output and skipped from the accepted delta set.

The Datasets import form now includes a visual-duplicate threshold slider:

- `Off` default: disables perceptual visual-duplicate cleanup entirely
- `0`: only identical perceptual hashes are skipped
- `1`: very strict
- `2`: strict
- `3`: balanced
- `4`: aggressive
- `5-8`: increasingly aggressive and more likely to remove visually similar but still useful training samples

Exact SHA256 duplicate skipping is always active, regardless of the visual threshold.

The top section shows:

- progress stages
- current import status
- imported file count
- accepted new images count
- duplicates skipped
- exact duplicates skipped
- visual duplicates skipped
- visual duplicate threshold used for that import
- corrupt images skipped
- invalid labels skipped
- empty-label background images kept

### Important Separation From Training

Dataset import does not:

- split train/val
- build a processed training dataset
- generate `data.yaml`

Those steps remain part of the training workflow only. When training starts, the backend prepares the cumulative dataset up to the selected version, then creates the train/val split and `data.yaml`.

### Dataset Versions List

The bottom section shows dataset versions in list form with:

- version name
- note
- total images up to that version
- datetime added
- `View Dataset` action
- delete action

The total shown in the list is cumulative, not delta-only.

Example:

- `v1` adds 100 images, list shows 100
- `v2` adds 5 images, list shows 105
- `v3` adds 20 images, list shows 125

### Dataset Inspection

Each dataset version row includes `View Dataset`. This opens a dedicated inspection page for visually reviewing images and labels.

Inspection always uses the cumulative dataset up to the selected version, matching training and dashboard behavior:

- if `v1` has 100 images
- and `v2` adds 5 images
- opening `View Dataset` for `v2` shows all 105 cumulative images

The inspection page includes:

- breadcrumb navigation back to Projects and Datasets
- a visible Back button
- selected version scope summary
- filters for file name search, resolution, bounding-box area bucket, and label state
- grid view by default, with a simple list view
- paginated results
- large image preview with toggleable bounding-box overlay
- preview dismissal by clicking empty space outside the image panel
- Previous/Next review controls within the current filtered, paginated result context

Supported label-state filters:

- `Has labels`
- `Empty label`
- `Single object`
- `Multiple objects`

Empty-label images are intentionally preserved and shown as background samples. In preview, they show the image without boxes and clearly indicate that no labels are present.

Bounding-box area filters use the same COCO-style normalized area buckets as the dashboard. An image matches a box filter if any box in that image belongs to the selected bucket.

File name search matches partial image names case-insensitively and combines with the other filters before pagination, so searches like `cam12_` or `00123` narrow the review set predictably.

### Deleting A Dataset Version

Deleting a version requires typing `DELETE` exactly.

Deletion removes:

- dataset version metadata
- related dataset item records
- actual image files and label files owned by that version
- linked training run metadata and stored run artifacts for that dataset version

After deletion, cumulative totals are recalculated for the remaining versions.

## Dataset Dashboard

The Dataset Stats Dashboard always uses the cumulative dataset up to the selected version, not only that version's delta.

Example:

- if `v1` has 100 images
- and `v2` adds 5 more
- selecting `v2` shows statistics for 105 cumulative images

### Dashboard Sections

The dashboard is optimized for 2-class datasets and arranged as a compact one-page responsive layout:

- Row 1: total images, total objects, avg objects per image
- Row 2: class balance, class coverage
- Row 3: objects-per-image distribution, normalized box area distribution
- Row 4: box height / pixel visibility analysis, resolution analysis

Each widget uses:

- a title
- a tooltip
- a compact visual
- a conclusion box

The conclusion box is the main indicator. Charts stay visually neutral so the meaning of green, yellow, and red lives only in the conclusion box.

The layout is intentionally dense so the key signals fit on one desktop page when possible, while still reflowing cleanly on tablet and mobile.

### Simplified Resolution Metric

The dashboard does not render a heavy resolution chart or a standalone warnings panel.

Instead it reports:

- most common resolution
- dominant resolution percentage
- top 3 resolutions plus `Other`
- number of unique resolutions

This keeps the signal useful while avoiding unnecessary chart noise and rendering overhead.

### Conclusions

Each widget now embeds its own contextual conclusion instead of relying on a separate warnings panel.

Examples:

- balanced or imbalanced class mix
- strong or weak class coverage
- healthy or skewed object density
- medium-scale or tiny-box-heavy annotation area
- healthy or weak object height for people-focused labels
- sufficient or poor pixel-height visibility for practical classification
- consistent or inconsistent resolution mix

### Bounding Box Learnability Metrics

The dashboard computes box analytics on demand from the cumulative dataset up to the selected version. These values are not treated as standalone import metadata; they follow the same selected-version cumulative scope used by training.

Normalized area is still used for dataset-scale comparison across mixed image resolutions:

- `Tiny`: area `< 0.001`
- `Small`: `0.001 <= area < 0.01`
- `Medium`: `0.01 <= area < 0.10`
- `Large`: area `>= 0.10`

Normalized height is also shown because this dataset is people-oriented. For tall, thin objects such as people, height often reflects usable visual detail better than area:

- `Very Short`: height `< 0.05`
- `Short`: `0.05 <= height < 0.10`
- `Medium`: `0.10 <= height < 0.20`
- `Tall`: height `>= 0.20`

Pixel-height visibility is included because YOLO ultimately learns from resized pixel information, not normalized coordinates alone:

- `Too Small`: `< 15 px`
- `Borderline`: `15 px` to `< 30 px`
- `Good Visibility`: `>= 30 px`

The bounding-box conclusion combines normalized area, normalized height, and pixel-height visibility. A dataset with many boxes below `15 px` height or many tiny/short boxes may be difficult for detection or staff/customer classification even when the normalized area chart looks acceptable.

A lightweight aspect-ratio support check is shown inside the height/visibility widget. It is a warning aid only: very square, very narrow, or very wide people boxes can indicate partial-body labels or annotation problems, but it is not a primary pass/fail metric.

## How To Start Training

1. Open `Training`.
2. Select a project and dataset version.
3. Choose a split ratio:
   `80/20` default, `90/10`, or `70/30`
4. Choose YOLO version and size.
5. Configure training parameters such as epochs, imgsz, batch, workers, cache, rect, optimizer, lr0, momentum, device, and amp.
5. Click `Start Training`.

Training runs asynchronously and stores artifacts under:

```text
backend/storage/projects/{project}/runs/{run_name}/
```

Each run stores:

- `best.pt`
- `last.pt`
- `metrics.json`
- `parameters.json`
- generated `data.yaml`

The selected dataset version is treated cumulatively for training, meaning the training cache includes all accepted dataset items added up to that version.

### Training Start Behavior

When `Start Training` is pressed, the app:

1. validates the selected inputs
2. saves the training config for that project
3. creates a queued run record
4. waits for earlier queued/running jobs if needed
5. clears the processed dataset folder for the project when the run actually starts
6. rebuilds the processed dataset from scratch
7. assigns train/val using deterministic hash-based splitting
8. generates a new `data.yaml`
9. starts training
10. updates metrics as the run completes

Only one processed dataset exists per project at a time.

### Training Queue

Training jobs now run through a single in-process queue.

Rules:

- only one training run executes at a time
- newly submitted runs stay in `queued` status while another run is active
- the processed dataset is rebuilt only when that queued run becomes the active run
- backend startup re-queues any stale `running` jobs left behind by a server restart, then resumes the queue

This prevents a new queued submission from clearing the processed dataset used by the currently active training job.

### Deterministic Train/Val Split

Train/val assignment is deterministic and based on the stored image hash:

- hash image
- convert to numeric value
- use modulo 100
- map to train or val according to the chosen split ratio

This keeps the same image in the same split bucket across rebuilds and avoids reshuffling older images when new data is added later.

### Saved Training Config

Training configuration is saved per project.

Rules:

- the last saved config is loaded when the training page opens for that project
- config is saved only when the user clicks `Start Training`
- unsaved edits are discarded if the user leaves the page

### Parameter Notes

The training UI shows a tooltip for each parameter explaining:

- what it does
- how changing it affects training
- the recommended default
- when to increase or decrease it

Current defaults:

- `epochs=100`
- `imgsz=1280`
- `batch=-1`
- `workers=2`
- `cache=True`
- `rect=True`
- `optimizer="AdamW"`
- `lr0=0.001`
- `momentum=0.9`
- `device="cuda"`
- `amp=True`
- `mosaic_enabled=True`
- `multiscale_enabled=False`

### Advanced Training Options

The training form includes an `Advanced Training Options` section for augmentation choices that can affect experiment comparability.

Mosaic Augmentation combines multiple images into one augmented sample. It improves variation in object scale, position, and background, which is often useful for smaller datasets and generalization. It defaults to enabled because Ultralytics uses mosaic as a standard augmentation probability by default. Disable it when you want more natural-looking samples or stricter experiment control.

Multi-scale Training varies the effective image scale during training. It can improve robustness when objects appear at very different sizes across cameras or scenes, but it can also make runs less controlled and harder to compare. It defaults to disabled so initial experiments stay easier to reason about.

Both advanced options follow the same saved-config behavior as the rest of the training form:

- the last saved project values load when the Training page opens
- values are saved only when `Start Training` is clicked
- unsaved edits are discarded when leaving the page

Every run stores `mosaic_enabled` and `multiscale_enabled` in `parameters.json` and the run metadata API response. This keeps later model comparison and run inspection trustworthy, even if these fields are not shown as top-level comparison-table columns yet.

### Training Run Deletion

Deleting a training run requires typing `DELETE`.

Deletion removes:

- the training run database record
- the run folder
- `best.pt`
- `last.pt`
- `metrics.json`
- `parameters.json`

## Model Comparison

The Model Comparison page helps compare completed runs by accuracy, speed, and overall deployment tradeoff.

### Main Comparison Sections

The page includes:

- summary cards for Best Accuracy, Best Speed, and Best Balanced Choice
- an accuracy vs speed scatter plot
- a metric comparison bar chart
- a sortable comparison table
- shared filters for dataset version, YOLO version, and model size

All filters affect the whole page together so the summary cards, charts, and table always describe the same run subset.

### Summary Cards

The three summary cards are:

- Best Accuracy: highest `mAP50-95`
- Best Speed: lowest `inference time`
- Best Balanced Choice: best weighted combination of accuracy and latency

`mAP50-95` is used for Best Accuracy because it is stricter and more reliable than `mAP50` for serious model comparison.

### Balanced Score

Best Balanced Choice uses a normalized weighted score:

- normalize `mAP50-95`
- normalize `inference time`
- reward higher accuracy
- reward lower latency

The current weighting favors accuracy first and then speed:

- `65%` normalized `mAP50-95`
- `35%` normalized inverse latency

Runs without inference time are excluded from balanced ranking and from the speed winner.

### Inference Time And Image Size

The comparison page uses:

- `inference time`: practical per-image latency when available from training results
- `image size`: saved training resolution from the run metadata

Larger image sizes can improve small-object detail but are slower; smaller image sizes are faster but may lose detail. Historical runs may show `N/A` if these values were not captured.

### Comparison Visuals

Accuracy vs Speed scatter plot:

- X-axis = inference time
- Y-axis = `mAP50-95`
- helps identify runs that are both accurate and fast

Metric Comparison bar chart:

- lets you switch between `mAP50`, `precision`, and `recall`
- useful for quick side-by-side comparison across the filtered runs

Comparison table:

- sortable by every displayed column
- includes run id, dataset version, model, `mAP50`, `mAP50-95`, precision, recall, inference time, image size, and started time
- clicking the Run ID downloads that run's `best.pt` model when available
- downloaded model filenames are auto-renamed from saved run metadata, such as `run_023_v3_yolo11s_img1280_map50-0.82.pt`
- clicking a row opens a side drawer with the saved applied run parameters and metric summary
- uses column tooltips that explain what good, moderate, and weak values look like
- color-codes the key metric values so strong, caution, and weak results are easier to scan
- handles missing historical values safely

## Supported Models

- YOLO8
- YOLO11
- YOLO26 placeholder

Sizes:

- `n`
- `s`
- `m`
- `l`
- `x`

Examples:

- `yolov8n.pt`
- `yolo11s.pt`

## Notes

- Python 3.12 is the recommended target for this project on your machine.
- `YOLO26` is included as a future placeholder and will require compatible weights before training can succeed.
- Dataset inspection is defensive and skips unreadable images instead of crashing the app.
- This redesign introduces a new dataset schema. On startup, if the app detects the old schema, it resets the local dataset/training database and generated dataset storage so the new additive-version model can initialize cleanly.
- Label Studio remains visible in the import UI as a `Coming Soon` option only.
