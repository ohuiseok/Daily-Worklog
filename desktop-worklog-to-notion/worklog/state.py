"""Persistent run state for incremental collection."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from worklog.config import STATE_DIR


RUN_STATE_PATH = STATE_DIR / "run_state.json"


@dataclass(frozen=True)
class RunState:
    last_success_at: str | None = None
    last_run_at: str | None = None
    timezone: str = "Asia/Seoul"

    @property
    def is_first_run(self) -> bool:
        return self.last_success_at is None


def load_run_state(path: Path = RUN_STATE_PATH) -> RunState:
    """Load persisted run state, returning a first-run state if missing."""
    if not path.exists():
        return RunState()

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError("Run state root must be a JSON object.")

    return RunState(
        last_success_at=_optional_str(data.get("last_success_at")),
        last_run_at=_optional_str(data.get("last_run_at")),
        timezone=str(data.get("timezone") or "Asia/Seoul"),
    )


def save_run_state(state: RunState, path: Path = RUN_STATE_PATH) -> None:
    """Persist run state as UTF-8 JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(asdict(state), file, ensure_ascii=False, indent=2)
        file.write("\n")


def mark_run_started(
    state: RunState, started_at: datetime, path: Path = RUN_STATE_PATH
) -> RunState:
    """Record an attempted run without changing last_success_at."""
    updated = RunState(
        last_success_at=state.last_success_at,
        last_run_at=started_at.isoformat(),
        timezone=state.timezone,
    )
    save_run_state(updated, path=path)
    return updated


def mark_run_success(
    state: RunState,
    succeeded_at: datetime,
    path: Path = RUN_STATE_PATH,
) -> RunState:
    """Record a successful run and advance last_success_at."""
    updated = RunState(
        last_success_at=succeeded_at.isoformat(),
        last_run_at=succeeded_at.isoformat(),
        timezone=state.timezone,
    )
    save_run_state(updated, path=path)
    return updated


def state_to_dict(state: RunState) -> dict[str, Any]:
    return {
        "last_success_at": state.last_success_at,
        "last_run_at": state.last_run_at,
        "timezone": state.timezone,
        "is_first_run": state.is_first_run,
    }


def was_recent_success(
    state: RunState,
    now: datetime,
    *,
    within_minutes: int = 30,
) -> bool:
    if state.last_success_at is None:
        return False

    last_success_at = datetime.fromisoformat(state.last_success_at)
    if last_success_at.tzinfo is None and now.tzinfo is not None:
        last_success_at = last_success_at.replace(tzinfo=now.tzinfo)

    return now - last_success_at < timedelta(minutes=within_minutes)


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
