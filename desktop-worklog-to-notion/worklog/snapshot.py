"""Snapshot creation and comparison helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from worklog.config import STATE_DIR
from worklog.scanner import ScannedFile


SnapshotProgressCallback = Callable[[int, int], None]


LATEST_SNAPSHOT_PATH = STATE_DIR / "latest_snapshot.json"


@dataclass(frozen=True)
class SnapshotFile:
    path: str
    mtime: str
    size: int
    sha256: str
    extension: str


@dataclass(frozen=True)
class Snapshot:
    generated_at: str
    files: list[SnapshotFile]


@dataclass(frozen=True)
class SnapshotDiff:
    new_files: list[SnapshotFile] = field(default_factory=list)
    modified_files: list[SnapshotFile] = field(default_factory=list)
    deleted_files: list[SnapshotFile] = field(default_factory=list)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_snapshot(
    scanned_files: list[ScannedFile],
    generated_at: datetime | None = None,
    *,
    hash_file_content: bool = True,
    progress: SnapshotProgressCallback | None = None,
) -> Snapshot:
    timestamp = (generated_at or datetime.now().astimezone()).isoformat()
    sorted_files = sorted(scanned_files, key=lambda item: item.relative_path.lower())
    snapshot_files: list[SnapshotFile] = []
    total = len(sorted_files)
    for index, file in enumerate(sorted_files, start=1):
        snapshot_files.append(
            SnapshotFile(
                path=file.relative_path,
                mtime=file.modified_at,
                size=file.size_bytes,
                sha256=(
                    sha256_file(file.path)
                    if hash_file_content
                    else metadata_fingerprint(file)
                ),
                extension=file.extension,
            )
        )
        if progress is not None and (index == 1 or index == total or index % 500 == 0):
            progress(index, total)
    return Snapshot(generated_at=timestamp, files=snapshot_files)


def metadata_fingerprint(file: ScannedFile) -> str:
    return f"metadata:{file.modified_at}:{file.size_bytes}"


def compare_snapshots(previous: Snapshot | None, current: Snapshot) -> SnapshotDiff:
    if previous is None:
        return SnapshotDiff(new_files=current.files)

    previous_by_path = {file.path: file for file in previous.files}
    current_by_path = {file.path: file for file in current.files}

    new_files = [
        file for path, file in current_by_path.items() if path not in previous_by_path
    ]
    modified_files = [
        file
        for path, file in current_by_path.items()
        if path in previous_by_path and file.sha256 != previous_by_path[path].sha256
    ]
    deleted_files = [
        file for path, file in previous_by_path.items() if path not in current_by_path
    ]

    return SnapshotDiff(
        new_files=sorted(new_files, key=lambda item: item.path.lower()),
        modified_files=sorted(modified_files, key=lambda item: item.path.lower()),
        deleted_files=sorted(deleted_files, key=lambda item: item.path.lower()),
    )


def load_snapshot(path: Path = LATEST_SNAPSHOT_PATH) -> Snapshot | None:
    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError("Snapshot root must be a JSON object.")

    files = [
        SnapshotFile(
            path=str(item["path"]),
            mtime=str(item["mtime"]),
            size=int(item["size"]),
            sha256=str(item["sha256"]),
            extension=str(item.get("extension", "")),
        )
        for item in data.get("files", [])
    ]
    return Snapshot(generated_at=str(data["generated_at"]), files=files)


def save_snapshot(snapshot: Snapshot, path: Path = LATEST_SNAPSHOT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(asdict(snapshot), file, ensure_ascii=False, indent=2)
        file.write("\n")


def save_dated_snapshot(snapshot: Snapshot, state_dir: Path = STATE_DIR) -> Path:
    date_part = snapshot.generated_at[:10]
    path = state_dir / f"{date_part}.json"
    save_snapshot(snapshot, path=path)
    return path
