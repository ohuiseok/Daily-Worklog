"""Command line interface for desktop-worklog-to-notion."""

from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from datetime import date
from datetime import datetime
from pathlib import Path

from worklog import __version__
from worklog.analyzers import analyze_files, analysis_summary
from worklog.app_paths import ensure_installed_exe, is_frozen_app
from worklog.config import init_config, load_config
from worklog.git_collector import collect_git_info
from worklog.notion_client import (
    DesktopPayloadInput,
    NotionClient,
    NotionConfigError,
    build_desktop_notion_payload,
    payload_to_safe_json_dict,
    validate_database_id,
)
from worklog.paths import resolve_config_paths
from worklog.scanner import ScanConfig, scan_roots
from worklog.scheduler import (
    AlreadyRunningError,
    RunLock,
    SchedulerConfig,
    register_scheduled_tasks,
)
from worklog.settings import load_user_settings, prompt_user_settings, user_settings_path
from worklog.startup import ensure_startup_shortcut
from worklog.uninstall import build_uninstall_plan, uninstall
from worklog.snapshot import (
    SnapshotDiff,
    SnapshotFile,
    compare_snapshots,
    create_snapshot,
    load_snapshot,
    save_dated_snapshot,
    save_snapshot,
)
from worklog.state import (
    load_run_state,
    mark_run_started,
    mark_run_success,
    state_to_dict,
    was_recent_success,
)
from worklog.summarizer import summarize_desktop_worklog


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="worklog",
        description=(
            "Collect Desktop file and Git activity, then prepare a daily "
            "Notion worklog."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser(
        "init",
        help="Create a local .env from .env.example.",
    )

    dry_run = subparsers.add_parser(
        "dry-run",
        help="Collect local activity and print output without uploading.",
    )
    dry_run.add_argument(
        "--root",
        action="append",
        help="Override configured root path. Can be passed multiple times.",
    )
    dry_run.add_argument(
        "--no-upload",
        action="store_true",
        help="Compatibility flag for scripts; dry-run never uploads.",
    )
    dry_run.add_argument(
        "--output",
        help="Optional path to write the generated dry-run JSON.",
    )

    run = subparsers.add_parser(
        "run",
        help="Collect local activity and upload the worklog to Notion.",
    )
    run.add_argument(
        "--root",
        action="append",
        help="Override configured root path. Can be passed multiple times.",
    )
    run.add_argument(
        "--force",
        action="store_true",
        help="Run even if a recent successful run exists.",
    )
    subparsers.add_parser(
        "status",
        help="Show current local worklog state.",
    )
    subparsers.add_parser(
        "setup",
        help="Save Notion settings to the user settings file.",
    )
    subparsers.add_parser(
        "install-startup",
        help="Create a Windows Startup shortcut for the installed exe.",
    )
    uninstall_parser = subparsers.add_parser(
        "uninstall",
        help="Remove Startup shortcut, installed app files, and settings.",
    )
    uninstall_parser.add_argument(
        "--keep-settings",
        action="store_true",
        help="Keep %APPDATA% settings.json while removing installed app files.",
    )
    install_scheduler = subparsers.add_parser(
        "install-scheduler",
        help="Register Windows scheduled tasks for automatic runs.",
    )
    install_scheduler.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the scheduled task commands without registering them.",
    )
    install_scheduler.add_argument(
        "--daily-time",
        default="23:30",
        help="Daily upload time in HH:MM format. Default: 23:30.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_console_output()
    install_result = ensure_installed_exe()
    if install_result.copied:
        print(f"Installed exe copy: {install_result.target_exe}")
    parser = build_parser()
    argv = _default_frozen_argv(argv)
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "init":
        result = init_config()
        status = "created" if result.created else "exists"
        print(f"[{status}] {result.config_path}")
        print(result.message)
        return 0

    if args.command == "setup":
        settings = prompt_user_settings()
        path = user_settings_path()
        print(f"Saved settings: {path}")
        if not settings.is_ready_for_upload:
            print("Settings saved, but Notion token or database ID is still missing.")
            return 2
        startup_result = ensure_startup_shortcut()
        if startup_result.created:
            print(f"Startup shortcut: {startup_result.shortcut_path}")
        return 0

    if args.command == "install-startup":
        startup_result = ensure_startup_shortcut()
        if not startup_result.created:
            print(f"Startup shortcut was not created: {startup_result.shortcut_path}")
            return 2
        print(f"Startup shortcut: {startup_result.shortcut_path}")
        print(f"Target exe: {startup_result.target_path}")
        return 0

    if args.command == "uninstall":
        result = uninstall(
            build_uninstall_plan(remove_settings=not args.keep_settings)
        )
        for path in result.removed:
            print(f"Removed: {path}")
        for path in result.missing:
            print(f"Already missing: {path}")
        for item in result.failed:
            print(f"Failed: {item}")
        return 0 if result.success else 1

    if args.command == "dry-run":
        dry_run_state = load_run_state()
        run_data = _collect_run_data(
            args.root,
            parser=parser,
            since=dry_run_state.last_success_at,
        )
        _print_run_data(run_data)
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("w", encoding="utf-8") as file:
                json.dump(
                    payload_to_safe_json_dict(run_data["payload"]),
                    file,
                    ensure_ascii=False,
                    indent=2,
                )
                file.write("\n")
            print(f"Wrote dry-run Notion payload: {output_path}")
        return 0

    if args.command == "run":
        config = load_config()
        notion_config = config.get("notion", {})
        database_id = str(notion_config.get("database_id", ""))
        try:
            validate_database_id(database_id)
        except NotionConfigError as exc:
            print(f"Notion config error: {exc}")
            return 2

        token = str(notion_config.get("token", ""))
        if not token:
            print("Notion config error: NOTION_TOKEN is required.")
            return 2

        try:
            with RunLock():
                started_at = datetime.now().astimezone()
                loaded_state = load_run_state()
                if (
                    not args.force
                    and was_recent_success(loaded_state, started_at, within_minutes=30)
                ):
                    print("Recent successful run found within 30 minutes; skipping.")
                    return 0

                state = mark_run_started(loaded_state, started_at)
                run_data = _collect_run_data(
                    args.root,
                    parser=parser,
                    config=config,
                    since=loaded_state.last_success_at,
                )
                _print_run_data(run_data)

                if run_data["is_first_snapshot"]:
                    save_snapshot(run_data["current_snapshot"])
                    save_dated_snapshot(run_data["current_snapshot"])
                    mark_run_success(state, datetime.now().astimezone())
                    print(
                        "First run baseline saved. "
                        "No Notion page was uploaded this time. "
                        "Run again later to upload changes after this baseline."
                    )
                    return 0

                client = NotionClient(token)
                result = client.upsert_desktop_worklog(
                    run_data["payload"],
                    worklog_date=run_data["worklog_date"],
                    source=run_data["source"],
                    project_name=run_data["project_name"],
                )
                save_snapshot(run_data["current_snapshot"])
                save_dated_snapshot(run_data["current_snapshot"])
                mark_run_success(state, datetime.now().astimezone())
                print(
                    "Uploaded Notion worklog: "
                    f"page_id={result.page_id}, "
                    f"created={result.created}, "
                    f"url={result.url or 'n/a'}"
                )
        except AlreadyRunningError as exc:
            print(f"Another worklog run is already active: {exc}")
            return 3
        return 0

    if args.command == "status":
        state = load_run_state()
        print(json.dumps(state_to_dict(state), ensure_ascii=False, indent=2))
        return 0

    if args.command == "install-scheduler":
        commands = register_scheduled_tasks(
            SchedulerConfig(daily_time=args.daily_time),
            dry_run=args.dry_run,
        )
        if args.dry_run:
            print("Scheduled task commands:")
            for command in commands:
                print(command)
        else:
            print("Registered Windows scheduled tasks:")
            for command in commands:
                print(command)
        return 0

    print(
        f"The '{args.command}' command is planned but not implemented yet. "
        "Run `worklog --help` to see the available command skeleton."
    )
    return 0


def _default_frozen_argv(argv: list[str] | None) -> list[str] | None:
    if argv is not None:
        return argv
    if not is_frozen_app() or len(sys.argv) > 1:
        return argv
    if load_user_settings().is_ready_for_upload:
        return ["run"]
    return ["setup"]


def _configure_console_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            continue


def _collect_run_data(
    root_overrides: list[str] | None,
    *,
    parser: argparse.ArgumentParser,
    config: dict | None = None,
    since: datetime | str | None = None,
) -> dict:
    config = config or load_config()
    raw_roots = root_overrides or config.get("root_paths", [])
    if not isinstance(raw_roots, list):
        parser.error("root_paths must be a list.")

    print("Resolving root paths...", flush=True)
    resolved_roots = resolve_config_paths(raw_roots)
    scan_config = ScanConfig.from_dict(config.get("scan"))
    existing_roots = [resolved.path for resolved in resolved_roots if resolved.exists]
    print(
        "Scanning files "
        f"(max_files={scan_config.max_scanned_files}, "
        f"max_seconds={scan_config.max_scan_seconds})...",
        flush=True,
    )
    scan_result = scan_roots(existing_roots, scan_config, progress=_print_scan_progress)
    if scan_result.stopped_reason:
        print(f"Scan stopped early: {scan_result.stopped_reason}", flush=True)
    print(
        f"Scan complete: files={len(scan_result.files)}, skipped={len(scan_result.skipped)}",
        flush=True,
    )
    print("Comparing snapshot...", flush=True)
    previous_snapshot = load_snapshot()
    hash_file_content = bool(config.get("scan", {}).get("hash_file_content", False))
    print(
        "Creating snapshot "
        f"(hash_file_content={str(hash_file_content).lower()})...",
        flush=True,
    )
    current_snapshot = create_snapshot(
        scan_result.files,
        hash_file_content=hash_file_content,
        progress=_print_snapshot_progress,
    )
    snapshot_diff = compare_snapshots(previous_snapshot, current_snapshot)
    snapshot_diff = _filter_snapshot_diff(snapshot_diff, scan_config)
    is_first_snapshot = previous_snapshot is None
    if is_first_snapshot:
        print(
            "First run baseline mode: no previous snapshot found. "
            "Current files will be saved as the baseline on real run.",
            flush=True,
        )
        snapshot_diff = compare_snapshots(current_snapshot, current_snapshot)
    max_analysis_files = int(config.get("scan", {}).get("max_analysis_files", 10000))
    scan_config_values = config.get("scan", {})
    privacy_config = config.get("privacy", {})
    print(f"Analyzing files (max_files={max_analysis_files})...", flush=True)
    analyses = analyze_files(
        scan_result.files,
        max_files=max_analysis_files,
        include_content_preview=bool(
            privacy_config.get("upload_raw_content", True)
        ),
        text_preview_lines=int(scan_config_values.get("text_preview_lines", 20)),
        table_preview_rows=int(scan_config_values.get("table_preview_rows", 5)),
        progress=_print_analysis_progress,
    )
    print(f"Analysis complete: analyses={len(analyses)}", flush=True)
    git_since = current_snapshot.generated_at if is_first_snapshot and since is None else since
    git_config = config.get("git", {})
    print("Collecting Git info...", flush=True)
    git_infos = collect_git_info(
        existing_roots,
        since=git_since,
        author_emails=git_config.get("author_emails", []),
        author_names=git_config.get("author_names", []),
        auto_author=bool(git_config.get("auto_author", True)),
    )
    print(f"Git collection complete: repos={len(git_infos)}", flush=True)
    print("Building summary and Notion payload...", flush=True)
    desktop_summary = summarize_desktop_worklog(
        snapshot_diff,
        analyses,
        git_infos,
    )
    notion_config = config.get("notion", {})
    worklog_date = date.fromisoformat(current_snapshot.generated_at[:10])
    project_name = str(config.get("project_name", "Desktop Worklog"))
    source = str(notion_config.get("source", "Desktop"))
    payload = build_desktop_notion_payload(
        DesktopPayloadInput(
            database_id=str(notion_config.get("database_id", "NOTION_DATABASE_ID")),
            project_name=project_name,
            worklog_date=worklog_date,
            source=source,
            summary=desktop_summary,
            diff=snapshot_diff,
            analyses=analyses,
            git_infos=git_infos,
            skipped_count=len(scan_result.skipped),
        )
    )
    return {
        "resolved_roots": resolved_roots,
        "scan_result": scan_result,
        "current_snapshot": current_snapshot,
        "snapshot_diff": snapshot_diff,
        "is_first_snapshot": is_first_snapshot,
        "analyses": analyses,
        "git_infos": git_infos,
        "desktop_summary": desktop_summary,
        "payload": payload,
        "worklog_date": worklog_date,
        "project_name": project_name,
        "source": source,
    }


def _print_scan_progress(
    _stage: str,
    dirs_seen: int,
    files_seen: int,
    skipped_seen: int,
) -> None:
    print(
        f"  scan progress: dirs={dirs_seen}, files={files_seen}, skipped={skipped_seen}",
        flush=True,
    )


def _filter_snapshot_diff(diff: SnapshotDiff, scan_config: ScanConfig) -> SnapshotDiff:
    return SnapshotDiff(
        new_files=[
            file for file in diff.new_files if not _snapshot_file_excluded(file, scan_config)
        ],
        modified_files=[
            file
            for file in diff.modified_files
            if not _snapshot_file_excluded(file, scan_config)
        ],
        deleted_files=[
            file
            for file in diff.deleted_files
            if not _snapshot_file_excluded(file, scan_config)
        ],
    )


def _snapshot_file_excluded(file: SnapshotFile, scan_config: ScanConfig) -> bool:
    normalized_path = file.path.replace("\\", "/")
    path_parts = [part for part in normalized_path.split("/") if part]
    excluded_dirs = {directory.lower() for directory in scan_config.exclude_dirs}
    if any(part.lower() in excluded_dirs for part in path_parts[:-1]):
        return True

    if file.extension.lower() in {
        extension.lower() for extension in scan_config.exclude_extensions
    }:
        return True

    file_name = path_parts[-1] if path_parts else normalized_path
    return any(
        fnmatch.fnmatch(file_name, pattern)
        for pattern in scan_config.exclude_name_patterns
    )


def _print_analysis_progress(done: int, total: int) -> None:
    print(f"  analysis progress: {done}/{total}", flush=True)


def _print_snapshot_progress(done: int, total: int) -> None:
    print(f"  snapshot progress: {done}/{total}", flush=True)


def _print_run_data(run_data: dict) -> None:
    print("Resolved root paths:")
    for resolved in run_data["resolved_roots"]:
        print(f"- {resolved.path} (exists={resolved.exists})")
        if resolved.warning:
            print(f"  warning: {resolved.warning}")

    scan_result = run_data["scan_result"]
    snapshot_diff = run_data["snapshot_diff"]
    analyses = run_data["analyses"]
    git_infos = run_data["git_infos"]
    desktop_summary = run_data["desktop_summary"]
    summary = analysis_summary(analyses)

    print(
        f"Scanned files: {len(scan_result.files)} "
        f"(skipped={len(scan_result.skipped)})"
    )
    print(
        "Snapshot diff: "
        f"new={len(snapshot_diff.new_files)}, "
        f"modified={len(snapshot_diff.modified_files)}, "
        f"deleted={len(snapshot_diff.deleted_files)}"
    )
    print(
        "Analysis summary: "
        f"text={summary['text']}, "
        f"csv={summary['csv']}, "
        f"excel={summary['excel']}, "
        f"unsupported={summary['unsupported']}, "
        f"error={summary['error']}"
    )
    print(
        "Git summary: "
        f"repos={len(git_infos)}, "
        f"commits={sum(len(info.commits) for info in git_infos)}, "
        f"dirty_repos={sum(1 for info in git_infos if info.status)}"
    )
    for git_info in git_infos[:10]:
        print(
            "- git "
            f"{git_info.path} "
            f"(branch={git_info.branch or 'unknown'}, "
            f"commits={len(git_info.commits)}, "
            f"status={len(git_info.status)}, "
            f"error={git_info.error or 'none'})"
        )
    print(f"Desktop summary status: {desktop_summary.status}")
    print("Desktop summary:")
    for bullet in desktop_summary.bullets:
        print(f"- {bullet}")
    changed_files = [
        *snapshot_diff.new_files,
        *snapshot_diff.modified_files,
        *snapshot_diff.deleted_files,
    ]
    for changed_file in changed_files[:20]:
        print(
            "- "
            f"{changed_file.path} "
            f"({changed_file.extension or 'no extension'}, "
            f"{changed_file.size} bytes)"
        )
    if len(changed_files) > 20:
        print(f"... {len(changed_files) - 20} more changed files")


if __name__ == "__main__":
    raise SystemExit(main())
