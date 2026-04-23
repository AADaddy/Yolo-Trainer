from __future__ import annotations

from backend.config import TRACKING_CONFIG_DIR


def get_tracking_module_status() -> dict:
    TRACKING_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return {
        "enabled": False,
        "message": "Tracking parameter collaboration module placeholder.",
        "storage_path": str(TRACKING_CONFIG_DIR),
        "notes": [
            "Keep tracking APIs in /api/tracking.",
            "Keep tracking business logic in services/tracking_parameters.py or sibling modules.",
            "Use dedicated storage so tracking and YOLO training can evolve independently."
        ],
    }
