"""Windows Startup folder shortcut registration."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from worklog.app_paths import installed_exe_path, roaming_app_data_dir


SHORTCUT_NAME = "Desktop Worklog to Notion.lnk"
HIDDEN_RUNNER_NAME = "run-hidden.vbs"


@dataclass(frozen=True)
class StartupShortcutResult:
    shortcut_path: Path
    target_path: Path
    runner_path: Path
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


def hidden_runner_path(target_path: Path | None = None) -> Path:
    target = (target_path or installed_exe_path()).resolve()
    return target.parent / HIDDEN_RUNNER_NAME


def ensure_startup_shortcut(
    *,
    target_path: Path | None = None,
    shortcut_path: Path | None = None,
) -> StartupShortcutResult:
    target = (target_path or installed_exe_path()).resolve()
    shortcut = shortcut_path or startup_shortcut_path()
    runner = hidden_runner_path(target)
    shortcut.parent.mkdir(parents=True, exist_ok=True)
    runner.parent.mkdir(parents=True, exist_ok=True)
    _write_hidden_runner(runner, target)
    _create_shortcut(shortcut, target, runner)
    return StartupShortcutResult(
        shortcut_path=shortcut,
        target_path=target,
        runner_path=runner,
        created=shortcut.exists(),
    )


def shortcut_command(shortcut_path: Path, target_path: Path, runner_path: Path) -> str:
    shortcut = _ps_single_quote(str(shortcut_path))
    wscript = _ps_single_quote("wscript.exe")
    arguments = _ps_single_quote(f'//B //Nologo "{runner_path}"')
    working_dir = _ps_single_quote(str(target_path.parent))
    return (
        "$Shell = New-Object -ComObject WScript.Shell; "
        f"$Shortcut = $Shell.CreateShortcut({shortcut}); "
        f"$Shortcut.TargetPath = {wscript}; "
        f"$Shortcut.Arguments = {arguments}; "
        f"$Shortcut.WorkingDirectory = {working_dir}; "
        "$Shortcut.WindowStyle = 7; "
        "$Shortcut.Save()"
    )


def hidden_runner_script(target_path: Path) -> str:
    target = _vbs_quote(str(target_path))
    working_dir = _vbs_quote(str(target_path.parent))
    command = _vbs_quote(f'"{target_path}" run')
    return (
        'Set Shell = CreateObject("WScript.Shell")\n'
        f"Shell.CurrentDirectory = {working_dir}\n"
        f"Shell.Run {command}, 0, False\n"
    )


def _write_hidden_runner(runner_path: Path, target_path: Path) -> None:
    runner_path.write_text(hidden_runner_script(target_path), encoding="utf-8")


def _create_shortcut(shortcut_path: Path, target_path: Path, runner_path: Path) -> None:
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            shortcut_command(shortcut_path, target_path, runner_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def _ps_single_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _vbs_quote(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'
