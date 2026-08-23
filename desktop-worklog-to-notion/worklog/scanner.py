"""Filesystem scanner for configured worklog roots."""

from __future__ import annotations

import fnmatch
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


ProgressCallback = Callable[[str, int, int, int], None]


@dataclass(frozen=True)
class ScanConfig:
    max_file_size_kb: int = 1024
    max_scanned_files: int = 20000
    max_scan_seconds: int = 180
    exclude_dirs: tuple[str, ...] = ()
    exclude_extensions: tuple[str, ...] = ()
    exclude_name_patterns: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ScanConfig":
        data = data or {}
        return cls(
            max_file_size_kb=int(data.get("max_file_size_kb", 1024)),
            max_scanned_files=int(data.get("max_scanned_files", 20000)),
            max_scan_seconds=int(data.get("max_scan_seconds", 180)),
            exclude_dirs=tuple(str(item) for item in data.get("exclude_dirs", [])),
            exclude_extensions=tuple(
                _normalize_extension(str(item))
                for item in data.get("exclude_extensions", [])
            ),
            exclude_name_patterns=tuple(
                str(item) for item in data.get("exclude_name_patterns", [])
            ),
        )


@dataclass(frozen=True)
class ScannedFile:
    root: Path
    path: Path
    relative_path: str
    name: str
    extension: str
    size_bytes: int
    modified_at: str


@dataclass(frozen=True)
class SkippedPath:
    path: Path
    reason: str


@dataclass
class ScanResult:
    files: list[ScannedFile] = field(default_factory=list)
    skipped: list[SkippedPath] = field(default_factory=list)
    stopped_reason: str | None = None


def scan_roots(
    roots: list[Path],
    config: ScanConfig,
    progress: ProgressCallback | None = None,
) -> ScanResult:
    result = ScanResult()
    started_at = time.monotonic()
    dirs_seen = 0

    for root in roots:
        if result.stopped_reason:
            break
        if not root.exists():
            result.skipped.append(SkippedPath(path=root, reason="root_missing"))
            continue
        if not root.is_dir():
            result.skipped.append(SkippedPath(path=root, reason="root_not_directory"))
            continue

        dirs_seen = _scan_root(
            root=root,
            config=config,
            result=result,
            started_at=started_at,
            dirs_seen=dirs_seen,
            progress=progress,
        )

    return result


def _scan_root(
    root: Path,
    config: ScanConfig,
    result: ScanResult,
    started_at: float,
    dirs_seen: int,
    progress: ProgressCallback | None,
) -> int:
    stack = [root]

    while stack:
        if _should_stop_scan(config, result, started_at):
            break

        current = stack.pop()
        dirs_seen += 1
        _emit_progress(progress, "scan", dirs_seen, len(result.files), len(result.skipped))

        try:
            children = list(current.iterdir())
        except OSError as exc:
            result.skipped.append(
                SkippedPath(path=current, reason=f"read_error:{exc.__class__.__name__}")
            )
            continue

        for child in children:
            try:
                if child.is_dir():
                    if _is_excluded_dir(child, config):
                        result.skipped.append(
                            SkippedPath(path=child, reason="excluded_dir")
                        )
                        continue
                    stack.append(child)
                    continue

                if not child.is_file():
                    result.skipped.append(
                        SkippedPath(path=child, reason="not_regular_file")
                    )
                    continue

                skip_reason = _file_skip_reason(child, config)
                if skip_reason:
                    result.skipped.append(SkippedPath(path=child, reason=skip_reason))
                    continue

                scanned = _to_scanned_file(root=root, path=child)
                result.files.append(scanned)
                _emit_progress(
                    progress,
                    "scan",
                    dirs_seen,
                    len(result.files),
                    len(result.skipped),
                )
            except OSError as exc:
                result.skipped.append(
                    SkippedPath(path=child, reason=f"stat_error:{exc.__class__.__name__}")
                )
                _emit_progress(
                    progress,
                    "scan",
                    dirs_seen,
                    len(result.files),
                    len(result.skipped),
                )

            if _should_stop_scan(config, result, started_at):
                break

    return dirs_seen


def _to_scanned_file(root: Path, path: Path) -> ScannedFile:
    stat = path.stat()
    modified_at = datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat()
    relative_path = path.relative_to(root).as_posix()

    return ScannedFile(
        root=root,
        path=path,
        relative_path=relative_path,
        name=path.name,
        extension=_normalize_extension(path.suffix),
        size_bytes=stat.st_size,
        modified_at=modified_at,
    )


def _file_skip_reason(path: Path, config: ScanConfig) -> str | None:
    if _matches_name_pattern(path.name, config.exclude_name_patterns):
        return "excluded_name_pattern"

    if _normalize_extension(path.suffix) in config.exclude_extensions:
        return "excluded_extension"

    max_bytes = config.max_file_size_kb * 1024
    try:
        if path.stat().st_size > max_bytes:
            return "file_too_large"
    except OSError as exc:
        return f"stat_error:{exc.__class__.__name__}"

    return None


def _is_excluded_dir(path: Path, config: ScanConfig) -> bool:
    lowered_name = path.name.lower()
    return any(lowered_name == excluded.lower() for excluded in config.exclude_dirs)


def _matches_name_pattern(name: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)


def _normalize_extension(extension: str) -> str:
    if not extension:
        return ""
    return extension.lower() if extension.startswith(".") else f".{extension.lower()}"


def _should_stop_scan(
    config: ScanConfig,
    result: ScanResult,
    started_at: float,
) -> bool:
    if config.max_scanned_files > 0 and len(result.files) >= config.max_scanned_files:
        result.stopped_reason = "max_scanned_files_reached"
        return True

    if config.max_scan_seconds > 0 and time.monotonic() - started_at >= config.max_scan_seconds:
        result.stopped_reason = "max_scan_seconds_reached"
        return True

    return False


def _emit_progress(
    progress: ProgressCallback | None,
    stage: str,
    dirs_seen: int,
    files_seen: int,
    skipped_seen: int,
) -> None:
    if progress is None:
        return
    is_first_event = dirs_seen == 1 and files_seen == 0 and skipped_seen == 0
    if is_first_event or (files_seen > 0 and files_seen % 500 == 0) or dirs_seen % 200 == 0:
        progress(stage, dirs_seen, files_seen, skipped_seen)
