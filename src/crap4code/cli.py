"""CLI entrypoints for ``crap4code``.

The CLI is intentionally explicit because the primary use case is agents and
humans running the tool in CI or against a working tree and then making
verifiable follow-up changes.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from crap4code.core.config import DEFAULT_CONFIG_NAME, load_project_config, sample_config_text
from crap4code.core.coverage import cleanup_artifacts, load_coverage_database, run_coverage_command
from crap4code.core.crap_score import calculate_crap
from crap4code.core.files import discover_source_files
from crap4code.core.models import FunctionMetrics
from crap4code.core.recommendations import enrich_rows
from crap4code.core.report import build_report, format_report, format_report_json
from crap4code.core.thresholds import DEFAULT_THRESHOLD, is_threshold_exceeded
from crap4code.languages import get_language_registry


class _Parser(argparse.ArgumentParser):
    """Argument parser that preserves the tool's documented exit codes."""

    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level CLI parser."""

    parser = _Parser(prog="crap4code")
    subparsers = parser.add_subparsers(dest="command")

    scan = subparsers.add_parser("scan", help="Analyze source files and coverage")
    scan.add_argument("paths", nargs="*", help="Files or directories to scan")
    scan.add_argument(
        "--lang",
        choices=["python", "javascript", "typescript", "rust"],
        help="Language to scan. Defaults to all enabled languages.",
    )
    scan.add_argument("--changed", action="store_true", help="Only analyze changed files")
    scan.add_argument(
        "--base-ref",
        help="Optional git base ref for CI-style changed-file scans, for example origin/main",
    )
    scan.add_argument(
        "--format",
        choices=["table", "json"],
        help="Output format. Defaults to the config value or table.",
    )
    scan.add_argument(
        "--threshold",
        type=float,
        help=f"CRAP threshold. Defaults to the config value or {DEFAULT_THRESHOLD}.",
    )
    scan.add_argument(
        "--config",
        help=f"Optional path to a config file. Defaults to ./{DEFAULT_CONFIG_NAME} when present.",
    )
    scan.add_argument(
        "--report-only",
        action="store_true",
        help="Only read an existing coverage report. Do not run configured coverage commands.",
    )

    init = subparsers.add_parser("init", help="Write a sample repo-local config")
    init.add_argument(
        "--config",
        default=DEFAULT_CONFIG_NAME,
        help=f"Config path to create. Defaults to ./{DEFAULT_CONFIG_NAME}.",
    )
    init.add_argument("--force", action="store_true", help="Overwrite an existing config file")

    return parser


def _apply_coverage(rows: list[FunctionMetrics], root: Path, report_path: str | None, report_format: str | None) -> tuple[list[FunctionMetrics], list[str]]:
    """Attach measured coverage when a report is available."""

    warnings: list[str] = []
    database = load_coverage_database(root=root, report_path=report_path, report_format=report_format)
    if database is None:
        if report_path or report_format:
            warnings.append(
                f"Coverage report was not available or could not be mapped: path={report_path!r} format={report_format!r}"
            )
        return (rows, warnings)

    for row in rows:
        state, percent = database.coverage_for(row.file_path, row.start_line, row.end_line)
        row.coverage_state = state
        row.coverage_percent = percent
        if percent is not None:
            row.crap_score = calculate_crap(row.complexity, percent / 100.0)

    return (rows, warnings)


def _scan(args: argparse.Namespace) -> int:
    """Execute the ``scan`` command."""

    root = Path.cwd()
    registry = get_language_registry()
    config = load_project_config(root=root, config_path=args.config, languages=list(registry))

    selected_languages = [args.lang] if args.lang else [name for name, settings in config.languages.items() if settings.enabled]
    output_format = args.format or config.scan.format
    threshold = args.threshold if args.threshold is not None else config.scan.threshold

    all_rows: list[FunctionMetrics] = []
    warnings: list[str] = []
    coverage_commands_run: list[str] = []
    scanned_files = 0

    for language in selected_languages:
        definition = registry[language]
        settings = config.languages[language]
        default_paths = settings.paths or config.scan.default_paths
        files = discover_source_files(
            root=root,
            explicit_paths=args.paths,
            default_paths=default_paths,
            extensions=definition.extensions,
            changed_only=args.changed,
            base_ref=args.base_ref,
        )
        scanned_files += len(files)
        if not files:
            continue

        if settings.coverage_command and not args.report_only:
            cleanup_artifacts(root, settings.stale_artifacts)
            success, detail = run_coverage_command(root, settings.coverage_command)
            coverage_commands_run.append(settings.coverage_command)
            if not success:
                if detail:
                    print(detail, file=sys.stderr)
                print(
                    f"Coverage command failed for {language}: {settings.coverage_command}",
                    file=sys.stderr,
                )
                return 1

        rows = definition.analyzer.analyze(root=root, files=files)
        rows, coverage_warnings = _apply_coverage(
            rows,
            root=root,
            report_path=settings.coverage_report,
            report_format=settings.coverage_format,
        )
        warnings.extend(coverage_warnings)
        all_rows.extend(rows)

    if scanned_files == 0:
        print("No matching source files found.")
        return 0

    enrich_rows(all_rows)
    report = build_report(
        all_rows,
        scanned_files=scanned_files,
        threshold=threshold,
        changed_only=args.changed,
        base_ref=args.base_ref,
        warnings=warnings,
        coverage_commands_run=coverage_commands_run,
        config_path=str(config.config_path) if config.config_path else None,
    )

    if output_format == "json":
        print(format_report_json(report))
    else:
        print(format_report(report))

    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)

    return 2 if is_threshold_exceeded(report.functions, threshold) else 0


def _init(args: argparse.Namespace) -> int:
    """Execute the ``init`` command."""

    root = Path.cwd()
    config_path = Path(args.config)
    resolved = config_path if config_path.is_absolute() else root / config_path

    if resolved.exists() and not args.force:
        print(f"Config already exists: {resolved}", file=sys.stderr)
        return 1

    resolved.write_text(sample_config_text(), encoding="utf-8")
    print(f"Wrote sample config to {resolved}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint used by both ``python -m`` and console scripts."""

    parser = _build_parser()

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        return 0 if code == 0 else 1

    if args.command == "scan":
        return _scan(args)
    if args.command == "init":
        return _init(args)

    parser.print_help()
    return 1
