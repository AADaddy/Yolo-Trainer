from __future__ import annotations

from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
STORAGE_DIR = BACKEND_DIR / "storage"
PROJECTS_STORAGE_DIR = STORAGE_DIR / "projects"
PROCESSED_STORAGE_DIR = STORAGE_DIR / "processed"
DATABASE_PATH = STORAGE_DIR / "yolo_trainer.db"

API_PREFIX = "/api"
APP_TITLE = "Yolo Trainer"
APP_VERSION = "1.0.0"

# Tracking config is intentionally separate so a second tool can be merged
# without tangling training logic and tracking logic together.
TRACKING_CONFIG_DIR = STORAGE_DIR / "tracking"
