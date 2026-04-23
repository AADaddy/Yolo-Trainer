# Dataset Module Spec

## Purpose

This document is the working reference for the dataset module in `Yolo Trainer`.

It exists to keep product behavior, backend logic, storage rules, and UI behavior aligned as the project grows. The dataset module has enough moving parts now that a written spec is more reliable than relying on memory or code inspection alone.

## Scope

This spec covers:

- the Datasets page
- dataset import and cleanse
- dataset versioning
- dataset storage ownership
- duplicate detection rules
- progress reporting during import
- dataset deletion behavior
- the boundary between dataset import and training preparation

This spec does not define:

- YOLO model training hyperparameter behavior
- tracking features
- Label Studio integration details beyond the current placeholder state

## Product Goals

- Let users import YOLO-style datasets into a project with immediate cleansing.
- Keep dataset versions as additive deltas rather than snapshots.
- Store accepted dataset files on disk, not in SQLite blobs.
- Prevent duplicate accumulation across versions.
- Make deletion safe by ensuring each stored dataset item belongs to exactly one dataset version.
- Keep training preparation separate from import-time cleansing.

## Non-Goals

- Import-time train/val split generation
- Import-time `data.yaml` generation
- Raw junk-file preservation
- Snapshot-style version cloning
- Label Studio sync/version mirroring

## Core Definitions

### Project

A project is the top-level container for dataset versions and training runs.

### Dataset Version

A dataset version represents one import event.

Important:

- A dataset version stores only the accepted new files from that import.
- It is a delta, not a full snapshot.
- A dataset version may add zero or more files conceptually, but the current workflow is expected to create versions only when there are accepted files worth keeping.

### Dataset Item

A dataset item is one accepted image/label pair stored in the project dataset pool.

Important:

- Each dataset item belongs to exactly one dataset version.
- Dataset items are the ownership boundary used for deletion.

### Cumulative Dataset

For any selected dataset version, the cumulative dataset means:

- all dataset items from earlier versions in the same project
- plus all dataset items from the selected version

Training uses the cumulative dataset, not only the delta from the selected version.

## Versioning Model

The dataset module uses additive delta versioning.

Rules:

- Each import creates at most one dataset version.
- The version contains only the newly accepted files from that import.
- Rejected files are not stored.
- Failed raw imports are not stored.
- Dataset versions are ordered by creation time and id for cumulative calculations.

Example:

- `v1` imports 100 accepted files
- `v2` imports 5 accepted new files
- `v3` imports 20 accepted new files

Then:

- `v1` cumulative total = 100
- `v2` cumulative total = 105
- `v3` cumulative total = 125

## Storage Model

Accepted dataset files live on disk under the project storage directory.

Current layout:

```text
backend/storage/projects/{project_id}-{slug}/dataset/
  images/
  labels/
```

Rules:

- Images and labels are stored as files on disk.
- SQLite stores metadata and ownership only.
- All accepted files across all versions share the same project dataset pool.
- File names are derived from content hashing for storage stability.

## Database Model

The current schema is centered on:

- `projects`
- `dataset_versions`
- `dataset_items`
- `training_runs`

### `dataset_versions`

Stores:

- version identity and note
- import status
- delta count added by that version
- cumulative image count up to that version
- cached progress payload
- validation, cleaning, stats, and import summary payloads
- error message when an import fails

### `dataset_items`

Stores:

- project ownership
- dataset version ownership
- stored image filename
- stored label filename
- exact image hash
- exact label hash
- width and height
- created timestamp
- source filenames for reference/debugging

Invariant:

- a `dataset_item` belongs to exactly one `dataset_version`

## Import Modes

Current supported import modes:

- `Direct Import`
- `Label Studio` placeholder

### Direct Import

User selects a folder containing:

```text
images/
labels/
```

### Label Studio

Visible in the UI as `Coming Soon`.

Rules:

- It is intentionally not implemented yet.
- The placeholder should remain visible so future integration has a reserved place in the workflow.

## Import Workflow

Import starts immediately when the user presses `Import`.

High-level flow:

1. validate dataset structure
2. check image/label pairing
3. detect duplicates
4. validate labels
5. save accepted files
6. create dataset version metadata
7. complete or fail import

### Detailed Cleanse Rules

The import workflow must:

- validate the existence of `images/` and `labels/`
- detect missing labels
- detect orphan labels
- detect corrupt images
- preserve empty labels as valid background images
- detect invalid YOLO labels
- reject duplicates already present in the project dataset pool
- optionally reject perceptual duplicates inside the current import batch based on the configured threshold
- store only accepted files, including valid empty-label background images
- create metadata only for accepted files

Rejected files must not be preserved in storage.

## Duplicate Detection Model

Duplicate handling uses two layers.

### Exact Duplicate Detection

Purpose:

- storage safety
- cross-version dedup
- exact same-file dedup inside the same import

Implementation behavior:

- compute SHA256 hash for each incoming image
- skip the file if that hash already exists in the project dataset pool
- skip the file if the same hash already appeared earlier in the same import

This behavior is always on.

### Visual Duplicate Detection

Purpose:

- optional perceptual near-duplicate cleanup within the current import batch

Implementation behavior:

- compute perceptual hashes using `imagehash.phash`
- group images whose perceptual distance is within the configured threshold
- keep the first item in each group
- skip later items in the same group

This behavior only applies within the current import batch. It does not compare perceptual duplicates against older project versions.

### Visual Duplicate Threshold

The import form exposes a visual duplicate threshold setting.

Current values:

- `Off`: disable perceptual duplicate cleanup entirely
- `0`: only identical perceptual hashes are skipped
- `1`: very strict
- `2`: strict
- `3`: balanced
- `4`: aggressive
- `5-8`: increasingly aggressive

Default:

- `Off`

Rationale:

- Camera/video datasets often contain many frames that are visually similar but still useful for training.
- The safest default is to leave perceptual duplicate skipping off unless the user explicitly enables it.

## Import Progress Reporting

Progress is stored on the dataset version and polled by the UI.

Current steps:

- `validating_dataset`
- `checking_image_label_pairs`
- `detecting_duplicates`
- `validating_labels`
- `saving_accepted_files`
- `creating_dataset_version`
- `completed`

Rules:

- Import progress must be visible while the import runs.
- The most recently started import should remain the active progress target in the UI.
- Both success and failure are terminal states.

## Datasets Page Requirements

The Datasets page is split into two sections.

### Top Section: Import + Cleanse

Must include:

- import mode selection
- version name field
- dataset path field for direct import
- version note field
- visual duplicate threshold control
- import progress
- import summary

Current UX decisions:

- `Version Name` and `Dataset Path` share the same row
- `Version Note` is on the next row
- required fields are marked with `*`
- visual duplicate threshold defaults to `Off`
- selecting an import mode expands the detailed import form, and selecting it again collapses the form
- direct import uses one combined dataset folder containing `images/` and `labels/`

### Bottom Section: Dataset Versions List

Each row shows:

- version name
- note
- cumulative total images up to that version
- datetime added
- delete action
- view dataset action

The list must not show local dataset source paths.

### Dataset Inspection Page

The `View Dataset` action opens a separate inspection page scoped to the selected dataset version.

Rules:

- inspection scope is cumulative up to the selected version, not delta-only
- breadcrumb navigation should allow easy return to Projects and Datasets
- a visible Back button returns to the Datasets page
- empty-label images must be visible because they are intentional background samples
- preview overlays draw all valid YOLO boxes and gracefully show no boxes for empty labels

Initial filters:

- file name search, using partial case-insensitive matching
- image resolution
- bounding-box normalized area bucket, using the same bucket definitions as the dashboard
- label state: has labels, empty label, single object, multiple objects

Bounding-box filters match an image when any box in that image matches the selected bucket.

Preview behavior:

- enlarged preview uses most of the viewport while preserving image aspect ratio
- clicking outside the preview content closes it
- previous/next controls stay within the current filtered, paginated result order
- first/last image navigation is disabled at the edges

## Import Summary Requirements

After import, the top section should show:

- imported file count
- accepted new image count
- total duplicates skipped
- exact duplicates skipped
- visual duplicates skipped
- visual duplicate threshold used
- corrupt images skipped
- invalid labels skipped
- empty-label background images kept

## Training Boundary

Dataset import and training preparation are intentionally separate.

Import must not:

- build train/val splits
- create `data.yaml`
- create processed training datasets

Training may:

- gather the cumulative dataset up to the selected version
- build a processed dataset cache
- split train and val
- generate `data.yaml`

## Deletion Rules

Deleting a dataset version requires exact confirmation:

- `DELETE`

Deletion must remove:

- the dataset version row
- dataset items owned by that version
- the owned image files
- the owned label files
- linked training runs and their stored artifacts

After deletion:

- cumulative totals must be recalculated
- processed training cache for that project must be cleared
- UI lists must refresh correctly

## Failure Handling

If import fails after files were copied but before metadata is finalized:

- copied files from that in-flight import should be cleaned up
- the dataset version should record failure status and traceback/error details

## Schema Reset Assumption

The dataset redesign introduced a new schema incompatible with the earlier snapshot-oriented structure.

Current startup rule:

- if the app detects the old schema, it resets the local dataset/training database and generated dataset storage so the new additive-version model can initialize cleanly

## Invariants

These should remain true unless the spec is explicitly changed.

- Dataset versions are additive deltas, not snapshots.
- Separate image-folder + label-folder import is intentionally not supported.
- Dataset import does not generate train/val split output.
- Dataset import does not generate `data.yaml`.
- Accepted files live on disk, not in SQLite blobs.
- Dataset items belong to exactly one dataset version.
- Exact duplicate skipping is always enabled.
- Visual duplicate skipping is configurable and defaults to `Off`.
- Training uses the cumulative dataset up to the selected version.
- Deleting a dataset version removes its owned files safely.

## Change Management Notes

If future work changes behavior in this module, update:

- this spec
- README user-facing workflow notes
- any relevant backend service comments
- Datasets page text so UI and behavior remain aligned
