"""Path expansion helpers for user-configured paths."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from worklog.config import PROJECT_ROOT


@dataclass(frozen=True)
class ResolvedPath:
    raw: str
    path: Path
    exists: bool
    warning: str | None = None


def expand_config_path(path_value: str, base_dir: Path = PROJECT_ROOT) -> Path:
    """Expand environment, user, and relative path syntax."""
    expanded = os.path.expandvars(path_value)
    expanded = _expand_windows_percent_vars(expanded)
    expanded = os.path.expanduser(expanded)

    path = Path(expanded)
    if not path.is_absolute():
        path = base_dir / path

    return path.resolve()


def resolve_config_paths(
    path_values: list[str], base_dir: Path = PROJECT_ROOT
) -> list[ResolvedPath]:
    """Resolve configured paths and attach non-fatal existence warnings."""
    resolved_paths: list[ResolvedPath] = []

    for raw in path_values:
        path = expand_config_path(raw, base_dir=base_dir)
        exists = path.exists()
        warning = None if exists else "Path does not exist and will be skipped."
        resolved_paths.append(
            ResolvedPath(raw=raw, path=path, exists=exists, warning=warning)
        )

    return resolved_paths


def _expand_windows_percent_vars(path_value: str) -> str:
    """Expand Windows %NAME% variables even when not running through cmd.exe."""
    result = path_value

    for key, value in os.environ.items():
        token = f"%{key}%"
        if token.lower() in result.lower():
            result = _replace_case_insensitive(result, token, value)

    return result


def _replace_case_insensitive(value: str, old: str, new: str) -> str:
    start = 0
    lowered_value = value.lower()
    lowered_old = old.lower()
    pieces: list[str] = []

    while True:
        index = lowered_value.find(lowered_old, start)
        if index == -1:
            pieces.append(value[start:])
            break

        pieces.append(value[start:index])
        pieces.append(new)
        start = index + len(old)

    return "".join(pieces)
