from __future__ import annotations

import subprocess
from datetime import datetime, timedelta

from worklog.git_collector import collect_git_info, collect_repo_info, find_git_repos


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _create_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "tester")
    (repo / "readme.md").write_text("hello", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial worklog test")
    return repo


def test_find_git_repos(tmp_path):
    repo = _create_repo(tmp_path)
    non_repo = tmp_path / "plain"
    non_repo.mkdir()

    repos = find_git_repos([tmp_path])

    assert repos == [repo.resolve()]


def test_collect_repo_info_includes_commit_message(tmp_path):
    repo = _create_repo(tmp_path)

    info = collect_repo_info(repo)

    assert info.error is None
    assert info.branch in {"master", "main"}
    assert len(info.commits) == 1
    assert info.commits[0].message == "initial worklog test"
    assert info.commits[0].author_email == "test@example.com"
    assert info.commits[0].author_name == "tester"
    assert info.commits[0].changed_files == ["readme.md"]
    assert any("+hello" in line for line in info.commits[0].diff_preview)
    assert info.status == []


def test_collect_repo_info_since_filters_old_commits(tmp_path):
    repo = _create_repo(tmp_path)
    future = datetime.now().astimezone() + timedelta(days=1)

    info = collect_repo_info(repo, since=future)

    assert info.commits == []


def test_collect_repo_info_status_and_diff_stat(tmp_path):
    repo = _create_repo(tmp_path)
    (repo / "readme.md").write_text("changed", encoding="utf-8")

    info = collect_repo_info(repo)

    assert any("readme.md" in line for line in info.status)
    assert any("readme.md" in line for line in info.diff_stat)
    assert any("-hello" in line for line in info.unstaged_diff_preview)
    assert any("+changed" in line for line in info.unstaged_diff_preview)


def test_collect_repo_info_includes_staged_diff_preview(tmp_path):
    repo = _create_repo(tmp_path)
    (repo / "readme.md").write_text("staged change", encoding="utf-8")
    _git(repo, "add", "readme.md")

    info = collect_repo_info(repo)

    assert any("-hello" in line for line in info.staged_diff_preview)
    assert any("+staged change" in line for line in info.staged_diff_preview)


def test_collect_repo_info_skips_noisy_tooling_diff(tmp_path):
    repo = _create_repo(tmp_path)
    wrapper = repo / "gradlew"
    wrapper.write_text("tooling script\n" * 20, encoding="utf-8")
    _git(repo, "add", "gradlew")
    _git(repo, "commit", "-m", "add wrapper")
    wrapper.unlink()
    (repo / "readme.md").write_text("real work", encoding="utf-8")

    info = collect_repo_info(repo)

    assert all("tooling script" not in line for line in info.unstaged_diff_preview)
    assert any("+real work" in line for line in info.unstaged_diff_preview)
    assert all("gradlew" not in line for line in info.status)
    assert any("readme.md" in line for line in info.status)


def test_collect_repo_info_summarizes_deleted_files_without_diff_body(tmp_path):
    repo = _create_repo(tmp_path)
    (repo / "feature.py").write_text(
        "def removed():\n    return 'deleted body'\n",
        encoding="utf-8",
    )
    _git(repo, "add", "feature.py")
    _git(repo, "commit", "-m", "add feature")
    (repo / "feature.py").unlink()

    info = collect_repo_info(repo)

    assert info.deleted_files == ["feature.py"]
    assert any("feature.py" in line for line in info.status)
    assert all("deleted body" not in line for line in info.unstaged_diff_preview)


def test_collect_repo_info_filters_commits_by_author_email(tmp_path):
    repo = _create_repo(tmp_path)

    info = collect_repo_info(repo, author_emails=["other@example.com"])

    assert info.error is None
    assert info.commits == []


def test_collect_repo_info_auto_author_uses_repo_git_config(tmp_path):
    repo = _create_repo(tmp_path)
    _git(repo, "config", "user.email", "other@example.com")
    _git(repo, "config", "user.name", "other")

    info = collect_repo_info(repo)

    assert info.error is None
    assert info.commits == []


def test_collect_git_info_ignores_non_repo_root(tmp_path):
    root = tmp_path / "plain"
    root.mkdir()

    infos = collect_git_info([root])

    assert infos == []
