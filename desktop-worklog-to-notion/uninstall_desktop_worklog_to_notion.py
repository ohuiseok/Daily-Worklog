"""PyInstaller entrypoint for uninstall-desktop-worklog-to-notion."""

from __future__ import annotations

from worklog.uninstall import build_uninstall_plan, uninstall


def main() -> int:
    result = uninstall(build_uninstall_plan(remove_settings=True))
    for path in result.removed:
        print(f"Removed: {path}")
    for path in result.missing:
        print(f"Already missing: {path}")
    for item in result.failed:
        print(f"Failed: {item}")
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
