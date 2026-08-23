"""Windows Startup folder shortcut registration."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from worklog.app_paths import installed_exe_path, roaming_app_data_dir


SHORTCUT_NAME = "Desktop Worklog to Notion.lnk"


@dataclass(frozen=True)
class StartupShortcutResult:
    shortcut_path: Path
    target_path: Path
    created: bool


def startup_folder() -> Path:
    return (
        roaming_app_data_dir()
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
    )


def startup_shortcut_path() -> Path:
    return startup_folder() / SHORTCUT_NAME


def ensure_startup_shortcut(
    *,
    target_path: Path | None = None,
    shortcut_path: Path | None = None,
) -> StartupShortcutResult:
    target = (target_path or installed_exe_path()).resolve()
    shortcut = shortcut_path or startup_shortcut_path()
    shortcut.parent.mkdir(parents=True, exist_ok=True)
    _create_shortcut(shortcut, target)
    return StartupShortcutResult(
        shortcut_path=shortcut,
        target_path=target,
        created=shortcut.exists(),
    )


def shortcut_command(shortcut_path: Path, target_path: Path) -> str:
    shortcut = _ps_single_quote(str(shortcut_path))
    target = _ps_single_quote(str(target_path))
    working_dir = _ps_single_quote(str(target_path.parent))
    return (
        "$Shell = New-Object -ComObject WScript.Shell; "
        f"$Shortcut = $Shell.CreateShortcut({shortcut}); "
        f"$Shortcut.TargetPath = {target}; "
        f"$Shortcut.WorkingDirectory = {working_dir}; "
        "$Shortcut.Save()"
    )


def _create_shortcut(shortcut_path: Path, target_path: Path) -> None:
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            shortcut_command(shortcut_path, target_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def _ps_single_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
