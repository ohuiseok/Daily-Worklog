from __future__ import annotations

from datetime import datetime, timezone

from worklog.scanner import ScanConfig, scan_roots
from worklog.snapshot import (
    Snapshot,
    SnapshotFile,
    compare_snapshots,
    create_snapshot,
    load_snapshot,
    save_dated_snapshot,
    save_snapshot,
    sha256_file,
    metadata_fingerprint,
)


def test_sha256_file(tmp_path):
    path = tmp_path / "a.txt"
    path.write_text("hello", encoding="utf-8")

    assert (
        sha256_file(path)
        == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    )


def test_create_snapshot_includes_hash(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.md").write_text("hello", encoding="utf-8")
    scanned = scan_roots([root], ScanConfig()).files

    snapshot = create_snapshot(
        scanned,
        generated_at=datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc),
    )

    assert snapshot.generated_at == "2026-08-23T12:00:00+00:00"
    assert len(snapshot.files) == 1
    assert snapshot.files[0].path == "a.md"
    assert snapshot.files[0].sha256 == sha256_file(root / "a.md")


def test_create_snapshot_can_use_fast_metadata_fingerprint(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.md").write_text("hello", encoding="utf-8")
    scanned = scan_roots([root], ScanConfig()).files
    calls = []

    snapshot = create_snapshot(
        scanned,
        generated_at=datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc),
        hash_file_content=False,
        progress=lambda done, total: calls.append((done, total)),
    )

    assert snapshot.files[0].sha256 == metadata_fingerprint(scanned[0])
    assert calls == [(1, 1)]


def test_compare_first_snapshot_treats_all_as_new():
    current = Snapshot(
        generated_at="2026-08-23T12:00:00+00:00",
        files=[
            SnapshotFile(
                path="a.md",
                mtime="now",
                size=5,
                sha256="hash",
                extension=".md",
            )
        ],
    )

    diff = compare_snapshots(None, current)

    assert [file.path for file in diff.new_files] == ["a.md"]
    assert diff.modified_files == []
    assert diff.deleted_files == []


def test_compare_snapshots_classifies_changes():
    previous = Snapshot(
        generated_at="2026-08-22T12:00:00+00:00",
        files=[
            SnapshotFile("same.md", "old", 1, "same", ".md"),
            SnapshotFile("changed.md", "old", 1, "old_hash", ".md"),
            SnapshotFile("deleted.md", "old", 1, "deleted_hash", ".md"),
        ],
    )
    current = Snapshot(
        generated_at="2026-08-23T12:00:00+00:00",
        files=[
            SnapshotFile("same.md", "new", 1, "same", ".md"),
            SnapshotFile("changed.md", "new", 2, "new_hash", ".md"),
            SnapshotFile("new.md", "new", 1, "new_hash", ".md"),
        ],
    )

    diff = compare_snapshots(previous, current)

    assert [file.path for file in diff.new_files] == ["new.md"]
    assert [file.path for file in diff.modified_files] == ["changed.md"]
    assert [file.path for file in diff.deleted_files] == ["deleted.md"]


def test_save_and_load_snapshot(tmp_path):
    path = tmp_path / "latest_snapshot.json"
    snapshot = Snapshot(
        generated_at="2026-08-23T12:00:00+00:00",
        files=[SnapshotFile("a.md", "now", 5, "hash", ".md")],
    )

    save_snapshot(snapshot, path=path)

    assert load_snapshot(path) == snapshot


def test_save_dated_snapshot(tmp_path):
    snapshot = Snapshot(
        generated_at="2026-08-23T12:00:00+00:00",
        files=[],
    )

    path = save_dated_snapshot(snapshot, state_dir=tmp_path)

    assert path == tmp_path / "2026-08-23.json"
    assert load_snapshot(path) == snapshot
