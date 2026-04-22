from __future__ import annotations

import argparse
import sys

from crap4code.analyzers import JSFamilyAnalyzer, PythonAnalyzer, RustAnalyzer
from crap4code.core.crap_score import calculate_crap
from crap4code.core.models import FunctionMetrics
from crap4code.core.report import format_report
from crap4code.core.thresholds import DEFAULT_THRESHOLD, is_threshold_exceeded


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="crap4code")
    subparsers = parser.add_subparsers(dest="command")

    scan = subparsers.add_parser("scan", help="Scan source files")
    scan.add_argument("paths", nargs="*", help="Files or directories to scan")
    scan.add_argument(
        "--lang",
        choices=["python", "typescript", "javascript", "rust"],
        help="Language to scan (default: all)",
    )
    scan.add_argument(
        "--changed", action="store_true", help="Only analyze git-changed files"
    )
    scan.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"CRAP threshold (default: {DEFAULT_THRESHOLD})",
    )

    return parser


def _rows_with_scores(rows: list[FunctionMetrics]) -> list[FunctionMetrics]:
    for row in rows:
        if row.coverage_percent is not None:
            row.crap_score = calculate_crap(row.complexity, row.coverage_percent / 100.0)
    return rows


def _scan(args: argparse.Namespace) -> int:
    analyzers = {
        "python": PythonAnalyzer(),
        "typescript": JSFamilyAnalyzer("typescript"),
        "javascript": JSFamilyAnalyzer("javascript"),
        "rust": RustAnalyzer(),
    }

    selected = [args.lang] if args.lang else list(analyzers.keys())

    total_files = 0
    rows: list[FunctionMetrics] = []

    for language in selected:
        analyzer = analyzers[language]
        files = analyzer.discover_files(args.paths, args.changed)
        total_files += len(files)
        rows.extend(analyzer.analyze(files))

    if total_files == 0:
        print("No matching source files found.")
        return 0

    scored_rows = _rows_with_scores(rows)
    print(format_report(scored_rows))

    return 2 if is_threshold_exceeded(scored_rows, args.threshold) else 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        return 0 if code == 0 else 1

    if args.command == "scan":
        return _scan(args)

    parser.print_help()
    return 1
