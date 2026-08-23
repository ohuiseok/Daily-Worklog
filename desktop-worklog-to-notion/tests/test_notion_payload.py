from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from worklog.analyzers import CsvAnalysis, ExcelAnalysis, ExcelSheetAnalysis, FileAnalysis, TextAnalysis
from worklog.git_collector import GitCommit, GitRepoInfo
from worklog.notion_client import (
    DesktopPayloadInput,
    EnsureSchemaResult,
    NotionClient,
    NotionConfigError,
    apply_title_property_name,
    assert_payload_has_no_raw_content,
    build_desktop_notion_payload,
    find_title_property_name,
    validate_database_id,
)
from worklog.snapshot import SnapshotDiff, SnapshotFile
from worklog.summarizer import DesktopSummary


def _payload(summary_bullets=None):
    summary = DesktopSummary(
        bullets=summary_bullets or ["Git 커밋 1개를 기록했다."],
        keywords=["git", "document"],
        status="Success",
    )
    return build_desktop_notion_payload(
        DesktopPayloadInput(
            database_id="database_id",
            project_name="Desktop Worklog",
            worklog_date=date(2026, 8, 23),
            source="Desktop",
            summary=summary,
            diff=SnapshotDiff(
                new_files=[
                    SnapshotFile("docs/plan.md", "now", 5, "hash", ".md")
                ],
                modified_files=[
                    SnapshotFile("src/app.py", "now", 10, "hash2", ".py")
                ],
            ),
            analyses=[FileAnalysis(path="docs/plan.md", kind="text")],
            git_infos=[
                GitRepoInfo(
                    path=Path("repo"),
                    branch="main",
                    commits=[
                        GitCommit(
                            hash="abc123",
                            authored_at="2026-08-23T10:00:00+09:00",
                            message="add desktop scanner",
                            changed_files=["worklog/analyzers.py"],
                            diff_preview=[
                                "@@ -1 +1 @@",
                                "+preview_lines: list[str] = field(default_factory=list)",
                            ],
                        )
                    ],
                )
            ],
            skipped_count=2,
        )
    )


def test_build_desktop_notion_payload_properties():
    payload = _payload()

    assert payload["parent"] == {"database_id": "database_id"}
    assert (
        payload["properties"]["Name"]["title"][0]["text"]["content"]
        == "2026-08-23 Desktop Worklog"
    )
    assert payload["properties"]["Date"]["date"]["start"] == "2026-08-23"
    assert payload["properties"]["Source"]["select"]["name"] == "Desktop"
    assert payload["properties"]["Commit Count"]["number"] == 1
    assert payload["properties"]["Modified Files"]["number"] == 1
    assert "Keywords" not in payload["properties"]
    assert "Written Chunks" not in payload["properties"]
    assert "Main Domains" not in payload["properties"]


def test_build_desktop_notion_payload_children():
    payload = _payload()
    rendered = str(payload["children"])

    assert "오늘 한 일" in rendered
    assert "근거 지표" in rendered
    assert "변경 파일 상세" in rendered
    assert "Git" in rendered
    assert "commit abc123: add desktop scanner" in rendered
    assert "worklog/analyzers.py" in rendered
    assert "+preview_lines" in rendered


def test_payload_places_file_details_before_git_section():
    summary = DesktopSummary(bullets=["테스트"], keywords=[], status="Success")
    payload = build_desktop_notion_payload(
        DesktopPayloadInput(
            database_id="database_id",
            project_name="Desktop Worklog",
            worklog_date=date(2026, 8, 23),
            source="Desktop",
            summary=summary,
            diff=SnapshotDiff(
                modified_files=[SnapshotFile("docs/plan.md", "now", 10, "hash", ".md")]
            ),
            analyses=[
                FileAnalysis(
                    path="docs/plan.md",
                    kind="text",
                    data=TextAnalysis(
                        line_count=1,
                        char_count=10,
                        preview_lines=["오늘 계획 수정"],
                    ),
                )
            ],
            git_infos=[
                GitRepoInfo(
                    path=Path("repo"),
                    branch="main",
                    status=[" M app.py"],
                )
            ],
            skipped_count=0,
        )
    )
    children = payload["children"]
    contents = [
        block[block["type"]]["rich_text"][0]["text"]["content"]
        for block in children
    ]

    file_detail_index = next(
        index
        for index, content in enumerate(contents)
        if "docs/plan.md: 텍스트" in content
    )
    git_heading_index = contents.index("Git")

    assert file_detail_index < git_heading_index


def test_payload_separates_outside_git_code_from_document_details():
    summary = DesktopSummary(bullets=["테스트"], keywords=[], status="Success")
    payload = build_desktop_notion_payload(
        DesktopPayloadInput(
            database_id="database_id",
            project_name="Desktop Worklog",
            worklog_date=date(2026, 8, 23),
            source="Desktop",
            summary=summary,
            diff=SnapshotDiff(
                modified_files=[
                    SnapshotFile("repo/app.py", "now", 10, "hash1", ".py"),
                    SnapshotFile("scripts/local_tool.py", "now", 10, "hash2", ".py"),
                    SnapshotFile("notes/today.md", "now", 10, "hash3", ".md"),
                ]
            ),
            analyses=[
                FileAnalysis(
                    path="repo/app.py",
                    kind="text",
                    data=TextAnalysis(
                        line_count=1,
                        char_count=10,
                        preview_lines=["print('git code')"],
                    ),
                ),
                FileAnalysis(
                    path="scripts/local_tool.py",
                    kind="text",
                    data=TextAnalysis(
                        line_count=1,
                        char_count=10,
                        preview_lines=["print('outside git')"],
                    ),
                ),
                FileAnalysis(
                    path="notes/today.md",
                    kind="text",
                    data=TextAnalysis(
                        line_count=1,
                        char_count=10,
                        preview_lines=["오늘 메모"],
                    ),
                ),
            ],
            git_infos=[
                GitRepoInfo(
                    path=Path("repo"),
                    branch="main",
                    status=[" M app.py"],
                    unstaged_diff_preview=["@@ -1 +1 @@", "+print('git diff')"],
                )
            ],
            skipped_count=0,
        )
    )
    rendered = str(payload["children"])

    assert "notes/today.md: 텍스트" in rendered
    assert "Git 밖 코드 파일" in rendered
    assert "scripts/local_tool.py: 텍스트" in rendered
    assert "print('outside git')" in rendered
    assert "repo/app.py: 텍스트" not in rendered
    assert "print('git code')" not in rendered
    assert "+print('git diff')" in rendered


def test_payload_skips_empty_git_repo_lines():
    summary = DesktopSummary(bullets=["테스트"], keywords=[], status="Success")
    payload = build_desktop_notion_payload(
        DesktopPayloadInput(
            database_id="database_id",
            project_name="Desktop Worklog",
            worklog_date=date(2026, 8, 23),
            source="Desktop",
            summary=summary,
            diff=SnapshotDiff(),
            analyses=[],
            git_infos=[
                GitRepoInfo(path=Path("empty"), branch="main"),
                GitRepoInfo(path=Path("dirty"), branch="main", status=[" M note.md"]),
            ],
            skipped_count=0,
        )
    )
    rendered = str(payload["children"])

    assert "empty: branch=main, commits=0, status=0" not in rendered
    assert "dirty: branch=main, commits=0, status=1" in rendered
    assert "관련 저장소: 1개" in rendered


def test_payload_includes_uncommitted_git_diff_preview():
    summary = DesktopSummary(bullets=["테스트"], keywords=[], status="Success")
    payload = build_desktop_notion_payload(
        DesktopPayloadInput(
            database_id="database_id",
            project_name="Desktop Worklog",
            worklog_date=date(2026, 8, 23),
            source="Desktop",
            summary=summary,
            diff=SnapshotDiff(),
            analyses=[],
            git_infos=[
                GitRepoInfo(
                    path=Path("repo"),
                    branch="main",
                    status=[" M app.py"],
                    unstaged_diff_preview=[
                        "@@ -1 +1 @@",
                        "-old code",
                        "+new code",
                    ],
                ),
            ],
            skipped_count=0,
        )
    )
    rendered = str(payload["children"])

    assert "repo 미커밋 변경:  M app.py" in rendered
    assert "+new code" in rendered


def test_payload_summarizes_deleted_git_files_without_diff_body():
    summary = DesktopSummary(bullets=["테스트"], keywords=[], status="Success")
    payload = build_desktop_notion_payload(
        DesktopPayloadInput(
            database_id="database_id",
            project_name="Desktop Worklog",
            worklog_date=date(2026, 8, 23),
            source="Desktop",
            summary=summary,
            diff=SnapshotDiff(),
            analyses=[],
            git_infos=[
                GitRepoInfo(
                    path=Path("repo"),
                    branch="main",
                    status=[" D old.py", " M app.py"],
                    deleted_files=["old.py"],
                    unstaged_diff_preview=["@@ -1 +1 @@", "+new code"],
                ),
            ],
            skipped_count=0,
        )
    )
    rendered = str(payload["children"])

    assert "repo 삭제 파일: old.py" in rendered
    assert "repo 삭제 파일 diff 본문은 생략" in rendered
    assert "repo 미커밋 변경:  M app.py" in rendered
    assert "+new code" in rendered


def test_payload_includes_file_content_previews():
    summary = DesktopSummary(bullets=["테스트"], keywords=[], status="Success")
    payload = build_desktop_notion_payload(
        DesktopPayloadInput(
            database_id="database_id",
            project_name="Desktop Worklog",
            worklog_date=date(2026, 8, 23),
            source="Desktop",
            summary=summary,
            diff=SnapshotDiff(
                new_files=[
                    SnapshotFile("note.md", "now", 30, "hash1", ".md"),
                    SnapshotFile("tasks.csv", "now", 40, "hash2", ".csv"),
                    SnapshotFile("report.xlsx", "now", 50, "hash3", ".xlsx"),
                ]
            ),
            analyses=[
                FileAnalysis(
                    path="note.md",
                    kind="text",
                    data=TextAnalysis(
                        line_count=2,
                        char_count=30,
                        title_candidate="회의 정리",
                        preview_lines=["오늘 회의에서 API 스키마를 정리했다."],
                    ),
                ),
                FileAnalysis(
                    path="tasks.csv",
                    kind="csv",
                    data=CsvAnalysis(
                        row_count=1,
                        column_count=2,
                        columns=["name", "status"],
                        sample_rows=[["문서 정리", "done"]],
                    ),
                ),
                FileAnalysis(
                    path="report.xlsx",
                    kind="excel",
                    data=ExcelAnalysis(
                        sheets=[
                            ExcelSheetAnalysis(
                                name="Summary",
                                row_count=2,
                                column_count=2,
                                header_candidates=["항목", "값"],
                                sample_rows=[["커밋", "2"]],
                            )
                        ]
                    ),
                ),
            ],
            git_infos=[],
            skipped_count=0,
        )
    )
    rendered = str(payload["children"])

    assert "오늘 회의에서 API 스키마를 정리했다." in rendered
    assert "문서 정리" in rendered
    assert "커밋" in rendered


def test_payload_does_not_include_raw_file_content():
    payload = _payload(["파일 변경 1개를 감지했다."])

    assert "my password is 1234" not in str(payload)
    assert_payload_has_no_raw_content(payload, ["my password is 1234"])


def test_apply_title_property_name_supports_korean_title_property():
    payload = _payload()

    updated = apply_title_property_name(payload, "이름")

    assert "Name" not in updated["properties"]
    assert (
        updated["properties"]["이름"]["title"][0]["text"]["content"]
        == "2026-08-23 Desktop Worklog"
    )


def test_find_title_property_name_detects_localized_title():
    assert (
        find_title_property_name(
            {
                "이름": {"type": "title", "title": {}},
                "Date": {"type": "date", "date": {}},
            }
        )
        == "이름"
    )


def test_assert_payload_has_no_raw_content_raises():
    payload = _payload(["raw secret text"])

    with pytest.raises(ValueError):
        assert_payload_has_no_raw_content(payload, ["raw secret text"])


def test_validate_database_id_rejects_placeholder():
    with pytest.raises(NotionConfigError):
        validate_database_id("YOUR_NOTION_DATABASE_ID")


def test_notion_client_creates_page_when_no_existing_page():
    session = FakeSession(
        [
            FakeResponse(200, {"properties": _complete_schema_properties()}),
            FakeResponse(200, {"results": []}),
            FakeResponse(200, {"id": "page_1", "url": "https://notion.so/page_1"}),
        ]
    )
    client = NotionClient("ntn_test", session=session)

    result = client.upsert_desktop_worklog(
        _payload(),
        worklog_date=date(2026, 8, 23),
        source="Desktop",
        project_name="Desktop Worklog",
    )

    assert result.page_id == "page_1"
    assert result.created is True
    assert [call["method"] for call in session.calls] == ["GET", "POST", "POST"]
    assert session.calls[0]["url"].endswith("/data_sources/database_id")
    assert session.calls[1]["url"].endswith("/data_sources/database_id/query")
    assert session.calls[2]["url"].endswith("/pages")
    assert session.calls[2]["json"]["parent"] == {
        "type": "data_source_id",
        "data_source_id": "database_id",
    }


def test_notion_client_splits_large_children_on_create():
    session = FakeSession(
        [
            FakeResponse(200, {"properties": _complete_schema_properties()}),
            FakeResponse(200, {"results": []}),
            FakeResponse(200, {"id": "page_1", "url": "https://notion.so/page_1"}),
            FakeResponse(200, {"results": []}),
        ]
    )
    client = NotionClient("ntn_test", session=session)
    payload = _payload()
    payload["children"] = [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": f"line {index}"}}]
            },
        }
        for index in range(105)
    ]

    result = client.upsert_desktop_worklog(
        payload,
        worklog_date=date(2026, 8, 23),
        source="Desktop",
        project_name="Desktop Worklog",
    )

    assert result.created is True
    assert [call["method"] for call in session.calls] == [
        "GET",
        "POST",
        "POST",
        "PATCH",
    ]
    assert len(session.calls[2]["json"]["children"]) == 100
    assert len(session.calls[3]["json"]["children"]) == 5


def test_notion_client_updates_existing_page_and_appends_blocks():
    session = FakeSession(
        [
            FakeResponse(200, {"properties": _complete_schema_properties()}),
            FakeResponse(
                200,
                {"results": [{"id": "page_1", "url": "https://notion.so/page_1"}]},
            ),
            FakeResponse(200, {"id": "page_1"}),
            FakeResponse(200, {"results": []}),
        ]
    )
    client = NotionClient("ntn_test", session=session)

    result = client.upsert_desktop_worklog(
        _payload(),
        worklog_date=date(2026, 8, 23),
        source="Desktop",
        project_name="Desktop Worklog",
    )

    assert result.page_id == "page_1"
    assert result.created is False
    assert [call["method"] for call in session.calls] == ["GET", "POST", "PATCH", "PATCH"]
    assert session.calls[2]["url"].endswith("/pages/page_1")
    assert session.calls[3]["url"].endswith("/blocks/page_1/children")


def test_notion_client_ensures_missing_database_properties():
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "properties": {
                        "Name": {"type": "title", "title": {}},
                        "Date": {"type": "date", "date": {}},
                    }
                },
            ),
            FakeResponse(200, {"properties": _complete_schema_properties()}),
        ]
    )
    client = NotionClient("ntn_test", session=session)

    result = client.ensure_database_schema("database_id")

    assert isinstance(result, EnsureSchemaResult)
    assert result.title_property_name == "Name"
    assert result.target_type == "data_source"
    assert result.data_source_id == "database_id"
    assert "Source" in result.added
    assert session.calls[1]["method"] == "PATCH"
    assert session.calls[1]["url"].endswith("/data_sources/database_id")
    assert "Source" in session.calls[1]["json"]["properties"]


def test_notion_client_rejects_incompatible_schema():
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "properties": {
                        "Name": {"type": "title", "title": {}},
                        "Date": {"type": "rich_text", "rich_text": {}},
                    }
                },
            )
        ]
    )
    client = NotionClient("ntn_test", session=session)

    with pytest.raises(Exception, match="incompatible properties"):
        client.ensure_database_schema("database_id")


def test_notion_client_resolves_database_id_to_first_data_source():
    session = FakeSession(
        [
            FakeResponse(404, {"message": "data source not found"}),
            FakeResponse(
                200,
                {"data_sources": [{"id": "data_source_1", "name": "Daily Worklog"}]},
            ),
            FakeResponse(200, {"properties": _complete_schema_properties("이름")}),
        ]
    )
    client = NotionClient("ntn_test", session=session)

    result = client.ensure_database_schema("database_id")

    assert result.target_type == "database"
    assert result.target_id == "database_id"
    assert result.data_source_id == "data_source_1"
    assert result.title_property_name == "이름"
    assert session.calls[0]["url"].endswith("/data_sources/database_id")
    assert session.calls[1]["url"].endswith("/databases/database_id")
    assert session.calls[2]["url"].endswith("/data_sources/data_source_1")


def test_notion_client_explains_inaccessible_database_or_data_source():
    session = FakeSession(
        [
            FakeResponse(404, {"message": "data source not found"}),
            FakeResponse(404, {"message": "database not found"}),
        ]
    )
    client = NotionClient("ntn_test", session=session)

    with pytest.raises(Exception, match="shared with this integration"):
        client.ensure_database_schema("missing_id")


def test_notion_client_searches_accessible_data_sources():
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "results": [
                        {
                            "id": "data_source_1",
                            "object": "data_source",
                            "title": [{"plain_text": "Daily Worklog"}],
                            "url": "https://notion.so/source",
                        }
                    ]
                },
            )
        ]
    )
    client = NotionClient("ntn_test", session=session)

    results = client.search_accessible_targets("Daily")

    assert results == [
        {
            "id": "data_source_1",
            "object": "data_source",
            "title": "Daily Worklog",
            "url": "https://notion.so/source",
        }
    ]
    assert session.calls[0]["url"].endswith("/search")
    assert session.calls[0]["json"]["filter"] == {
        "property": "object",
        "value": "data_source",
    }


def test_notion_client_reuses_localized_title_property_on_create():
    session = FakeSession(
        [
            FakeResponse(200, {"properties": _complete_schema_properties("이름")}),
            FakeResponse(200, {"results": []}),
            FakeResponse(200, {"id": "page_1", "url": "https://notion.so/page_1"}),
        ]
    )
    client = NotionClient("ntn_test", session=session)

    result = client.upsert_desktop_worklog(
        _payload(),
        worklog_date=date(2026, 8, 23),
        source="Desktop",
        project_name="Desktop Worklog",
    )

    create_payload = session.calls[2]["json"]
    assert result.created is True
    assert "Name" not in create_payload["properties"]
    assert "이름" in create_payload["properties"]


def test_notion_client_retries_rate_limit(monkeypatch):
    sleep_calls = []
    monkeypatch.setattr("worklog.notion_client.time.sleep", sleep_calls.append)
    session = FakeSession(
        [
            FakeResponse(429, {"error": "rate limited"}, headers={"Retry-After": "1"}),
            FakeResponse(200, {"results": []}),
        ]
    )
    client = NotionClient("ntn_test", session=session)

    result = client.find_existing_page(
        "database_id",
        worklog_date=date(2026, 8, 23),
        source="Desktop",
        project_name="Desktop Worklog",
    )

    assert result is None
    assert sleep_calls == [1.0]
    assert len(session.calls) == 2


class FakeResponse:
    def __init__(self, status_code, payload, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.text = str(payload)

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, headers, json, timeout):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        return self.responses.pop(0)


def _complete_schema_properties(title_property_name="Name"):
    return {
        title_property_name: {"type": "title", "title": {}},
        "Date": {"type": "date", "date": {}},
        "Source": {
            "type": "select",
            "select": {
                "options": [
                    {"name": "Browser", "color": "blue"},
                    {"name": "Desktop", "color": "green"},
                ]
            },
        },
        "Project": {"type": "rich_text", "rich_text": {}},
        "Status": {
            "type": "select",
            "select": {
                "options": [
                    {"name": "Success", "color": "green"},
                    {"name": "Failed", "color": "red"},
                    {"name": "Skipped", "color": "gray"},
                ]
            },
        },
        "Summary": {"type": "rich_text", "rich_text": {}},
        "Written Chunks": {"type": "number", "number": {"format": "number"}},
        "Main Domains": {"type": "multi_select", "multi_select": {"options": []}},
        "Commit Count": {"type": "number", "number": {"format": "number"}},
        "Modified Files": {"type": "number", "number": {"format": "number"}},
    }
