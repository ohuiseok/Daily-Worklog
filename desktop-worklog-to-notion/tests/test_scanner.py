from __future__ import annotations

from worklog.scanner import ScanConfig, scan_roots


def test_scan_collects_allowed_file(tmp_path):
    root = tmp_path / "DesktopLike"
    root.mkdir()
    (root / "a.md").write_text("hello", encoding="utf-8")

    result = scan_roots([root], ScanConfig())

    assert [file.relative_path for file in result.files] == ["a.md"]
    assert result.files[0].extension == ".md"
    assert result.files[0].size_bytes == 5


def test_scan_excludes_extension(tmp_path):
    root = tmp_path / "DesktopLike"
    root.mkdir()
    (root / "a.md").write_text("hello", encoding="utf-8")
    (root / "b.log").write_text("skip", encoding="utf-8")
    config = ScanConfig(exclude_extensions=(".log",))

    result = scan_roots([root], config)

    assert [file.relative_path for file in result.files] == ["a.md"]
    assert [(item.path.name, item.reason) for item in result.skipped] == [
        ("b.log", "excluded_extension")
    ]


def test_scan_excludes_directory(tmp_path):
    root = tmp_path / "DesktopLike"
    ignored = root / "node_modules"
    ignored.mkdir(parents=True)
    (ignored / "package.json").write_text("{}", encoding="utf-8")
    (root / "keep.txt").write_text("keep", encoding="utf-8")
    config = ScanConfig(exclude_dirs=("node_modules",))

    result = scan_roots([root], config)

    assert [file.relative_path for file in result.files] == ["keep.txt"]
    assert result.skipped[0].path.name == "node_modules"
    assert result.skipped[0].reason == "excluded_dir"


def test_scan_excludes_name_pattern(tmp_path):
    root = tmp_path / "DesktopLike"
    root.mkdir()
    (root / "~$draft.xlsx").write_text("skip", encoding="utf-8")
    (root / "draft.xlsx").write_text("keep", encoding="utf-8")
    config = ScanConfig(exclude_name_patterns=("~$*",))

    result = scan_roots([root], config)

    assert [file.relative_path for file in result.files] == ["draft.xlsx"]
    assert result.skipped[0].reason == "excluded_name_pattern"


def test_scan_excludes_large_file(tmp_path):
    root = tmp_path / "DesktopLike"
    root.mkdir()
    (root / "large.txt").write_text("123456", encoding="utf-8")
    config = ScanConfig(max_file_size_kb=0)

    result = scan_roots([root], config)

    assert result.files == []
    assert result.skipped[0].reason == "file_too_large"


def test_scan_missing_root_is_non_fatal(tmp_path):
    missing = tmp_path / "missing"

    result = scan_roots([missing], ScanConfig())

    assert result.files == []
    assert result.skipped[0].path == missing
    assert result.skipped[0].reason == "root_missing"


def test_scan_stops_at_max_scanned_files(tmp_path):
    root = tmp_path / "DesktopLike"
    root.mkdir()
    for index in range(3):
        (root / f"{index}.txt").write_text("hello", encoding="utf-8")

    result = scan_roots([root], ScanConfig(max_scanned_files=2))

    assert len(result.files) == 2
    assert result.stopped_reason == "max_scanned_files_reached"


def test_scan_reports_progress(tmp_path):
    root = tmp_path / "DesktopLike"
    root.mkdir()
    (root / "a.md").write_text("hello", encoding="utf-8")
    calls = []

    scan_roots([root], ScanConfig(), progress=lambda *args: calls.append(args))

    assert calls
