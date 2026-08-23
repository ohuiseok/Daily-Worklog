from __future__ import annotations

from pathlib import Path

import pytest

from worklog.scheduler import (
    AlreadyRunningError,
    RunLock,
    SchedulerConfig,
    build_scheduler_commands,
)


def test_build_scheduler_commands_include_daily_and_logon_tasks(tmp_path):
    commands = build_scheduler_commands(
        SchedulerConfig(daily_time="23:30"),
        python_executable=Path("C:/Python/python.exe"),
        project_root=tmp_path,
    )

    rendered = "\n".join(commands)

    assert "DesktopWorklogToNotionDaily" in rendered
    assert "DesktopWorklogToNotionLogon" in rendered
    assert "New-ScheduledTaskTrigger -Daily -At '23:30'" in rendered
    assert "New-ScheduledTaskTrigger -AtLogOn" in rendered
    assert "-m worklog.cli run" in rendered
    assert str(tmp_path) in rendered


def test_run_lock_creates_and_removes_lock_file(tmp_path):
    lock_path = tmp_path / "run.lock"

    with RunLock(lock_path):
        assert lock_path.exists()

    assert not lock_path.exists()


def test_run_lock_rejects_existing_lock_file(tmp_path):
    lock_path = tmp_path / "run.lock"
    lock_path.write_text("pid=1\n", encoding="utf-8")

    with pytest.raises(AlreadyRunningError):
        with RunLock(lock_path):
            pass
