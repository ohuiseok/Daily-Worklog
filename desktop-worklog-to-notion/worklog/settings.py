"""User settings stored outside the downloaded project folder."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from worklog.app_paths import user_settings_path


@dataclass(frozen=True)
class UserSettings:
    notion_token: str = ""
    notion_database_id: str = ""
    notion_source: str = "Desktop"
    project_name: str = "Desktop Worklog"
    root_paths: list[str] = field(default_factory=lambda: ["%USERPROFILE%/Desktop"])

    @property
    def is_ready_for_upload(self) -> bool:
        return bool(self.notion_token.strip() and self.notion_database_id.strip())


def load_user_settings(path: Path | None = None) -> UserSettings:
    settings_path = path or user_settings_path()
    if not settings_path.exists():
        return UserSettings()

    with settings_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError("Settings root must be a JSON object.")

    return UserSettings(
        notion_token=str(data.get("notion_token") or ""),
        notion_database_id=str(data.get("notion_database_id") or ""),
        notion_source=str(data.get("notion_source") or "Desktop"),
        project_name=str(data.get("project_name") or "Desktop Worklog"),
        root_paths=_list_of_strings(
            data.get("root_paths"),
            default=["%USERPROFILE%/Desktop"],
        ),
    )


def save_user_settings(settings: UserSettings, path: Path | None = None) -> Path:
    settings_path = path or user_settings_path()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    with settings_path.open("w", encoding="utf-8") as file:
        json.dump(asdict(settings), file, ensure_ascii=False, indent=2)
        file.write("\n")
    return settings_path


def prompt_user_settings(path: Path | None = None) -> UserSettings:
    current = load_user_settings(path)
    print("Desktop Worklog to Notion first setup")
    print("Press Enter to keep the value shown in brackets.")

    token = _prompt_secretish("Notion token", current.notion_token)
    database_id = _prompt_value("Notion database/data source ID", current.notion_database_id)
    project_name = _prompt_value("Project name", current.project_name)
    root_path = _prompt_value(
        "Folder to collect",
        current.root_paths[0] if current.root_paths else "%USERPROFILE%/Desktop",
    )

    updated = UserSettings(
        notion_token=token,
        notion_database_id=database_id,
        notion_source=current.notion_source or "Desktop",
        project_name=project_name or "Desktop Worklog",
        root_paths=[root_path or "%USERPROFILE%/Desktop"],
    )
    save_user_settings(updated, path)
    return updated


def settings_to_config_overrides(settings: UserSettings) -> dict[str, Any]:
    return {
        "project_name": settings.project_name,
        "root_paths": settings.root_paths,
        "notion": {
            "token": settings.notion_token,
            "database_id": settings.notion_database_id,
            "source": settings.notion_source,
        },
    }


def _prompt_value(label: str, current: str) -> str:
    suffix = f" [{current}]" if current else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or current


def _prompt_secretish(label: str, current: str) -> str:
    display = "saved" if current else ""
    suffix = f" [{display}]" if display else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or current


def _list_of_strings(value: object, *, default: list[str]) -> list[str]:
    if not isinstance(value, list):
        return list(default)
    result = [str(item).strip() for item in value if str(item).strip()]
    return result or list(default)
