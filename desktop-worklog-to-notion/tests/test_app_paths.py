from __future__ import annotations

from worklog import app_paths


def test_appdata_paths_use_windows_env(monkeypatch, tmp_path):
    local = tmp_path / "Local"
    roaming = tmp_path / "Roaming"
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("APPDATA", str(roaming))

    assert app_paths.install_root() == local / "DesktopWorklogToNotion"
    assert app_paths.installed_app_dir() == local / "DesktopWorklogToNotion" / "app"
    assert (
        app_paths.installed_exe_path()
        == local / "DesktopWorklogToNotion" / "app" / "desktop-worklog-to-notion.exe"
    )
    assert app_paths.runtime_state_dir() == local / "DesktopWorklogToNotion" / "state"
    assert app_paths.runtime_logs_dir() == local / "DesktopWorklogToNotion" / "logs"
    assert (
        app_paths.user_settings_path()
        == roaming / "DesktopWorklogToNotion" / "settings.json"
    )


def test_ensure_installed_exe_skips_non_frozen(tmp_path):
    target = tmp_path / "app" / "desktop-worklog-to-notion.exe"

    result = app_paths.ensure_installed_exe(target_exe=target, frozen=False)

    assert result.frozen is False
    assert result.copied is False
    assert not target.exists()


def test_ensure_installed_exe_copies_frozen_exe(tmp_path):
    source = tmp_path / "download" / "desktop-worklog-to-notion.exe"
    target = tmp_path / "Local" / "DesktopWorklogToNotion" / "app" / source.name
    source.parent.mkdir()
    source.write_bytes(b"exe-content")

    result = app_paths.ensure_installed_exe(
        source_exe=source,
        target_exe=target,
        frozen=True,
    )

    assert result.frozen is True
    assert result.copied is True
    assert result.already_installed is False
    assert target.read_bytes() == b"exe-content"


def test_ensure_installed_exe_detects_installed_target(tmp_path):
    target = tmp_path / "Local" / "DesktopWorklogToNotion" / "app" / "app.exe"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"same")

    result = app_paths.ensure_installed_exe(
        source_exe=target,
        target_exe=target,
        frozen=True,
    )

    assert result.copied is False
    assert result.already_installed is True
