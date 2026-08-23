from __future__ import annotations

from pathlib import Path

from worklog import startup


def test_startup_folder_uses_roaming_appdata(monkeypatch, tmp_path):
    roaming = tmp_path / "Roaming"
    monkeypatch.setenv("APPDATA", str(roaming))

    assert startup.startup_folder() == (
        roaming / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    )
    assert startup.startup_shortcut_path() == (
        startup.startup_folder() / "Desktop Worklog to Notion.lnk"
    )


def test_shortcut_command_points_to_target():
    shortcut = Path("C:/Users/me/AppData/Roaming/Startup/Desktop Worklog to Notion.lnk")
    target = Path("C:/Users/me/AppData/Local/DesktopWorklogToNotion/app/app.exe")

    command = startup.shortcut_command(shortcut, target)

    assert "WScript.Shell" in command
    assert str(shortcut) in command
    assert str(target) in command
    assert str(target.parent) in command


def test_ensure_startup_shortcut_uses_creator(monkeypatch, tmp_path):
    calls = []

    def fake_create(shortcut_path, target_path):
        calls.append((shortcut_path, target_path))
        shortcut_path.write_text("shortcut", encoding="utf-8")

    monkeypatch.setattr(startup, "_create_shortcut", fake_create)
    shortcut = tmp_path / "Startup" / "Desktop Worklog to Notion.lnk"
    target = tmp_path / "app" / "desktop-worklog-to-notion.exe"

    result = startup.ensure_startup_shortcut(
        shortcut_path=shortcut,
        target_path=target,
    )

    assert calls == [(shortcut, target.resolve())]
    assert result.created is True
    assert result.shortcut_path == shortcut
    assert result.target_path == target.resolve()
