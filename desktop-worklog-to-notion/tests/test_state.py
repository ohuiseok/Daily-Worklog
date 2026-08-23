from __future__ import annotations

from datetime import datetime, timezone

from worklog.state import (
    RunState,
    load_run_state,
    mark_run_started,
    mark_run_success,
    save_run_state,
    state_to_dict,
    was_recent_success,
)


def test_missing_state_is_first_run(tmp_path):
    state = load_run_state(tmp_path / "run_state.json")

    assert state.is_first_run is True
    assert state.last_success_at is None
    assert state.timezone == "Asia/Seoul"


def test_save_and_load_state(tmp_path):
    path = tmp_path / "state" / "run_state.json"
    original = RunState(
        last_success_at="2026-08-23T10:00:00+09:00",
        last_run_at="2026-08-23T10:00:00+09:00",
        timezone="Asia/Seoul",
    )

    save_run_state(original, path=path)
    loaded = load_run_state(path)

    assert loaded == original
    assert loaded.is_first_run is False


def test_mark_run_started_does_not_change_last_success_at(tmp_path):
    path = tmp_path / "run_state.json"
    state = RunState(last_success_at="2026-08-22T23:30:00+09:00")
    started_at = datetime(2026, 8, 23, 9, 0, tzinfo=timezone.utc)

    updated = mark_run_started(state, started_at, path=path)

    assert updated.last_success_at == "2026-08-22T23:30:00+09:00"
    assert updated.last_run_at == "2026-08-23T09:00:00+00:00"
    assert load_run_state(path) == updated


def test_mark_run_success_advances_last_success_at(tmp_path):
    path = tmp_path / "run_state.json"
    state = RunState(last_success_at="2026-08-22T23:30:00+09:00")
    succeeded_at = datetime(2026, 8, 23, 23, 30, tzinfo=timezone.utc)

    updated = mark_run_success(state, succeeded_at, path=path)

    assert updated.last_success_at == "2026-08-23T23:30:00+00:00"
    assert updated.last_run_at == "2026-08-23T23:30:00+00:00"
    assert load_run_state(path) == updated


def test_state_to_dict_includes_first_run_flag():
    state = RunState()

    result = state_to_dict(state)

    assert result["is_first_run"] is True
    assert result["last_success_at"] is None


def test_was_recent_success():
    state = RunState(last_success_at="2026-08-23T10:00:00+00:00")
    now = datetime(2026, 8, 23, 10, 20, tzinfo=timezone.utc)

    assert was_recent_success(state, now, within_minutes=30) is True


def test_was_recent_success_returns_false_for_old_run():
    state = RunState(last_success_at="2026-08-23T10:00:00+00:00")
    now = datetime(2026, 8, 23, 10, 31, tzinfo=timezone.utc)

    assert was_recent_success(state, now, within_minutes=30) is False
