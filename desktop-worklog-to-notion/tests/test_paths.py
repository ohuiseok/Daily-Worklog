from __future__ import annotations

from pathlib import Path

from worklog.paths import expand_config_path, resolve_config_paths


def test_expands_percent_userprofile(monkeypatch, tmp_path):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    result = expand_config_path("%USERPROFILE%/Desktop")

    assert result == (tmp_path / "Desktop").resolve()


def test_expands_braced_userprofile(monkeypatch, tmp_path):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    result = expand_config_path("${USERPROFILE}/Desktop")

    assert result == (tmp_path / "Desktop").resolve()


def test_expands_home(monkeypatch, tmp_path):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    result = expand_config_path("~/Desktop")

    assert result == (tmp_path / "Desktop").resolve()


def test_relative_path_uses_base_dir(tmp_path):
    base_dir = tmp_path / "project"
    base_dir.mkdir()

    result = expand_config_path("local-folder", base_dir=base_dir)

    assert result == (base_dir / "local-folder").resolve()


def test_resolve_config_paths_marks_missing_path(tmp_path):
    missing_path = tmp_path / "missing"

    result = resolve_config_paths([str(missing_path)])

    assert len(result) == 1
    assert result[0].path == missing_path.resolve()
    assert result[0].exists is False
    assert result[0].warning == "Path does not exist and will be skipped."


def test_handles_korean_path(tmp_path):
    korean_path = tmp_path / "한글 경로"
    korean_path.mkdir()

    result = resolve_config_paths([str(korean_path)])

    assert result[0].path == korean_path.resolve()
    assert result[0].exists is True
    assert result[0].warning is None
