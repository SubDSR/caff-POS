from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "CaffPOS"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def is_desktop_mode() -> bool:
    return os.environ.get("POS_DESKTOP_MODE", "False").lower() == "true"


def get_source_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def get_bundle_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", get_source_dir()))


def get_data_dir() -> Path:
    configured_dir = os.environ.get("POS_DATA_DIR", "").strip()
    if configured_dir:
        return Path(configured_dir)

    if is_frozen() or is_desktop_mode():
        local_app_data = os.environ.get("LOCALAPPDATA")
        base_dir = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        return base_dir / APP_NAME

    return get_source_dir()


def ensure_data_dir() -> Path:
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
