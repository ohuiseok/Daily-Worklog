"""Git repository discovery and summary collection."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path

MAX_COMMIT_CHANGED_FILES = 100
MAX_COMMIT_DIFF_LINES = 400
MAX_UNCOMMITTED_DIFF_LINES = 600
MAX_DIFF_LINE_LENGTH = 900
NOISY_GIT_PATH_PATTERNS = (
    ".idea/*",
    ".pytest_cache/*",
    "build/*",
    "dist/*",
    ".gradle/*",
    "gradle/wrapper/*",
    "gradlew",
    "gradlew.bat",
    "*.spec",
    "*.class",
    "*.jar",
    "*.war",
    "*.zip",
    "*.7z",
    "*.rar",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.webp",
    "*.ico",
    "*.pdf",
)


@dataclass(frozen=True)
class GitCommit:
    hash: str
    authored_at: str
    message: str
    author_email: str = ""
    author_name: str = ""
    changed_files: list[str] = field(default_factory=list)
    diff_preview: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GitRepoInfo:
    path: Path
    branch: str | None = None
    commits: list[GitCommit] = field(default_factory=list)
    status: list[str] = field(default_factory=list)
    diff_stat: list[str] = field(default_factory=list)
    staged_diff_stat: list[str] = field(default_factory=list)
    deleted_files: list[str] = field(default_factory=list)
    unstaged_diff_preview: list[str] = field(default_factory=list)
    staged_diff_preview: list[str] = field(default_factory=list)
    error: str | None = None


def find_git_repos(roots: list[Path]) -> list[Path]:
    """Find Git repositories below roots without descending into .git dirs."""
    repos: list[Path] = []
    seen: set[Path] = set()

    for root in roots:
        if not root.exists() or not root.is_dir():
            continue

        for current, dirs, _files in _walk_dirs(root):
            if ".git" in dirs:
                resolved = current.resolve()
                if resolved not in seen:
                    repos.append(resolved)
                    seen.add(resolved)
                dirs[:] = []

    return sorted(repos, key=lambda path: str(path).lower())


def collect_git_info(
    roots: list[Path],
    since: datetime | str | None = None,
    author_emails: list[str] | None = None,
    author_names: list[str] | None = None,
    auto_author: bool = True,
) -> list[GitRepoInfo]:
    repos = find_git_repos(roots)
    return [
        collect_repo_info(
            repo,
            since=since,
            author_emails=author_emails,
            author_names=author_names,
            auto_author=auto_author,
        )
        for repo in repos
    ]


def collect_repo_info(
    repo: Path,
    since: datetime | str | None = None,
    author_emails: list[str] | None = None,
    author_names: list[str] | None = None,
    auto_author: bool = True,
) -> GitRepoInfo:
    try:
        branch = _run_git(repo, ["branch", "--show-current"]).strip() or None
        commits = _collect_commits(
            repo,
            since=since,
            author_emails=author_emails,
            author_names=author_names,
            auto_author=auto_author,
        )
        status = [
            line
            for line in _lines(_run_git(repo, ["status", "--short"]))
            if not _is_noisy_git_status_line(line)
        ]
        deleted_files = _deleted_files_from_status(status)
        diff_stat = _lines(_run_git(repo, ["diff", "--stat"]))
        staged_diff_stat = _lines(_run_git(repo, ["diff", "--cached", "--stat"]))
        unstaged_diff_preview = _git_diff_preview(
            repo, ["diff", "--unified=3"], max_lines=MAX_UNCOMMITTED_DIFF_LINES
        )
        staged_diff_preview = _git_diff_preview(
            repo,
            ["diff", "--cached", "--unified=3"],
            max_lines=MAX_UNCOMMITTED_DIFF_LINES,
        )
        return GitRepoInfo(
            path=repo,
            branch=branch,
            commits=commits,
            status=status,
            diff_stat=diff_stat,
            staged_diff_stat=staged_diff_stat,
            deleted_files=deleted_files,
            unstaged_diff_preview=unstaged_diff_preview,
            staged_diff_preview=staged_diff_preview,
        )
    except (subprocess.CalledProcessError, OSError) as exc:
        return GitRepoInfo(path=repo, error=f"{exc.__class__.__name__}: {exc}")


def _collect_commits(
    repo: Path,
    since: datetime | str | None,
    author_emails: list[str] | None,
    author_names: list[str] | None,
    auto_author: bool,
) -> list[GitCommit]:
    command = ["log", "--pretty=format:%h|%ad|%ae|%an|%s", "--date=iso-strict"]
    if since is not None:
        since_value = (
            since.strftime("%Y-%m-%d %H:%M:%S %z")
            if isinstance(since, datetime)
            else since
        )
        command.insert(1, f"--since={since_value}")

    selected_emails, selected_names = _author_filters(
        repo,
        author_emails=author_emails,
        author_names=author_names,
        auto_author=auto_author,
    )

    output = _run_git(repo, command)
    commits: list[GitCommit] = []
    for line in _lines(output):
        parts = line.split("|", 4)
        if len(parts) != 5:
            continue
        commit = GitCommit(
            hash=parts[0],
            authored_at=parts[1],
            author_email=parts[2],
            author_name=parts[3],
            message=parts[4],
        )
        if not _matches_author(commit, selected_emails, selected_names):
            continue
        commit = GitCommit(
            hash=commit.hash,
            authored_at=commit.authored_at,
            author_email=commit.author_email,
            author_name=commit.author_name,
            message=commit.message,
            changed_files=_commit_changed_files(repo, commit.hash),
            diff_preview=_commit_diff_preview(repo, commit.hash),
        )
        commits.append(commit)
    return commits


def _commit_changed_files(repo: Path, commit_hash: str) -> list[str]:
    return [
        path
        for path in _lines(_run_git(repo, ["show", "--format=", "--name-only", commit_hash]))
        if not _is_noisy_git_path(path)
    ][
        :MAX_COMMIT_CHANGED_FILES
    ]


def _commit_diff_preview(repo: Path, commit_hash: str) -> list[str]:
    return _git_diff_preview(
        repo,
        ["show", "--format=", "--unified=3", "--no-ext-diff", commit_hash],
        max_lines=MAX_COMMIT_DIFF_LINES,
    )


def _git_diff_preview(repo: Path, args: list[str], *, max_lines: int) -> list[str]:
    output = _run_git(repo, args)
    preview: list[str] = []
    skip_current_file = False
    pending_file_is_noisy = False
    for line in output.splitlines():
        line = line.rstrip()
        if line.startswith("diff --git "):
            pending_file_is_noisy = _is_noisy_diff_header(line)
            skip_current_file = pending_file_is_noisy
            continue
        if line.startswith("deleted file mode "):
            skip_current_file = True
            continue
        if line.startswith(("new file mode ", "similarity index ", "rename from ", "rename to ")):
            skip_current_file = pending_file_is_noisy
        if skip_current_file:
            continue
        if not _useful_diff_line(line):
            continue
        preview.append(_clip_diff_line(line))
        if len(preview) >= max_lines:
            break
    return preview


def _is_noisy_diff_header(line: str) -> bool:
    parts = line.split()
    if len(parts) < 4:
        return False
    path = parts[3]
    if path.startswith("b/"):
        path = path[2:]
    return _is_noisy_git_path(path)


def _is_noisy_git_status_line(line: str) -> bool:
    return any(_is_noisy_git_path(path) for path in _paths_from_status_line(line))


def _deleted_files_from_status(status: list[str]) -> list[str]:
    deleted: list[str] = []
    for line in status:
        if not _is_deleted_status_line(line):
            continue
        deleted.extend(_paths_from_status_line(line))
    return deleted


def _is_deleted_status_line(line: str) -> bool:
    return len(line) >= 2 and "D" in line[:2]


def _paths_from_status_line(line: str) -> list[str]:
    value = line[3:].strip() if len(line) > 3 else line.strip()
    if " -> " in value:
        return [part.strip() for part in value.split(" -> ", 1)]
    return [value] if value else []


def _is_noisy_git_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("/")
    return any(fnmatch(normalized, pattern) for pattern in NOISY_GIT_PATH_PATTERNS)


def _useful_diff_line(line: str) -> bool:
    if not line:
        return False
    if line.startswith(("index ", "diff --git ", "--- ", "+++ ")):
        return False
    if line.startswith("Binary files "):
        return False
    return line.startswith(("@@", "+", "-"))


def _clip_diff_line(line: str) -> str:
    if len(line) <= MAX_DIFF_LINE_LENGTH:
        return line
    return line[: MAX_DIFF_LINE_LENGTH - 1].rstrip() + "…"


def _author_filters(
    repo: Path,
    *,
    author_emails: list[str] | None,
    author_names: list[str] | None,
    auto_author: bool,
) -> tuple[set[str], set[str]]:
    emails = {item.strip().casefold() for item in author_emails or [] if item.strip()}
    names = {item.strip().casefold() for item in author_names or [] if item.strip()}

    if auto_author and not emails and not names:
        email = _git_config_value(repo, "user.email")
        name = _git_config_value(repo, "user.name")
        if email:
            emails.add(email.casefold())
        if name:
            names.add(name.casefold())

    return emails, names


def _matches_author(
    commit: GitCommit,
    selected_emails: set[str],
    selected_names: set[str],
) -> bool:
    if not selected_emails and not selected_names:
        return True

    email = commit.author_email.strip().casefold()
    name = commit.author_name.strip().casefold()
    return email in selected_emails or name in selected_names


def _git_config_value(repo: Path, key: str) -> str:
    try:
        return _run_git(repo, ["config", "--get", key]).strip()
    except (subprocess.CalledProcessError, OSError):
        return ""


def _run_git(repo: Path, args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout


def _lines(output: str) -> list[str]:
    return [line.rstrip() for line in output.splitlines() if line.strip()]


def _walk_dirs(root: Path):
    import os

    for current, dirs, files in os.walk(root):
        dirs[:] = [directory for directory in dirs if directory != ".git"]
        current_path = Path(current)
        git_dir = current_path / ".git"
        if git_dir.exists():
            dirs.append(".git")
        yield current_path, dirs, files
