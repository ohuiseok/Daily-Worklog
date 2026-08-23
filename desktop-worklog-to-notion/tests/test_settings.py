from __future__ import annotations

from worklog.settings import UserSettings, load_user_settings, save_user_settings


def test_missing_user_settings_returns_defaults(tmp_path):
    settings = load_user_settings(tmp_path / "missing.json")

    assert settings.notion_token == ""
    assert settings.notion_database_id == ""
    assert settings.root_paths == ["%USERPROFILE%/Desktop"]
    assert settings.is_ready_for_upload is False


def test_save_and_load_user_settings(tmp_path):
    path = tmp_path / "settings.json"
    original = UserSettings(
        notion_token="ntn_test",
        notion_database_id="data_source_id",
        project_name="My Worklog",
        root_paths=["%USERPROFILE%/Desktop"],
    )

    saved_path = save_user_settings(original, path)
    loaded = load_user_settings(path)

    assert saved_path == path
    assert loaded == original
    assert loaded.is_ready_for_upload is True
