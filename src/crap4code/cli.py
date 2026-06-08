"""CLI entrypoints for ``crap4code``.

The CLI is intentionally explicit because the primary use case is agents and
humans running the tool in CI or against a working tree and then making
verifiable follow-up changes.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from crap4code import __version__
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
    """Build the top-level CLI parser.

    The parser is constructed here (not at import time) so tests can
    exercise main() with synthetic argv lists without side effects.
    """

    parser = _Parser(prog="crap4code")

    # Top-level options (before subparsers) so they work for bare invocation
    # e.g. ``crap4code --version`` and ``crap4code -V``.
    # Uses the single source of truth ``crap4code.__version__`` (see __init__.py).
    # This addresses Issue C2 in the Windows & Cross-Platform plan.
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show program's version number and exit",
    )

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
        # Pass warnings list so R1 case-insensitive fallback can record an
        # auditable diagnostic (see coverage.py and plan).
        state, percent = database.coverage_for(row.file_path, row.start_line, row.end_line, warnings)
        row.coverage_state = state
        row.coverage_percent = percent
        if percent is not None:
            row.crap_score = calculate_crap(row.complexity, percent / 100.0)

    return (rows, warnings)


def _scan(args: argparse.Namespace) -> int:
    """Execute the ``scan`` command.

    Warnings collected during the run (from coverage mapping, from git-changed
    discovery when --changed/--base-ref are supplied, etc.) are accumulated in
    the local `warnings` list, passed to build_report (so they appear inside
    the ScanReport and thus in JSON and the table summary), and also printed
    to stderr after the main output (see end of function).

    The git warning path (phase2-git-warn / Issue E2) is exercised when
    changed_only=True: discover_source_files now surfaces the warnings
    returned by get_changed_files. Special handling below the loop ensures
    that even the "No matching source files found." early-exit path (which
    happens precisely when --changed is used in a non-repo or git-less
    environment) still emits the diagnostic(s) to stderr. This gives users
    and agents on Windows CI the observability they previously lacked.

    After D1/D3 (phase1-d1) language decoupling: registry may contain only a
    subset of the four languages at runtime (Python is always present; the
    others depend on whether their tree-sitter grammar package could be
    imported and instantiated). If the user supplies --lang for a language
    that is not currently available, we emit a clear actionable message
    (matching the style in the plan) and return exit code 1 instead
    of KeyError or raw ImportError. Unrequested missing languages are
    silently not offered (config loading and default selection only see what
    the registry advertised).
    """

    root = Path.cwd()
    registry = get_language_registry()
    config, config_warnings = load_project_config(
        root=root, config_path=args.config, languages=list(registry)
    )

    # Handle explicit --lang request for a language whose analyzer/grammar
    # could not be loaded (the core of the graceful degradation for D3).
    # This check must be *after* registry (which does the tolerant load) but
    # before we index into registry[...] or config.languages[...].
    if args.lang and args.lang not in registry:
        pkg_map = {
            "javascript": "tree-sitter-javascript",
            "typescript": "tree-sitter-typescript",
            "rust": "tree-sitter-rust",
        }
        pkg = pkg_map.get(args.lang, f"tree-sitter-{args.lang}")
        available = sorted(registry.keys())
        if available:
            still = f"These languages still work: {', '.join(available)}."
        else:
            still = "No languages are currently available."
        print(
            f"{args.lang.capitalize()} support requires `pip install {pkg}`. {still}",
            file=sys.stderr,
        )
        return 1

    selected_languages = [args.lang] if args.lang else [name for name, settings in config.languages.items() if settings.enabled]
    output_format = args.format or config.scan.format
    threshold = args.threshold if args.threshold is not None else config.scan.threshold

    all_rows: list[FunctionMetrics] = []
    warnings: list[str] = list(config_warnings)
    coverage_commands_run: list[str] = []
    scanned_files = 0

    for language in selected_languages:
        definition = registry[language]
        settings = config.languages[language]
        default_paths = settings.paths or config.scan.default_paths
        files, git_warnings = discover_source_files(
            root=root,
            explicit_paths=args.paths,
            default_paths=default_paths,
            extensions=definition.extensions,
            changed_only=args.changed,
            base_ref=args.base_ref,
        )
        warnings.extend(git_warnings)
        scanned_files += len(files)
        if not files:
            continue

        if settings.coverage_command and not args.report_only:
            # Hardened cleanup (phase1-e1) now returns warnings instead of
            # potentially raising. Propagate them so they appear in ScanReport
            # (via build_report) and are printed after the report (phase2).
            cleanup_warnings = cleanup_artifacts(root, settings.stale_artifacts)
            warnings.extend(cleanup_warnings)
            success, detail = run_coverage_command(root, settings.coverage_command)
            coverage_commands_run.append(settings.coverage_command)
            if not success:
                if detail:
                    # detail from run_coverage_command now contains the rich
                    # diagnostics block (platform shell/ComSpec, exact command,
                    # cwd, returncode). Prefix it for the user (phase1-s1).
                    print("--- coverage command diagnostics (see plan S1/S2) ---", file=sys.stderr)
                    print(detail, file=sys.stderr)
                print(
                    f"Coverage command failed for {language}: {settings.coverage_command}",
                    file=sys.stderr,
                )
                # Make it actionable especially for Windows users who may be
                # surprised that their pwsh session still results in cmd.exe.
                print(
                    "Actionable hint: coverage commands run via shell=True under the "
                    "platform's default shell (ComSpec=cmd.exe on Windows, $SHELL on POSIX). "
                    "Use python -m forms for portability, or wrap with "
                    "pwsh -Command '...' when you need pwsh syntax. "
                    "Diagnostics above include the exact string that was executed.",
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
        # Surface any warnings (e.g. the git --changed failure diagnostic)
        # even on the early "no files" path. Without this, a --changed scan
        # outside a git repo would print the "No matching..." message and
        # return silently with zero diagnostics — exactly the problem E2
        # set out to fix. Warnings still appear in the structured report only
        # on the path that actually builds a ScanReport.
        for warning in warnings:
            print(f"warning: {warning}", file=sys.stderr)
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
    """CLI entrypoint used by both ``python -m crap4code`` (and ``python -m crap4code.main``) and the console script.

    The console script (see pyproject.toml) points at ``crap4code.main:main``.
    ``python -m crap4code`` is enabled by the sibling ``__main__.py`` which
    also delegates through ``main`` to here.

    ``argv`` is accepted for testability (see tests/test_cli.py) so that
    we can drive the parser without touching sys.argv.
    """

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
