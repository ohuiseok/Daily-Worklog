"""Configuration loading and initialization helpers."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from worklog.app_paths import is_frozen_app, install_root, runtime_state_dir
from worklog.settings import load_user_settings, settings_to_config_overrides


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKLOG_DIR = install_root() if is_frozen_app() else PROJECT_ROOT / ".worklog"
STATE_DIR = runtime_state_dir() if is_frozen_app() else WORKLOG_DIR / "state"
ENV_EXAMPLE_PATH = PROJECT_ROOT / ".env.example"
LOCAL_ENV_PATH = PROJECT_ROOT / ".env"

DEFAULT_EXCLUDE_DIRS = (
    ".git",
    ".worklog",
    ".pytest_cache",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    ".next",
    ".cache",
    ".gradle",
    ".gradle-home",
    "__pycache__",
    "$RECYCLE.BIN",
    "Cache",
    "Cache_Data",
    "Code Cache",
    "GPUCache",
    "DawnCache",
    "ShaderCache",
    "GrShaderCache",
    "Service Worker",
    "IndexedDB",
    "Local Storage",
    "Session Storage",
    "blob_storage",
)
DEFAULT_EXCLUDE_EXTENSIONS = (
    ".lnk",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".zip",
    ".7z",
    ".rar",
    ".exe",
    ".msi",
    ".dll",
    ".jar",
    ".bin",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".crt",
    ".cer",
    ".tmp",
    ".log",
    ".lock",
    ".spec",
)
DEFAULT_EXCLUDE_NAME_PATTERNS = (
    "~$*",
    "스크린샷*",
    "Screenshot*",
    "test_workspace",
)


@dataclass(frozen=True)
class InitResult:
    created: bool
    config_path: Path
    message: str


def init_config() -> InitResult:
    """Create a local .env file from .env.example without overwriting it."""
    if LOCAL_ENV_PATH.exists():
        return InitResult(
            created=False,
            config_path=LOCAL_ENV_PATH,
            message="Local .env already exists; leaving it unchanged.",
        )

    if not ENV_EXAMPLE_PATH.exists():
        raise FileNotFoundError(f"Missing example env file: {ENV_EXAMPLE_PATH}")

    shutil.copyfile(ENV_EXAMPLE_PATH, LOCAL_ENV_PATH)
    return InitResult(
        created=True,
        config_path=LOCAL_ENV_PATH,
        message="Created local .env from .env.example.",
    )


def load_config(env_path: Path | None = LOCAL_ENV_PATH) -> dict[str, Any]:
    """Load runtime configuration from environment variables and .env."""
    if env_path is not None:
        load_dotenv(env_path)
    settings_config = settings_to_config_overrides(load_user_settings())
    settings_notion = settings_config["notion"]
    return {
        "project_name": _env(
            "WORKLOG_PROJECT_NAME",
            str(settings_config["project_name"]),
        ),
        "root_paths": _env_list(
            "WORKLOG_ROOT_PATHS",
            list(settings_config["root_paths"]),
        ),
        "timezone": _env("WORKLOG_TIMEZONE", "Asia/Seoul"),
        "notion": {
            "token": _env("NOTION_TOKEN", str(settings_notion["token"])),
            "database_id": _env(
                "NOTION_DATABASE_ID",
                str(settings_notion["database_id"] or "NOTION_DATABASE_ID"),
            ),
            "source": _env("NOTION_SOURCE", str(settings_notion["source"])),
        },
        "scan": {
            "first_run_mode": _env("WORKLOG_FIRST_RUN_MODE", "baseline_only"),
            "max_file_size_kb": _env_int("WORKLOG_MAX_FILE_SIZE_KB", 1024),
            "max_scanned_files": _env_int("WORKLOG_MAX_SCANNED_FILES", 20000),
            "max_scan_seconds": _env_int("WORKLOG_MAX_SCAN_SECONDS", 180),
            "max_analysis_files": _env_int("WORKLOG_MAX_ANALYSIS_FILES", 10000),
            "hash_file_content": _env_bool("WORKLOG_HASH_FILE_CONTENT", False),
            "text_preview_lines": _env_int("WORKLOG_TEXT_PREVIEW_LINES", 40),
            "table_preview_rows": _env_int("WORKLOG_TABLE_PREVIEW_ROWS", 10),
            "exclude_dirs": _env_list("WORKLOG_EXCLUDE_DIRS", DEFAULT_EXCLUDE_DIRS),
            "exclude_extensions": _env_list(
                "WORKLOG_EXCLUDE_EXTENSIONS",
                DEFAULT_EXCLUDE_EXTENSIONS,
            ),
            "exclude_name_patterns": _env_list(
                "WORKLOG_EXCLUDE_NAME_PATTERNS",
                DEFAULT_EXCLUDE_NAME_PATTERNS,
            ),
        },
        "git": {
            "auto_author": _env_bool("WORKLOG_GIT_AUTO_AUTHOR", True),
            "author_emails": _env_list("WORKLOG_GIT_AUTHOR_EMAILS", []),
            "author_names": _env_list("WORKLOG_GIT_AUTHOR_NAMES", []),
        },
        "privacy": {
            "upload_raw_content": _env_bool("WORKLOG_UPLOAD_RAW_CONTENT", True),
            "upload_file_attachments": _env_bool(
                "WORKLOG_UPLOAD_FILE_ATTACHMENTS",
                False,
            ),
            "upload_relative_paths_only": _env_bool(
                "WORKLOG_UPLOAD_RELATIVE_PATHS_ONLY",
                True,
            ),
            "mask_sensitive_file_names": _env_bool(
                "WORKLOG_MASK_SENSITIVE_FILE_NAMES",
                True,
            ),
        },
    }


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip()


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value.strip())
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"{name} must be true or false.")


def _env_list(name: str, default: list[str] | tuple[str, ...]) -> list[str]:
    value = os.getenv(name)
    if value is None or not value.strip():
        return list(default)
    return [item.strip() for item in value.split(";") if item.strip()]
