"""Runtime paths for installed Windows exe builds."""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


APP_FOLDER_NAME = "DesktopWorklogToNotion"
EXE_NAME = "desktop-worklog-to-notion.exe"


@dataclass(frozen=True)
class InstallResult:
    frozen: bool
    source_exe: Path | None
    target_exe: Path
    copied: bool = False
    already_installed: bool = False


def is_frozen_app() -> bool:
    return bool(getattr(sys, "frozen", False))


def local_app_data_dir() -> Path:
    value = os.getenv("LOCALAPPDATA")
    if value:
        return Path(value)
    return Path.home() / "AppData" / "Local"


def roaming_app_data_dir() -> Path:
    value = os.getenv("APPDATA")
    if value:
        return Path(value)
    return Path.home() / "AppData" / "Roaming"


def install_root() -> Path:
    return local_app_data_dir() / APP_FOLDER_NAME


def installed_app_dir() -> Path:
    return install_root() / "app"


def installed_exe_path() -> Path:
    return installed_app_dir() / EXE_NAME


def runtime_state_dir() -> Path:
    return install_root() / "state"


def runtime_logs_dir() -> Path:
    return install_root() / "logs"


def user_settings_path() -> Path:
    return roaming_app_data_dir() / APP_FOLDER_NAME / "settings.json"


def current_executable_path() -> Path:
    return Path(sys.executable).resolve()


def ensure_installed_exe(
    *,
    source_exe: Path | None = None,
    target_exe: Path | None = None,
    frozen: bool | None = None,
) -> InstallResult:
    """Copy the frozen exe to the stable AppData install path when needed."""
    frozen = is_frozen_app() if frozen is None else frozen
    target = (target_exe or installed_exe_path()).resolve()

    if not frozen:
        return InstallResult(
            frozen=False,
            source_exe=None,
            target_exe=target,
        )

    source = (source_exe or current_executable_path()).resolve()
    if _same_path(source, target):
        return InstallResult(
            frozen=True,
            source_exe=source,
            target_exe=target,
            already_installed=True,
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    if _copy_needed(source, target):
        shutil.copy2(source, target)
        copied = True
    else:
        copied = False

    return InstallResult(
        frozen=True,
        source_exe=source,
        target_exe=target,
        copied=copied,
        already_installed=False,
    )


def _copy_needed(source: Path, target: Path) -> bool:
    if not target.exists():
        return True
    source_stat = source.stat()
    target_stat = target.stat()
    return (
        source_stat.st_size != target_stat.st_size
        or int(source_stat.st_mtime) > int(target_stat.st_mtime)
    )


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.samefile(right)
    except FileNotFoundError:
        return left == right
