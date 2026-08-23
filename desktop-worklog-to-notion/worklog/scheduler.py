"""Windows Task Scheduler integration and run locking."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from worklog.config import PROJECT_ROOT, STATE_DIR


LOCK_PATH = STATE_DIR / "run.lock"


@dataclass(frozen=True)
class SchedulerConfig:
    task_name_daily: str = "DesktopWorklogToNotionDaily"
    task_name_logon: str = "DesktopWorklogToNotionLogon"
    daily_time: str = "23:30"


class AlreadyRunningError(RuntimeError):
    """Raised when another run appears to be active."""


class RunLock:
    def __init__(self, path: Path = LOCK_PATH) -> None:
        self.path = path

    def __enter__(self) -> "RunLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise AlreadyRunningError(f"Lock file already exists: {self.path}") from exc

        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(f"pid={os.getpid()}\n")
            file.write(f"started_at={datetime.now().astimezone().isoformat()}\n")
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


def build_scheduler_commands(
    config: SchedulerConfig = SchedulerConfig(),
    *,
    python_executable: Path | None = None,
    project_root: Path = PROJECT_ROOT,
) -> list[str]:
    python_executable = python_executable or Path(sys.executable)
    action = _ps_command(
        "New-ScheduledTaskAction",
        {
            "Execute": str(python_executable),
            "Argument": "-m worklog.cli run",
            "WorkingDirectory": str(project_root),
        },
    )
    daily_trigger = _ps_command(
        "New-ScheduledTaskTrigger",
        {"Daily": None, "At": config.daily_time},
    )
    logon_trigger = _ps_command("New-ScheduledTaskTrigger", {"AtLogOn": None})

    return [
        (
            f"$Action = {action}; "
            f"$Trigger = {daily_trigger}; "
            f"Register-ScheduledTask "
            f"-TaskName {_quote(config.task_name_daily)} "
            f"-Action $Action -Trigger $Trigger "
            f"-Description {_quote('Upload Desktop worklog to Notion daily')} "
            f"-Force"
        ),
        (
            f"$Action = {action}; "
            f"$Trigger = {logon_trigger}; "
            f"Register-ScheduledTask "
            f"-TaskName {_quote(config.task_name_logon)} "
            f"-Action $Action -Trigger $Trigger "
            f"-Description {_quote('Upload pending Desktop worklog to Notion at logon')} "
            f"-Force"
        ),
    ]


def register_scheduled_tasks(
    config: SchedulerConfig = SchedulerConfig(),
    *,
    dry_run: bool = False,
) -> list[str]:
    commands = build_scheduler_commands(config)
    if dry_run:
        return commands

    for command in commands:
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ],
            check=True,
        )
    return commands


def _ps_command(command: str, args: dict[str, str | None]) -> str:
    parts = [command]
    for name, value in args.items():
        parts.append(f"-{name}")
        if value is not None:
            parts.append(_quote(value))
    return " ".join(parts)


def _quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
