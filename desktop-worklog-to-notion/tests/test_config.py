from __future__ import annotations

import pytest

from worklog.config import load_config
from worklog.settings import UserSettings, save_user_settings


def test_load_config_uses_env_values(monkeypatch):
    monkeypatch.setenv("NOTION_TOKEN", "ntn_test")
    monkeypatch.setenv("NOTION_DATABASE_ID", "data_source_id")
    monkeypatch.setenv("NOTION_SOURCE", "Desktop")
    monkeypatch.setenv("WORKLOG_PROJECT_NAME", "My Worklog")
    monkeypatch.setenv(
        "WORKLOG_ROOT_PATHS",
        "%USERPROFILE%/Desktop;%USERPROFILE%/Documents",
    )
    monkeypatch.setenv("WORKLOG_MAX_FILE_SIZE_KB", "2048")
    monkeypatch.setenv("WORKLOG_MAX_SCANNED_FILES", "123")
    monkeypatch.setenv("WORKLOG_MAX_SCAN_SECONDS", "45")
    monkeypatch.setenv("WORKLOG_MAX_ANALYSIS_FILES", "67")
    monkeypatch.setenv("WORKLOG_HASH_FILE_CONTENT", "true")
    monkeypatch.setenv("WORKLOG_GIT_AUTO_AUTHOR", "false")
    monkeypatch.setenv("WORKLOG_GIT_AUTHOR_EMAILS", "me@example.com;work@example.com")
    monkeypatch.setenv("WORKLOG_GIT_AUTHOR_NAMES", "me;work")
    monkeypatch.setenv("WORKLOG_EXCLUDE_DIRS", ".git;node_modules")
    monkeypatch.setenv("WORKLOG_EXCLUDE_EXTENSIONS", ".png;.zip")
    monkeypatch.setenv("WORKLOG_EXCLUDE_NAME_PATTERNS", "~$*;Screenshot*")

    config = load_config(env_path=None)

    assert config["project_name"] == "My Worklog"
    assert config["root_paths"] == [
        "%USERPROFILE%/Desktop",
        "%USERPROFILE%/Documents",
    ]
    assert config["notion"] == {
        "token": "ntn_test",
        "database_id": "data_source_id",
        "source": "Desktop",
    }
    assert config["scan"]["max_file_size_kb"] == 2048
    assert config["scan"]["max_scanned_files"] == 123
    assert config["scan"]["max_scan_seconds"] == 45
    assert config["scan"]["max_analysis_files"] == 67
    assert config["scan"]["hash_file_content"] is True
    assert config["scan"]["exclude_dirs"] == [".git", "node_modules"]
    assert config["scan"]["exclude_extensions"] == [".png", ".zip"]
    assert config["scan"]["exclude_name_patterns"] == ["~$*", "Screenshot*"]
    assert config["git"]["auto_author"] is False
    assert config["git"]["author_emails"] == ["me@example.com", "work@example.com"]
    assert config["git"]["author_names"] == ["me", "work"]


def test_load_config_defaults_to_desktop(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    for name in [
        "NOTION_DATABASE_ID",
        "NOTION_SOURCE",
        "WORKLOG_PROJECT_NAME",
        "WORKLOG_ROOT_PATHS",
        "WORKLOG_GIT_AUTO_AUTHOR",
        "WORKLOG_GIT_AUTHOR_EMAILS",
        "WORKLOG_GIT_AUTHOR_NAMES",
    ]:
        monkeypatch.delenv(name, raising=False)

    config = load_config(env_path=None)

    assert config["project_name"] == "Desktop Worklog"
    assert config["root_paths"] == ["%USERPROFILE%/Desktop"]
    assert config["notion"]["database_id"] == "NOTION_DATABASE_ID"
    assert config["notion"]["token"] == ""
    assert config["notion"]["source"] == "Desktop"
    assert config["git"]["auto_author"] is True
    assert config["git"]["author_emails"] == []
    assert config["git"]["author_names"] == []


def test_load_config_rejects_invalid_integer(monkeypatch):
    monkeypatch.setenv("WORKLOG_MAX_FILE_SIZE_KB", "large")

    with pytest.raises(ValueError, match="WORKLOG_MAX_FILE_SIZE_KB"):
        load_config(env_path=None)


def test_load_config_uses_user_settings_when_env_is_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.delenv("NOTION_TOKEN", raising=False)
    monkeypatch.delenv("NOTION_DATABASE_ID", raising=False)
    monkeypatch.delenv("WORKLOG_PROJECT_NAME", raising=False)
    monkeypatch.delenv("WORKLOG_ROOT_PATHS", raising=False)
    save_user_settings(
        UserSettings(
            notion_token="ntn_from_settings",
            notion_database_id="settings_data_source",
            project_name="Settings Worklog",
            root_paths=["%USERPROFILE%/Desktop"],
        )
    )

    config = load_config(env_path=None)

    assert config["notion"]["token"] == "ntn_from_settings"
    assert config["notion"]["database_id"] == "settings_data_source"
    assert config["project_name"] == "Settings Worklog"
