from __future__ import annotations

# Compatibility shim for modules that still import the old service name.
# The dataset module now lives in dataset_version_service.py.

from .dataset_version_service import *  # noqa: F401,F403
