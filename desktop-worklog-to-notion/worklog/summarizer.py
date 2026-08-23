"""Rule-based Desktop worklog summary generation."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from worklog.analyzers import FileAnalysis
from worklog.git_collector import GitRepoInfo
from worklog.snapshot import SnapshotDiff

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


@dataclass(frozen=True)
class DesktopSummary:
    bullets: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    status: str = "Success"


def summarize_desktop_worklog(
    diff: SnapshotDiff,
    analyses: list[FileAnalysis],
    git_infos: list[GitRepoInfo],
) -> DesktopSummary:
    bullets: list[str] = []
    keywords: list[str] = []

    total_changes = (
        len(diff.new_files) + len(diff.modified_files) + len(diff.deleted_files)
    )
    total_commits = sum(len(info.commits) for info in git_infos)
    total_dirty_files = sum(len(info.status) for info in git_infos)
    errored_repos = [info for info in git_infos if info.error]
    errored_files = [analysis for analysis in analyses if analysis.kind == "error"]

    if total_commits:
        bullets.append(f"Git 커밋 {total_commits}개를 기록했다.")
        keywords.append("git")
        for message in _commit_messages(git_infos)[:5]:
            bullets.append(f"커밋 작업: {message}")

    if total_changes:
        bullets.append(
            f"파일 변경 {total_changes}개를 감지했다"
            f" (새 파일 {len(diff.new_files)}개, "
            f"수정 {len(diff.modified_files)}개, "
            f"삭제 {len(diff.deleted_files)}개)."
        )

    extension_counts = _extension_counts(diff)
    if extension_counts:
        top_extensions = ", ".join(
            f"{extension or 'no extension'} {count}개"
            for extension, count in extension_counts.most_common(5)
        )
        bullets.append(f"주요 변경 파일 타입: {top_extensions}.")
        keywords.extend(extension.lstrip(".") for extension in extension_counts)

    folder_counts = _folder_counts(diff)
    if folder_counts:
        top_folders = ", ".join(
            f"{folder} {count}개" for folder, count in folder_counts.most_common(3)
        )
        bullets.append(f"변경이 집중된 폴더: {top_folders}.")

    changed_paths = {
        file.path for file in [*diff.new_files, *diff.modified_files]
    }
    changed_analyses = [
        analysis
        for analysis in analyses
        if analysis.path in changed_paths
        and not _is_code_file_path(analysis.path)
    ]
    analysis_counts = Counter(analysis.kind for analysis in changed_analyses)
    document_parts = []
    if analysis_counts["text"]:
        document_parts.append(f"텍스트/문서 {analysis_counts['text']}개")
        keywords.append("document")
    if analysis_counts["csv"]:
        document_parts.append(f"CSV {analysis_counts['csv']}개")
        keywords.append("csv")
    if analysis_counts["excel"]:
        document_parts.append(f"Excel {analysis_counts['excel']}개")
        keywords.append("excel")
    if document_parts:
        bullets.append(f"오늘 변경 파일 중 내용 확인: {', '.join(document_parts)}.")

    if total_dirty_files:
        bullets.append(f"커밋되지 않은 Git 변경 파일 {total_dirty_files}개가 남아 있다.")

    if errored_files:
        bullets.append(f"분석 실패 파일 {len(errored_files)}개가 있어 확인이 필요하다.")

    if not bullets:
        bullets.append("새로 기록할 Desktop 변경사항이 없다.")

    status = "Partial" if errored_files or errored_repos else "Success"
    return DesktopSummary(
        bullets=bullets,
        keywords=_dedupe_keywords(keywords),
        status=status,
    )


def _commit_messages(git_infos: list[GitRepoInfo]) -> list[str]:
    messages: list[str] = []
    for info in git_infos:
        for commit in info.commits:
            messages.append(commit.message)
    return messages


def _is_code_file_path(path: str) -> bool:
    return PurePosixPath(path.replace("\\", "/")).suffix.lower() in CODE_FILE_EXTENSIONS


def _extension_counts(diff: SnapshotDiff) -> Counter[str]:
    counter: Counter[str] = Counter()
    for file in [*diff.new_files, *diff.modified_files, *diff.deleted_files]:
        counter[file.extension] += 1
    return counter


def _folder_counts(diff: SnapshotDiff) -> Counter[str]:
    counter: Counter[str] = Counter()
    for file in [*diff.new_files, *diff.modified_files, *diff.deleted_files]:
        folder = str(PurePosixPath(file.path.replace("\\", "/")).parent)
        if folder == ".":
            counter["."] += 1
            continue

        display_folder = _safe_folder_label(folder)
        if display_folder:
            counter[display_folder] += 1
    return counter


def _safe_folder_label(folder: str, *, max_parts: int = 3, max_length: int = 80) -> str:
    if _looks_corrupted(folder):
        parts = [part for part in folder.split("/") if part]
        safe_parts = [part for part in parts if not _looks_corrupted(part)]
        if not safe_parts:
            return "(깨진 이름이 포함된 폴더)"
        folder = "/".join(safe_parts[:max_parts])

    parts = [part for part in folder.split("/") if part]
    if len(parts) > max_parts:
        folder = ".../" + "/".join(parts[-max_parts:])

    if len(folder) > max_length:
        return folder[: max_length - 1].rstrip() + "..."

    return folder


def _looks_corrupted(value: str) -> bool:
    if "\ufffd" in value:
        return True
    suspicious = ("�", "ì", "í", "ë", "ê", "ã", "Â", "媛", "蹂", "而")
    return any(token in value for token in suspicious)


def _dedupe_keywords(keywords: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for keyword in keywords:
        normalized = keyword.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped[:20]
