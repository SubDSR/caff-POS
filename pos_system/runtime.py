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


def get_executable_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return get_source_dir()


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


def _strip_env_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def load_env_file(env_path: Path) -> None:
    if not env_path.exists() or not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue

        os.environ.setdefault(key, _strip_env_quotes(value.strip()))


def load_env_files() -> None:
    candidate_paths = [
        Path.cwd() / ".env",
        get_source_dir() / ".env",
        get_bundle_dir() / ".env",
        get_executable_dir() / ".env",
        get_data_dir() / ".env",
    ]

    seen_paths: set[Path] = set()
    for env_path in candidate_paths:
        try:
            normalized_path = env_path.resolve(strict=False)
        except OSError:
            normalized_path = env_path

        if normalized_path in seen_paths:
            continue

        seen_paths.add(normalized_path)
        load_env_file(env_path)
