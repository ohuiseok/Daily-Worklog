"""Uninstall helpers for the Windows exe distribution."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from worklog.app_paths import install_root, user_settings_path
from worklog.startup import startup_shortcut_path


@dataclass(frozen=True)
class UninstallPlan:
    shortcut_path: Path
    install_root: Path
    settings_path: Path
    remove_settings: bool = True


@dataclass(frozen=True)
class UninstallResult:
    removed: list[Path] = field(default_factory=list)
    missing: list[Path] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return not self.failed


def build_uninstall_plan(
    *,
    shortcut_path: Path | None = None,
    install_root_path: Path | None = None,
    settings_path: Path | None = None,
    remove_settings: bool = True,
) -> UninstallPlan:
    return UninstallPlan(
        shortcut_path=shortcut_path or startup_shortcut_path(),
        install_root=install_root_path or install_root(),
        settings_path=settings_path or user_settings_path(),
        remove_settings=remove_settings,
    )


def uninstall(plan: UninstallPlan | None = None) -> UninstallResult:
    plan = plan or build_uninstall_plan()
    removed: list[Path] = []
    missing: list[Path] = []
    failed: list[str] = []

    _remove_file(plan.shortcut_path, removed, missing, failed)
    if plan.remove_settings:
        _remove_file(plan.settings_path, removed, missing, failed)
        _remove_empty_parents(plan.settings_path.parent, stop_at=plan.settings_path.parent.parent)
    _remove_tree(plan.install_root, removed, missing, failed)

    return UninstallResult(
        removed=removed,
        missing=missing,
        failed=failed,
    )


def _remove_file(
    path: Path,
    removed: list[Path],
    missing: list[Path],
    failed: list[str],
) -> None:
    try:
        path.unlink()
        removed.append(path)
    except FileNotFoundError:
        missing.append(path)
    except OSError as exc:
        failed.append(f"{path}: {exc}")


def _remove_tree(
    path: Path,
    removed: list[Path],
    missing: list[Path],
    failed: list[str],
) -> None:
    if not path.exists():
        missing.append(path)
        return
    try:
        shutil.rmtree(path)
        removed.append(path)
    except OSError as exc:
        failed.append(f"{path}: {exc}")


def _remove_empty_parents(path: Path, *, stop_at: Path) -> None:
    current = path
    stop = stop_at.resolve()
    while current.exists() and current.resolve() != stop:
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent
