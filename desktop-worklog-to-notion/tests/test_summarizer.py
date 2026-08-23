from __future__ import annotations

from pathlib import Path

from worklog.analyzers import FileAnalysis
from worklog.git_collector import GitCommit, GitRepoInfo
from worklog.snapshot import SnapshotDiff, SnapshotFile
from worklog.summarizer import summarize_desktop_worklog


def _file(path: str, sha: str = "hash", extension: str = ".md") -> SnapshotFile:
    return SnapshotFile(
        path=path,
        mtime="2026-08-23T10:00:00+09:00",
        size=10,
        sha256=sha,
        extension=extension,
    )


def test_summary_mentions_git_commits_and_file_changes():
    diff = SnapshotDiff(
        new_files=[_file("docs/plan.md")],
        modified_files=[_file("src/app.py", extension=".py")],
        deleted_files=[],
    )
    git_infos = [
        GitRepoInfo(
            path=Path("repo"),
            branch="main",
            commits=[
                GitCommit(
                    hash="abc123",
                    authored_at="2026-08-23T10:00:00+09:00",
                    message="add desktop scanner",
                )
            ],
        )
    ]
    analyses = [FileAnalysis(path="docs/plan.md", kind="text")]

    summary = summarize_desktop_worklog(diff, analyses, git_infos)

    assert summary.status == "Success"
    assert "Git 커밋 1개를 기록했다." in summary.bullets
    assert "커밋 작업: add desktop scanner" in summary.bullets
    assert any("파일 변경 2개를 감지했다" in bullet for bullet in summary.bullets)
    assert "git" in summary.keywords
    assert "py" in summary.keywords


def test_summary_mentions_dirty_git_files():
    diff = SnapshotDiff()
    git_infos = [
        GitRepoInfo(
            path=Path("repo"),
            branch="main",
            status=[" M readme.md", "?? new.md"],
        )
    ]

    summary = summarize_desktop_worklog(diff, [], git_infos)

    assert "커밋되지 않은 Git 변경 파일 2개가 남아 있다." in summary.bullets


def test_summary_reports_no_changes():
    summary = summarize_desktop_worklog(SnapshotDiff(), [], [])

    assert summary.bullets == ["새로 기록할 Desktop 변경사항이 없다."]
    assert summary.status == "Success"


def test_summary_marks_partial_on_analysis_error():
    summary = summarize_desktop_worklog(
        SnapshotDiff(),
        [FileAnalysis(path="broken.xlsx", kind="error", error="bad file")],
        [],
    )

    assert summary.status == "Partial"
    assert "분석 실패 파일 1개가 있어 확인이 필요하다." in summary.bullets


def test_summary_does_not_include_file_raw_content():
    diff = SnapshotDiff(modified_files=[_file("secret.md")])
    analyses = [
        FileAnalysis(
            path="secret.md",
            kind="text",
        )
    ]

    summary = summarize_desktop_worklog(diff, analyses, [])

    assert "my password is 1234" not in " ".join(summary.bullets)


def test_summary_hides_corrupted_folder_names():
    diff = SnapshotDiff(
        new_files=[
            _file("OPIC/�ㅽ뵿留뚯닔瑜� mp3/audio.mp3", extension=".mp3"),
        ],
    )

    summary = summarize_desktop_worklog(diff, [], [])

    rendered = " ".join(summary.bullets)
    assert "�ㅽ뵿" not in rendered
    assert "변경이 집중된 폴더" in rendered
