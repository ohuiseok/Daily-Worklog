"""PyInstaller entrypoint for desktop-worklog-to-notion."""

from __future__ import annotations

from worklog.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
