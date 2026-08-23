from __future__ import annotations

from zipfile import ZipFile

from openpyxl import Workbook

from worklog.analyzers import (
    CsvAnalysis,
    ExcelAnalysis,
    TextAnalysis,
    analysis_summary,
    analysis_to_safe_dict,
    analyze_csv_file,
    analyze_docx_file,
    analyze_excel_file,
    analyze_file,
    analyze_files,
    analyze_text_file,
)
from worklog.scanner import ScanConfig, scan_roots


def test_analyze_text_file_returns_counts_without_body(tmp_path):
    path = tmp_path / "note.md"
    path.write_text("# Worklog Plan\nhello notion notion\n", encoding="utf-8")

    result = analyze_text_file(path)

    assert result.line_count == 2
    assert result.char_count == 37
    assert result.title_candidate == "Worklog Plan"
    assert "notion" in result.keyword_candidates
    assert "worklog" in result.keyword_candidates
    assert result.preview_lines == ["# Worklog Plan", "hello notion notion"]


def test_analyze_csv_file_returns_shape_and_columns(tmp_path):
    path = tmp_path / "data.csv"
    path.write_text("name,count\nalpha,1\nbeta,2\n", encoding="utf-8")

    result = analyze_csv_file(path)

    assert result == CsvAnalysis(
        row_count=2,
        column_count=2,
        columns=["name", "count"],
        encoding="utf-8-sig",
        sample_rows=[["alpha", "1"], ["beta", "2"]],
    )


def test_analyze_excel_file_returns_sheet_structure(tmp_path):
    path = tmp_path / "book.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Summary"
    sheet.append(["Name", "Count"])
    sheet.append(["alpha", 1])
    workbook.save(path)

    result = analyze_excel_file(path)

    assert isinstance(result, ExcelAnalysis)
    assert len(result.sheets) == 1
    assert result.sheets[0].name == "Summary"
    assert result.sheets[0].row_count == 2
    assert result.sheets[0].column_count == 2
    assert result.sheets[0].header_candidates == ["Name", "Count"]
    assert result.sheets[0].sample_rows == [["alpha", "1"]]


def test_analyze_docx_file_returns_text_preview(tmp_path):
    path = tmp_path / "daily-worklog-doc.docx"
    _write_docx(
        path,
        [
            "Daily Worklog docx preview",
            "DOCX 문서 내용도 Notion에 일부 표시된다.",
        ],
    )

    result = analyze_docx_file(path)

    assert result.line_count == 2
    assert result.preview_lines == [
        "Daily Worklog docx preview",
        "DOCX 문서 내용도 Notion에 일부 표시된다.",
    ]
    assert "docx" in result.keyword_candidates


def test_analyze_files_continues_after_error(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "ok.md").write_text("hello", encoding="utf-8")
    broken = root / "broken.xlsx"
    broken.write_text("not an excel file", encoding="utf-8")
    scanned_files = scan_roots([root], ScanConfig()).files

    results = analyze_files(scanned_files)

    by_path = {result.path: result for result in results}
    assert by_path["ok.md"].kind == "text"
    assert by_path["broken.xlsx"].kind == "error"
    assert by_path["broken.xlsx"].error is not None


def test_unsupported_file_is_reported(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "file.bin").write_bytes(b"binary")
    scanned_file = scan_roots([root], ScanConfig()).files[0]

    result = analyze_file(scanned_file)

    assert result.kind == "unsupported"
    assert result.data is None


def test_analysis_can_disable_content_preview(tmp_path):
    path = tmp_path / "note.md"
    path.write_text("secret raw sentence that should not appear", encoding="utf-8")

    analysis = analyze_file(
        scan_roots([tmp_path], ScanConfig()).files[0],
        include_content_preview=False,
    )
    safe = analysis_to_safe_dict(analysis)

    assert "secret raw sentence" not in str(safe)
    assert safe["data"]["line_count"] == 1
    assert safe["data"]["char_count"] == 42
    assert safe["data"]["preview_lines"] == []


def test_analysis_summary_counts_kinds(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "note.md").write_text("hello", encoding="utf-8")
    (root / "data.csv").write_text("a\n1\n", encoding="utf-8")
    (root / "file.bin").write_bytes(b"binary")

    analyses = analyze_files(scan_roots([root], ScanConfig()).files)

    assert analysis_summary(analyses) == {
        "text": 1,
        "csv": 1,
        "excel": 0,
        "unsupported": 1,
        "error": 0,
    }


def test_analyze_files_can_limit_expensive_analysis(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    for index in range(3):
        (root / f"{index}.md").write_text("hello", encoding="utf-8")
    scanned_files = scan_roots([root], ScanConfig()).files
    calls = []

    analyses = analyze_files(
        scanned_files,
        max_files=2,
        progress=lambda done, total: calls.append((done, total)),
    )

    assert len([analysis for analysis in analyses if analysis.kind == "text"]) == 2
    assert analyses[-1].error == "analysis_limit_reached"
    assert calls[-1] == (2, 2)


def _write_docx(path, paragraphs):
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        + "".join(
            f"<w:p><w:r><w:t>{paragraph}</w:t></w:r></w:p>"
            for paragraph in paragraphs
        )
        + "</w:body></w:document>"
    )
    with ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "")
        archive.writestr("word/document.xml", document_xml)
