"""Notion payload builders for Desktop worklog entries."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

import requests

from worklog.analyzers import (
    CsvAnalysis,
    ExcelAnalysis,
    FileAnalysis,
    TextAnalysis,
    analysis_summary,
)
from worklog.git_collector import GitRepoInfo
from worklog.snapshot import SnapshotDiff
from worklog.summarizer import DesktopSummary

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2026-03-11"
MAX_NOTION_CHILDREN_PER_REQUEST = 100
MAX_DESKTOP_ANALYSIS_DETAIL_LINES = 80
MAX_DESKTOP_GIT_REPOS = 20
MAX_DESKTOP_COMMITS_PER_REPO = 20
MAX_DESKTOP_COMMIT_CHANGED_FILES = 80
MAX_DESKTOP_COMMIT_DIFF_LINES = 140
MAX_DESKTOP_STATUS_FILES = 80
MAX_DESKTOP_STAGED_DIFF_LINES = 180
MAX_DESKTOP_UNSTAGED_DIFF_LINES = 260
MAX_DESKTOP_PREVIEW_CHARS = 1200
MAX_DESKTOP_TABLE_PREVIEW_CHARS = 1200
MAX_DESKTOP_DELETED_FILES = 30
MAX_DESKTOP_OUTSIDE_GIT_CODE_FILES = 40
CODE_FILE_EXTENSIONS = {
    ".bat",
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".css",
    ".go",
    ".groovy",
    ".h",
    ".hpp",
    ".html",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".kt",
    ".kts",
    ".php",
    ".ps1",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".sql",
    ".swift",
    ".ts",
    ".tsx",
    ".vue",
    ".xml",
    ".yaml",
    ".yml",
}
NOISY_DETAIL_PATH_PATTERNS = (
    "*/.pytest_cache/*",
    "*/build/*",
    "*/dist/*",
    "*/.idea/*",
    "*/.gradle/*",
    "*/gradle/wrapper/*",
    "*/gradlew",
    "*/gradlew.bat",
    "*.spec",
)
PLACEHOLDER_DATABASE_IDS = {"", "YOUR_NOTION_DATABASE_ID", "NOTION_DATABASE_ID"}
DEFAULT_TITLE_PROPERTY_NAME = "Name"

REQUIRED_DATABASE_PROPERTIES: dict[str, dict[str, Any]] = {
    "Date": {"type": "date", "schema": {"date": {}}},
    "Source": {
        "type": "select",
        "schema": {
            "select": {
                "options": [
                    {"name": "Browser", "color": "blue"},
                    {"name": "Desktop", "color": "green"},
                ]
            }
        },
    },
    "Project": {"type": "rich_text", "schema": {"rich_text": {}}},
    "Status": {
        "type": "select",
        "schema": {
            "select": {
                "options": [
                    {"name": "Success", "color": "green"},
                    {"name": "Failed", "color": "red"},
                    {"name": "Skipped", "color": "gray"},
                ]
            }
        },
    },
    "Summary": {"type": "rich_text", "schema": {"rich_text": {}}},
    "Written Chunks": {
        "type": "number",
        "schema": {"number": {"format": "number"}},
    },
    "Main Domains": {
        "type": "multi_select",
        "schema": {"multi_select": {"options": []}},
    },
    "Commit Count": {
        "type": "number",
        "schema": {"number": {"format": "number"}},
    },
    "Modified Files": {
        "type": "number",
        "schema": {"number": {"format": "number"}},
    },
}


@dataclass(frozen=True)
class DesktopPayloadInput:
    database_id: str
    project_name: str
    worklog_date: date
    source: str
    summary: DesktopSummary
    diff: SnapshotDiff
    analyses: list[FileAnalysis]
    git_infos: list[GitRepoInfo]
    skipped_count: int = 0


@dataclass(frozen=True)
class UpsertResult:
    page_id: str
    created: bool
    url: str | None = None


@dataclass(frozen=True)
class EnsureSchemaResult:
    added: list[str]
    existing: list[str]
    incompatible: list[str]
    title_property_name: str = DEFAULT_TITLE_PROPERTY_NAME
    target_id: str = ""
    target_type: str = "data_source"
    data_source_id: str = ""


@dataclass(frozen=True)
class DataSourceTarget:
    input_id: str
    input_type: str
    data_source_id: str
    data_source: dict[str, Any]


class NotionConfigError(ValueError):
    """Raised when local Notion settings are not ready for upload."""


class NotionApiError(RuntimeError):
    """Raised when Notion returns an unsuccessful response."""


class NotionClient:
    def __init__(self, token: str, session: requests.Session | None = None) -> None:
        if not token:
            raise NotionConfigError("NOTION_TOKEN is required.")

        self.session = session or requests.Session()
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_VERSION,
        }

    def upsert_desktop_worklog(
        self,
        payload: dict[str, Any],
        *,
        worklog_date: date,
        source: str,
        project_name: str,
    ) -> UpsertResult:
        database_id = payload["parent"]["database_id"]
        validate_database_id(database_id)
        schema_result = self.ensure_database_schema(database_id)
        data_source_id = schema_result.data_source_id
        payload = apply_title_property_name(
            payload,
            schema_result.title_property_name,
        )

        existing_page = self.find_existing_page(
            data_source_id,
            worklog_date=worklog_date,
            source=source,
            project_name=project_name,
        )

        if existing_page is None:
            children = list(payload.get("children", []))
            create_payload = {
                **payload,
                "parent": {
                    "type": "data_source_id",
                    "data_source_id": data_source_id,
                },
                "children": children[:MAX_NOTION_CHILDREN_PER_REQUEST],
            }
            response = self._request(
                "POST",
                "/pages",
                json=create_payload,
            )
            page_id = response["id"]
            remaining_children = children[MAX_NOTION_CHILDREN_PER_REQUEST:]
            if remaining_children:
                self.append_blocks(page_id, remaining_children)
            return UpsertResult(
                page_id=page_id,
                created=True,
                url=response.get("url"),
            )

        page_id = existing_page["id"]
        self._request(
            "PATCH",
            f"/pages/{page_id}",
            json={"properties": payload["properties"]},
        )
        self.append_blocks(page_id, payload["children"])
        return UpsertResult(
            page_id=page_id,
            created=False,
            url=existing_page.get("url"),
        )

    def ensure_database_schema(self, database_id: str) -> EnsureSchemaResult:
        validate_database_id(database_id)
        target = self.resolve_data_source_target(database_id)
        properties = target.data_source.get("properties", {})
        if not isinstance(properties, dict):
            properties = {}

        title_property_name = find_title_property_name(properties)
        patch_properties: dict[str, Any] = {}
        added: list[str] = []
        existing: list[str] = [title_property_name]
        incompatible: list[str] = []

        for name, required in REQUIRED_DATABASE_PROPERTIES.items():
            current = properties.get(name)
            if not isinstance(current, dict):
                patch_properties[name] = required["schema"]
                added.append(name)
                continue

            if current.get("type") != required["type"]:
                incompatible.append(
                    f"{name}: expected {required['type']}, got {current.get('type')}"
                )
                continue

            existing.append(name)
            option_patch = _build_option_patch(current, required)
            if option_patch:
                patch_properties[name] = option_patch
                added.append(f"{name} options")

        if incompatible:
            raise NotionApiError(
                "Notion database schema has incompatible properties: "
                + ", ".join(incompatible)
            )

        if patch_properties:
            self._request(
                "PATCH",
                f"/data_sources/{target.data_source_id}",
                json={"properties": patch_properties},
            )

        return EnsureSchemaResult(
            added=added,
            existing=existing,
            incompatible=incompatible,
            title_property_name=title_property_name,
            target_id=target.input_id,
            target_type=target.input_type,
            data_source_id=target.data_source_id,
        )

    def resolve_data_source_target(self, notion_id: str) -> DataSourceTarget:
        validate_database_id(notion_id)
        data_source_lookup_error: str | None = None

        try:
            data_source = self._request("GET", f"/data_sources/{notion_id}")
        except NotionApiError as error:
            if not str(error).startswith("Notion API failed: 404"):
                raise
            data_source_lookup_error = str(error)
            data_source = None

        if data_source is not None:
            return DataSourceTarget(
                input_id=notion_id,
                input_type="data_source",
                data_source_id=notion_id,
                data_source=data_source,
            )

        try:
            database = self._request("GET", f"/databases/{notion_id}")
        except NotionApiError as error:
            if str(error).startswith("Notion API failed: 404"):
                details = [
                    "Could not access the Notion database/data source.",
                    "Check that the copied ID is correct and that the database is shared with this integration.",
                ]
                if data_source_lookup_error:
                    details.append(f"Data source lookup: {data_source_lookup_error}")
                details.append(f"Database lookup: {error}")
                raise NotionApiError(" ".join(details)) from error
            raise

        data_sources = database.get("data_sources", [])
        if not isinstance(data_sources, list):
            data_sources = []
        first_data_source = next(
            (
                item
                for item in data_sources
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            ),
            None,
        )
        if first_data_source is None:
            raise NotionApiError("Notion database has no data sources.")

        data_source_id = str(first_data_source["id"])
        return DataSourceTarget(
            input_id=notion_id,
            input_type="database",
            data_source_id=data_source_id,
            data_source=self._request("GET", f"/data_sources/{data_source_id}"),
        )

    def find_existing_page(
        self,
        data_source_id: str,
        *,
        worklog_date: date,
        source: str,
        project_name: str,
    ) -> dict[str, Any] | None:
        validate_database_id(data_source_id)
        body = {
            "filter": {
                "and": [
                    {"property": "Date", "date": {"equals": worklog_date.isoformat()}},
                    {"property": "Source", "select": {"equals": source}},
                    {"property": "Project", "rich_text": {"equals": project_name}},
                ]
            },
            "page_size": 1,
        }
        response = self._request("POST", f"/data_sources/{data_source_id}/query", json=body)
        results = response.get("results", [])
        return results[0] if results else None

    def search_accessible_targets(self, query: str = "") -> list[dict[str, Any]]:
        response = self._request(
            "POST",
            "/search",
            json={
                "query": query,
                "page_size": 20,
                "filter": {"property": "object", "value": "data_source"},
                "sort": {"direction": "descending", "timestamp": "last_edited_time"},
            },
        )
        results = response.get("results", [])
        if not isinstance(results, list):
            return []
        return [
            {
                "id": item.get("id", ""),
                "object": item.get("object", "unknown"),
                "title": _title_from_search_result(item),
                "url": item.get("url"),
            }
            for item in results
            if isinstance(item, dict)
        ]

    def append_blocks(self, page_id: str, blocks: list[dict[str, Any]]) -> None:
        for chunk in _chunks(blocks, MAX_NOTION_CHILDREN_PER_REQUEST):
            self._request(
                "PATCH",
                f"/blocks/{page_id}/children",
                json={"children": chunk},
            )

    def _request(
        self, method: str, path: str, json: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        url = f"{NOTION_API_BASE}{path}"
        for attempt in range(3):
            response = self.session.request(
                method,
                url,
                headers=self.headers,
                json=json,
                timeout=30,
            )
            if response.status_code == 429 and attempt < 2:
                retry_after = response.headers.get("Retry-After", "1")
                try:
                    sleep_seconds = max(float(retry_after), 1.0)
                except ValueError:
                    sleep_seconds = 1.0
                time.sleep(sleep_seconds)
                continue

            if response.status_code >= 400:
                raise NotionApiError(
                    f"Notion API failed: {response.status_code} {response.text}"
                )

            return response.json()

        raise NotionApiError("Notion API failed after retries.")

    def _request_or_none(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        on_not_found=None,
    ) -> dict[str, Any] | None:
        try:
            return self._request(method, path, json=json)
        except NotionApiError as error:
            if str(error).startswith("Notion API failed: 404"):
                if on_not_found is not None:
                    on_not_found(error)
                return None
            raise


def validate_database_id(database_id: str) -> None:
    if database_id in PLACEHOLDER_DATABASE_IDS:
        raise NotionConfigError(
            "Set NOTION_DATABASE_ID in .env before uploading."
        )


def build_desktop_notion_payload(input_data: DesktopPayloadInput) -> dict[str, Any]:
    """Build a Notion create/update payload without raw file content."""
    title = f"{input_data.worklog_date.isoformat()} {input_data.project_name}"
    commit_count = sum(len(info.commits) for info in input_data.git_infos)
    modified_count = len(input_data.diff.modified_files)
    changed_count = (
        len(input_data.diff.new_files)
        + len(input_data.diff.modified_files)
        + len(input_data.diff.deleted_files)
    )
    return {
        "parent": {"database_id": input_data.database_id},
        "properties": {
            DEFAULT_TITLE_PROPERTY_NAME: {"title": [_text(title)]},
            "Date": {"date": {"start": input_data.worklog_date.isoformat()}},
            "Source": {"select": {"name": input_data.source}},
            "Project": {"rich_text": [_text(input_data.project_name)]},
            "Status": {"select": {"name": input_data.summary.status}},
            "Summary": {"rich_text": [_text(_short_summary(input_data.summary))]},
            "Commit Count": {"number": commit_count},
            "Modified Files": {"number": modified_count},
        },
        "children": build_desktop_blocks(
            input_data.summary,
            input_data.diff,
            input_data.analyses,
            input_data.git_infos,
            changed_count=changed_count,
            skipped_count=input_data.skipped_count,
        ),
    }


def apply_title_property_name(
    payload: dict[str, Any],
    title_property_name: str,
) -> dict[str, Any]:
    """Return a payload whose title property matches the actual Notion database."""
    if title_property_name == DEFAULT_TITLE_PROPERTY_NAME:
        return payload

    properties = payload.get("properties")
    if not isinstance(properties, dict):
        return payload

    title_property = properties.pop(DEFAULT_TITLE_PROPERTY_NAME, None)
    if title_property is not None:
        properties[title_property_name] = title_property
    return payload


def find_title_property_name(properties: dict[str, Any]) -> str:
    for name, property_schema in properties.items():
        if isinstance(property_schema, dict) and property_schema.get("type") == "title":
            return name

    raise NotionApiError(
        "Notion database schema does not include a title property. "
        "Create the database in Notion first, then share it with this integration."
    )


def _title_from_search_result(item: dict[str, Any]) -> str:
    title = item.get("title")
    if not isinstance(title, list):
        return "(untitled)"

    parts = [
        part.get("plain_text", "")
        for part in title
        if isinstance(part, dict) and isinstance(part.get("plain_text"), str)
    ]
    text = "".join(parts).strip()
    return text or "(untitled)"


def build_desktop_blocks(
    summary: DesktopSummary,
    diff: SnapshotDiff,
    analyses: list[FileAnalysis],
    git_infos: list[GitRepoInfo],
    changed_count: int,
    skipped_count: int,
) -> list[dict[str, Any]]:
    changed_paths = {
        file.path for file in [*diff.new_files, *diff.modified_files]
    }
    changed_analyses = [
        analysis for analysis in analyses if analysis.path in changed_paths
    ]
    work_git_infos = _work_git_infos(git_infos)
    diagnostic_git_infos = [info for info in git_infos if info.error]
    git_paths = _git_touched_paths(work_git_infos)
    document_analyses = [
        analysis
        for analysis in changed_analyses
        if not _is_code_file_path(analysis.path)
    ]
    outside_git_code_analyses = [
        analysis
        for analysis in changed_analyses
        if _is_code_file_path(analysis.path)
        and _normalize_path(analysis.path) not in git_paths
    ]
    document_counts = analysis_summary(document_analyses)
    blocks: list[dict[str, Any]] = [
        _heading("오늘 한 일"),
        *[_bulleted_item(bullet) for bullet in summary.bullets],
        _heading("근거 지표"),
        _bulleted_item(f"전체 파일 변경: {changed_count}개"),
        _bulleted_item(f"새 파일: {len(diff.new_files)}개"),
        _bulleted_item(f"수정 파일: {len(diff.modified_files)}개"),
        _bulleted_item(f"삭제 파일: {len(diff.deleted_files)}개"),
        _bulleted_item(f"제외/스킵된 항목: {skipped_count}개"),
        _heading("변경 파일 상세"),
        _bulleted_item(f"내용 확인된 문서/메모/표 파일: {len(document_analyses)}개"),
        _bulleted_item(
            "타입: "
            f"텍스트/문서 {document_counts['text']}개, "
            f"CSV {document_counts['csv']}개, "
            f"Excel {document_counts['excel']}개"
        ),
    ]

    for detail in _analysis_detail_lines(document_analyses, diff):
        blocks.append(_bulleted_item(detail))

    if outside_git_code_analyses:
        blocks.append(_heading("Git 밖 코드 파일"))
        blocks.append(
            _bulleted_item(
                f"Git 저장소 밖 코드 파일: {len(outside_git_code_analyses)}개"
            )
        )
        for detail in _analysis_detail_lines(
            outside_git_code_analyses,
            diff,
            limit=MAX_DESKTOP_OUTSIDE_GIT_CODE_FILES,
        ):
            blocks.append(_bulleted_item(detail))

    blocks.extend(
        [
        _heading("Git"),
        _bulleted_item(f"관련 저장소: {len(work_git_infos)}개"),
        _bulleted_item(f"커밋: {sum(len(info.commits) for info in git_infos)}개"),
        _bulleted_item(
            f"미커밋 변경 파일: {sum(len(info.status) for info in work_git_infos)}개"
        ),
        ]
    )

    for repo_info in work_git_infos[:MAX_DESKTOP_GIT_REPOS]:
        repo_name = repo_info.path.name
        blocks.append(
            _bulleted_item(
                f"{repo_name}: branch={repo_info.branch or 'unknown'}, "
                f"commits={len(repo_info.commits)}, status={len(repo_info.status)}"
            )
        )
        for commit in repo_info.commits[:MAX_DESKTOP_COMMITS_PER_REPO]:
            blocks.append(_bulleted_item(f"commit {commit.hash}: {commit.message}"))
            if commit.changed_files:
                blocks.append(
                    _bulleted_item(
                        f"commit {commit.hash} 변경 파일: "
                    f"{', '.join(commit.changed_files[:MAX_DESKTOP_COMMIT_CHANGED_FILES])}"
                )
            )
            for line in commit.diff_preview[:MAX_DESKTOP_COMMIT_DIFF_LINES]:
                blocks.append(_bulleted_item(f"commit {commit.hash} diff: {line}"))

        if repo_info.deleted_files:
            blocks.append(
                _bulleted_item(
                    f"{repo_name} 삭제 파일: "
                    f"{_format_deleted_files(repo_info.deleted_files)}"
                )
            )
            blocks.append(_bulleted_item(f"{repo_name} 삭제 파일 diff 본문은 생략"))

        if repo_info.status:
            visible_status = _non_deleted_status_lines(repo_info.status)
            if visible_status:
                blocks.append(
                    _bulleted_item(
                        f"{repo_name} 미커밋 변경: "
                        f"{', '.join(visible_status[:MAX_DESKTOP_STATUS_FILES])}"
                    )
                )
            elif not repo_info.deleted_files:
                blocks.append(
                    _bulleted_item(
                        f"{repo_name} 미커밋 변경: "
                        f"{', '.join(repo_info.status[:MAX_DESKTOP_STATUS_FILES])}"
                    )
                )
        if repo_info.staged_diff_preview or repo_info.unstaged_diff_preview:
            blocks.append(
                _bulleted_item(f"{repo_name} 수정/추가 diff")
            )
            for line in [
                *repo_info.staged_diff_preview[:MAX_DESKTOP_STAGED_DIFF_LINES],
                *repo_info.unstaged_diff_preview[:MAX_DESKTOP_UNSTAGED_DIFF_LINES],
            ]:
                blocks.append(_bulleted_item(f"{repo_name} diff: {line}"))

    diagnostics = _diagnostic_lines(
        analyses=analyses,
        diagnostic_git_infos=diagnostic_git_infos,
        total_analysis_counts=analysis_summary(analyses),
    )
    if diagnostics:
        blocks.append(_heading("진단 정보"))
        for line in diagnostics:
            blocks.append(_bulleted_item(line))

    return blocks


def _work_git_infos(git_infos: list[GitRepoInfo]) -> list[GitRepoInfo]:
    return [
        info
        for info in git_infos
        if not info.error and (info.commits or info.status)
    ]


def _git_touched_paths(git_infos: list[GitRepoInfo]) -> set[str]:
    paths: set[str] = set()
    for info in git_infos:
        repo_prefix = _normalize_path(str(info.path))
        repo_name = info.path.name
        for status_line in info.status:
            for path in _paths_from_git_status_line(status_line):
                _add_git_path_candidates(paths, repo_prefix, repo_name, path)
        for deleted_file in info.deleted_files:
            _add_git_path_candidates(paths, repo_prefix, repo_name, deleted_file)
        for commit in info.commits:
            for changed_file in commit.changed_files:
                _add_git_path_candidates(paths, repo_prefix, repo_name, changed_file)
    return paths


def _add_git_path_candidates(
    paths: set[str],
    repo_prefix: str,
    repo_name: str,
    path: str,
) -> None:
    normalized = _normalize_path(path)
    if not normalized:
        return
    paths.add(normalized)
    if repo_name:
        paths.add(_normalize_path(f"{repo_name}/{normalized}"))
    if repo_prefix:
        paths.add(_normalize_path(f"{repo_prefix}/{normalized}"))


def _paths_from_git_status_line(line: str) -> list[str]:
    value = line[3:].strip() if len(line) > 3 else line.strip()
    if " -> " in value:
        return [part.strip() for part in value.split(" -> ", 1)]
    return [value] if value else []


def _non_deleted_status_lines(status: list[str]) -> list[str]:
    return [line for line in status if not _is_deleted_status_line(line)]


def _is_deleted_status_line(line: str) -> bool:
    return len(line) >= 2 and "D" in line[:2]


def _format_deleted_files(deleted_files: list[str]) -> str:
    visible = deleted_files[:MAX_DESKTOP_DELETED_FILES]
    rendered = ", ".join(visible)
    remaining = len(deleted_files) - len(visible)
    if remaining > 0:
        rendered += f" 외 {remaining}개"
    return rendered


def _diagnostic_lines(
    *,
    analyses: list[FileAnalysis],
    diagnostic_git_infos: list[GitRepoInfo],
    total_analysis_counts: dict[str, int],
) -> list[str]:
    lines: list[str] = []
    if diagnostic_git_infos:
        lines.append(f"Git 수집 오류 저장소: {len(diagnostic_git_infos)}개")
        for info in diagnostic_git_infos[:10]:
            lines.append(f"{info.path.name}: Git 정보를 읽지 못해 건너뜀")
    if total_analysis_counts["error"]:
        lines.append(f"분석 실패 파일: {total_analysis_counts['error']}개")
    if analyses:
        lines.append(
            "전체 스캔 중 분석 가능 파일: "
            f"텍스트/문서 {total_analysis_counts['text']}개, "
            f"CSV {total_analysis_counts['csv']}개, "
            f"Excel {total_analysis_counts['excel']}개"
        )
    return lines


def _analysis_detail_lines(
    analyses: list[FileAnalysis],
    diff: SnapshotDiff,
    *,
    limit: int = MAX_DESKTOP_ANALYSIS_DETAIL_LINES,
) -> list[str]:
    analyses_by_path = {analysis.path: analysis for analysis in analyses}
    lines: list[str] = []
    changed_files = [
        file
        for file in [*diff.new_files, *diff.modified_files]
        if not _is_noisy_detail_path(file.path)
    ]
    for file in changed_files:
        if len(lines) >= limit:
            break
        analysis = analyses_by_path.get(file.path)
        if analysis is None:
            continue
        detail = _analysis_detail_line(analysis)
        if detail:
            lines.append(detail)
    return lines


def _analysis_detail_line(analysis: FileAnalysis) -> str | None:
    data = analysis.data
    if isinstance(data, TextAnalysis):
        parts = [f"{analysis.path}: 텍스트 {data.line_count}줄, {data.char_count}자"]
        if data.title_candidate:
            parts.append(f"제목 후보 `{data.title_candidate}`")
        if data.keyword_candidates:
            parts.append(f"주요 단어 {', '.join(data.keyword_candidates[:5])}")
        if data.preview_lines:
            parts.append(f"내용 일부 `{_inline_preview(data.preview_lines)}`")
        return ", ".join(parts)

    if isinstance(data, CsvAnalysis):
        parts = [
            f"{analysis.path}: CSV {data.row_count}행 x {data.column_count}열"
        ]
        if data.columns:
            parts.append(f"컬럼 {', '.join(data.columns[:6])}")
        if data.sample_rows:
            parts.append(f"샘플 `{_table_preview(data.sample_rows)}`")
        return ", ".join(parts)

    if isinstance(data, ExcelAnalysis):
        sheet_parts = []
        for sheet in data.sheets[:3]:
            sheet_detail = f"{sheet.name} {sheet.row_count}행 x {sheet.column_count}열"
            if sheet.header_candidates:
                sheet_detail += f" ({', '.join(sheet.header_candidates[:5])})"
            if sheet.sample_rows:
                sheet_detail += f" 샘플 `{_table_preview(sheet.sample_rows)}`"
            sheet_parts.append(sheet_detail)
        if sheet_parts:
            return f"{analysis.path}: Excel " + "; ".join(sheet_parts)

    return None


def _is_noisy_detail_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return any(fnmatch(normalized, pattern) for pattern in NOISY_DETAIL_PATH_PATTERNS)


def _is_code_file_path(path: str) -> bool:
    return Path(path).suffix.lower() in CODE_FILE_EXTENSIONS


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip().lstrip("./")


def _inline_preview(
    lines: list[str],
    *,
    max_length: int = MAX_DESKTOP_PREVIEW_CHARS,
) -> str:
    preview = " / ".join(line.strip() for line in lines if line.strip())
    return _clip_preview(preview, max_length)


def _table_preview(
    rows: list[list[str]],
    *,
    max_length: int = MAX_DESKTOP_TABLE_PREVIEW_CHARS,
) -> str:
    preview = " | ".join(
        ", ".join(cell for cell in row if cell)
        for row in rows
        if any(cell for cell in row)
    )
    return _clip_preview(preview, max_length)


def _clip_preview(value: str, max_length: int) -> str:
    value = value.replace("\n", " ").replace("\r", " ").strip()
    if len(value) <= max_length:
        return value
    return value[: max_length - 1].rstrip() + "…"

def assert_payload_has_no_raw_content(
    payload: dict[str, Any], forbidden_values: list[str]
) -> None:
    rendered = str(payload)
    for value in forbidden_values:
        if value and value in rendered:
            raise ValueError(f"Notion payload contains forbidden raw content: {value}")


def payload_to_safe_json_dict(payload: dict[str, Any]) -> dict[str, Any]:
    """Return payload as-is; named to make dry-run intent explicit."""
    return payload


def _chunks(items: list[dict[str, Any]], size: int):
    for index in range(0, len(items), size):
        yield items[index : index + size]


def _build_option_patch(
    current: dict[str, Any], required: dict[str, Any]
) -> dict[str, Any] | None:
    property_type = required["type"]
    if property_type not in {"select", "multi_select"}:
        return None

    required_config = required["schema"].get(property_type, {})
    current_config = current.get(property_type, {})
    if not isinstance(required_config, dict) or not isinstance(current_config, dict):
        return None

    required_options = required_config.get("options", [])
    current_options = current_config.get("options", [])
    if not isinstance(required_options, list) or not isinstance(current_options, list):
        return None

    current_names = {
        option.get("name")
        for option in current_options
        if isinstance(option, dict) and isinstance(option.get("name"), str)
    }
    missing_options = [
        option
        for option in required_options
        if isinstance(option, dict)
        and isinstance(option.get("name"), str)
        and option["name"] not in current_names
    ]
    if not missing_options:
        return None

    return {property_type: {"options": [*current_options, *missing_options]}}


def _short_summary(summary: DesktopSummary) -> str:
    return " ".join(summary.bullets[:2])[:1900]


def _heading(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "heading_2",
        "heading_2": {"rich_text": [_text(text)]},
    }


def _bulleted_item(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": [_text(text)]},
    }


def _text(content: str) -> dict[str, Any]:
    return {"type": "text", "text": {"content": content[:2000]}}
