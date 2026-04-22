"""Table and JSON reporting for scan results."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
import json

from crap4code.core.models import FunctionMetrics, ScanReport, ScanSummary


def _sort_key(row: FunctionMetrics) -> tuple[int, float, int, str, str]:
    if row.crap_score is None:
        return (1, 0.0, -row.complexity, row.file_path, row.function_name)
    return (0, -row.crap_score, -row.complexity, row.file_path, row.function_name)


def build_report(
    rows: Iterable[FunctionMetrics],
    *,
    scanned_files: int,
    threshold: float,
    changed_only: bool,
    base_ref: str | None,
    warnings: list[str],
    coverage_commands_run: list[str],
    config_path: str | None,
) -> ScanReport:
    """Build the stable top-level scan report structure."""

    ordered_rows = sorted(rows, key=_sort_key)
    by_language = Counter(row.language for row in ordered_rows)
    risk_counts = Counter(row.risk_level for row in ordered_rows)
    threshold_exceeded = any(
        row.crap_score is not None and row.crap_score > threshold for row in ordered_rows
    )

    recommendations: list[dict[str, object]] = []
    for row in ordered_rows[:10]:
        if not row.recommended_actions:
            continue
        recommendations.append(
            {
                "language": row.language,
                "file_path": row.file_path,
                "function_name": row.function_name,
                "risk_level": row.risk_level,
                "recommended_actions": row.recommended_actions,
            }
        )

    summary = ScanSummary(
        scanned_files=scanned_files,
        functions_found=len(ordered_rows),
        threshold=threshold,
        threshold_exceeded=threshold_exceeded,
        changed_only=changed_only,
        base_ref=base_ref,
        by_language=dict(by_language),
        risk_counts={"high": risk_counts.get("high", 0), "moderate": risk_counts.get("moderate", 0), "low": risk_counts.get("low", 0)},
    )

    return ScanReport(
        summary=summary,
        functions=ordered_rows,
        recommendations=recommendations,
        run_metadata={
            "coverage_commands_run": coverage_commands_run,
            "config_path": config_path,
        },
        warnings=warnings,
    )


def format_report(report: ScanReport) -> str:
    """Render the default human-readable table output."""

    headers = [
        "language",
        "file",
        "container",
        "function",
        "lines",
        "complexity",
        "coverage",
        "crap",
        "risk",
    ]

    def fmt_coverage(value: float | None, state: str) -> str:
        return "N/A" if value is None or state != "measured" else f"{value:.1f}%"

    def fmt_crap(value: float | None) -> str:
        return "N/A" if value is None else f"{value:.2f}"

    table_rows = [
        [
            row.language,
            row.file_path,
            row.container or "module",
            row.function_name,
            f"{row.start_line}-{row.end_line}",
            str(row.complexity),
            fmt_coverage(row.coverage_percent, row.coverage_state),
            fmt_crap(row.crap_score),
            row.risk_level,
        ]
        for row in report.functions
    ]

    widths = [len(header) for header in headers]
    for row in table_rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def render_row(cells: list[str]) -> str:
        return " | ".join(cell.ljust(widths[index]) for index, cell in enumerate(cells))

    lines = [
        (
            f"scanned_files={report.summary.scanned_files} "
            f"functions={report.summary.functions_found} "
            f"threshold={report.summary.threshold:.2f} "
            f"threshold_exceeded={'yes' if report.summary.threshold_exceeded else 'no'}"
        ),
        render_row(headers),
        "-+-".join("-" * width for width in widths),
    ]
    lines.extend(render_row(row) for row in table_rows)
    return "\n".join(lines)


def format_report_json(report: ScanReport) -> str:
    """Serialize the report as stable JSON for CI and agent tooling."""

    return json.dumps(report.to_dict(), indent=2, sort_keys=True)
