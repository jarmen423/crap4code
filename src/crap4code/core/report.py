from __future__ import annotations

from collections.abc import Iterable

from .models import FunctionMetrics


def _sort_key(row: FunctionMetrics) -> tuple[int, float, int, str, str]:
    if row.crap_score is None:
        return (1, 0.0, -row.complexity, row.file_path, row.function_name)
    return (0, -row.crap_score, -row.complexity, row.file_path, row.function_name)


def _fmt_coverage(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.1f}%"


def _fmt_crap(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.2f}"


def format_report(metrics: Iterable[FunctionMetrics]) -> str:
    rows = sorted(metrics, key=_sort_key)

    headers = [
        "language",
        "file",
        "container",
        "function",
        "line",
        "complexity",
        "coverage",
        "crap",
    ]

    table_rows = [
        [
            row.language,
            row.file_path,
            row.container or "-",
            row.function_name,
            str(row.line),
            str(row.complexity),
            _fmt_coverage(row.coverage_percent),
            _fmt_crap(row.crap_score),
        ]
        for row in rows
    ]

    widths = [len(h) for h in headers]
    for row in table_rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))

    def render_row(cells: list[str]) -> str:
        return " | ".join(cell.ljust(widths[idx]) for idx, cell in enumerate(cells))

    output = [render_row(headers), "-+-".join("-" * w for w in widths)]
    output.extend(render_row(row) for row in table_rows)
    return "\n".join(output)
