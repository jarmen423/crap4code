"""Reporting for scan results: plain text, rich terminal TUI, and self-contained HTML.

This module is the presentation layer. The data contract lives in models.py
(build_report assembles a stable ScanReport). We provide multiple renderers so
humans get delight in the terminal (rich) and can share a beautiful standalone
HTML file, while agents/CI continue to use JSON or the simple text table.

Design notes:
- Rich renderer uses direct Console printing for best colors, wrapping, and
  width detection. It is the default "table" experience.
- HTML is a single-file, zero-install, Tailwind-CDN powered report with client-side
  interactivity (sort + risk filters + search + JSON export).
- Plain text table is kept for compatibility, piping, and tests that capture stdout.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
import datetime
import json

from crap4code.core.models import FunctionMetrics, ScanReport, ScanSummary

# --- Rich (terminal) support ---
# We import lazily inside the render function so that a completely minimal
# environment can still import the module (rich is now a declared dep, but
# defensive loading doesn't hurt and matches the spirit of the lazy language
# registry).
_HAS_RICH = False
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich import box
    _HAS_RICH = True
except Exception:  # pragma: no cover
    Console = None  # type: ignore
    Panel = None    # type: ignore
    Table = None    # type: ignore
    Text = None     # type: ignore
    box = None      # type: ignore


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


# =============================================================================
# Rich Terminal Renderer (the nice TUI experience)
# =============================================================================

def _risk_style(risk: str) -> str:
    """Map risk level to a rich style string."""
    risk = (risk or "low").lower()
    if risk == "high":
        return "bold red"
    if risk == "moderate":
        return "yellow"
    return "green"


def _fmt_cov(pct: float | None, state: str) -> str:
    if pct is None or state != "measured":
        return "N/A"
    return f"{pct:.1f}%"


def _fmt_crap(val: float | None) -> str:
    return "N/A" if val is None else f"{val:.2f}"


def render_rich_report(report: ScanReport) -> None:
    """Render a beautiful, colored, scannable report directly to the terminal using rich.

    This is what users see for the default ``--format table`` (or when format is
    omitted). It gives a real "TUI feel": header panels, risk-colored cells,
    clear visual hierarchy, and the top recommendations surfaced prominently.

    Falls back to a plain-text version if rich cannot be imported (shouldn't
    happen after the declared dependency, but defensive).
    """
    if not _HAS_RICH or Console is None:
        # Fallback: use the existing plain ASCII table so we never explode.
        print(format_report(report))
        return

    console = Console()

    # --- Header / Title ---
    title = Text("crap4code", style="bold cyan")
    subtitle = Text("  •  complexity • coverage • CRAP • risk", style="dim")
    console.print(Panel(Text.assemble(title, subtitle), box=box.ROUNDED, style="cyan", padding=(0, 1)))

    # --- Top summary line (same data as before but prettier) ---
    s = report.summary
    summary_line = (
        f"[bold]files[/]: {s.scanned_files}   "
        f"[bold]functions[/]: {s.functions_found}   "
        f"[bold]threshold[/]: {s.threshold:.1f}   "
        f"exceeded: {'[bold red]yes[/]' if s.threshold_exceeded else '[green]no[/]'}"
    )
    console.print(summary_line, style="dim")
    console.print()

    # --- Stats cards row (risk distribution + languages) ---
    risk_counts = s.risk_counts
    high = risk_counts.get("high", 0)
    mod = risk_counts.get("moderate", 0)
    low = risk_counts.get("low", 0)
    total = high + mod + low or 1

    risk_text = Text()
    risk_text.append("HIGH ", style="bold red")
    risk_text.append(f"{high}  ", style="red")
    risk_text.append("MODERATE ", style="yellow")
    risk_text.append(f"{mod}  ", style="yellow")
    risk_text.append("LOW ", style="green")
    risk_text.append(f"{low}", style="green")

    lang_items = ", ".join(f"{k}:{v}" for k, v in sorted(s.by_language.items()))
    lang_text = Text(f"languages: {lang_items}", style="dim")

    stats_panel = Panel(
        Text.assemble(risk_text, "\n", lang_text),
        title="Risk & Language Summary",
        box=box.SQUARE,
        padding=(1, 2),
    )
    console.print(stats_panel)
    console.print()

    # --- Main data table ---
    table = Table(
        title="Functions (sorted by CRAP desc, then complexity)",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        padding=(0, 1),
        expand=True,
    )

    # Columns chosen for scannability on typical wide terminals
    table.add_column("lang", style="dim")
    table.add_column("file", style="blue", no_wrap=True, max_width=42)
    table.add_column("fn", style="white", max_width=28)
    table.add_column("lines", justify="right", style="dim")
    table.add_column("cx", justify="right")
    table.add_column("cov", justify="right")
    table.add_column("CRAP", justify="right")
    table.add_column("risk", justify="center")

    for row in report.functions:
        risk_style = _risk_style(row.risk_level)
        crap_str = _fmt_crap(row.crap_score)
        # Give high-CRAP numbers a stronger visual pop
        if row.crap_score is not None and row.crap_score > 30:
            crap_style = "bold red"
        elif row.crap_score is not None and row.crap_score > 8:
            crap_style = "yellow"
        else:
            crap_style = "green"

        table.add_row(
            row.language[:4],
            row.file_path,
            row.function_name,
            f"{row.start_line}-{row.end_line}",
            str(row.complexity),
            _fmt_cov(row.coverage_percent, row.coverage_state),
            Text(crap_str, style=crap_style),
            Text(row.risk_level.upper(), style=risk_style),
        )

    console.print(table)
    console.print()

    # --- Top recommendations (actionable, from the pre-computed list) ---
    if report.recommendations:
        rec_lines: list[str] = []
        for r in report.recommendations[:8]:  # keep the panel compact
            loc = f"{r['file_path']}:{r['function_name']}"
            risk_s = _risk_style(r.get("risk_level", "low"))
            actions = "; ".join(r.get("recommended_actions", [])[:2])
            rec_lines.append(f"[{risk_s}]{r['risk_level'].upper()}[/]  {loc}\n    {actions}")

        rec_panel = Panel(
            "\n\n".join(rec_lines) if rec_lines else "None",
            title="Priority Recommendations (top offenders first)",
            box=box.SQUARE,
            style="yellow",
            padding=(1, 2),
        )
        console.print(rec_panel)
        console.print()

    # --- Warnings (if any) ---
    if report.warnings:
        warn_text = "\n".join(f"• {w}" for w in report.warnings)
        warn_panel = Panel(
            Text(warn_text, style="yellow"),
            title="Warnings",
            box=box.SQUARE,
            style="yellow",
            padding=(0, 1),
        )
        console.print(warn_panel)
        console.print()

    # --- Footer ---
    footer = Text(f"threshold={s.threshold}  generated={datetime.datetime.now().isoformat(timespec='seconds')}", style="dim")
    console.print(footer)
    console.print(Text("Run with --format json for machine consumption or --format html for a shareable report.", style="dim"))


# =============================================================================
# Self-contained HTML Report
# =============================================================================

def format_report_html(report: ScanReport) -> str:
    """Return a complete, beautiful, single-file HTML document.

    Features:
    - Zero external files at view time (Tailwind via CDN play script + vanilla JS).
    - Summary cards + risk distribution at the top.
    - Interactive table: click column headers to sort, risk filter chips,
      live text search across file+function.
    - Visual coverage bars + color scaling for CRAP/risk.
    - Embedded full JSON so you can "Download JSON" without re-running the scan.
    - Recommendations section and warnings (if present).
    - Responsive, dark-friendly, copy-paste friendly.

    Typical usage:
        crap4code scan --format html > crap4code-report.html
        # then open the file in any browser
    """
    s = report.summary
    now = datetime.datetime.now().isoformat(timespec="seconds")
    data_json = json.dumps(report.to_dict(), indent=2, sort_keys=True)

    # Pre-compute a few things for the template
    risk_high = s.risk_counts.get("high", 0)
    risk_mod = s.risk_counts.get("moderate", 0)
    risk_low = s.risk_counts.get("low", 0)
    total_funcs = s.functions_found or 1

    def _row_html(row: FunctionMetrics) -> str:
        cov = row.coverage_percent if row.coverage_state == "measured" and row.coverage_percent is not None else None
        cov_label = f"{cov:.1f}%" if cov is not None else "N/A"
        cov_bar = f'<div class="h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden mt-0.5"><div class="h-1.5 bg-emerald-500" style="width:{min(cov or 0, 100)}%"></div></div>' if cov is not None else ""

        crap = row.crap_score
        if crap is None:
            crap_label = "N/A"
            crap_color = "text-slate-400"
        elif crap > 30:
            crap_label = f"{crap:.2f}"
            crap_color = "text-red-600 dark:text-red-400 font-semibold"
        elif crap > 8:
            crap_label = f"{crap:.2f}"
            crap_color = "text-amber-600 dark:text-amber-400 font-semibold"
        else:
            crap_label = f"{crap:.2f}"
            crap_color = "text-emerald-600 dark:text-emerald-400"

        risk = (row.risk_level or "low").lower()
        if risk == "high":
            risk_badge = '<span class="px-2 py-0.5 text-xs font-bold rounded bg-red-100 text-red-700 dark:bg-red-900/60 dark:text-red-300">HIGH</span>'
        elif risk == "moderate":
            risk_badge = '<span class="px-2 py-0.5 text-xs font-bold rounded bg-amber-100 text-amber-700 dark:bg-amber-900/60 dark:text-amber-300">MODERATE</span>'
        else:
            risk_badge = '<span class="px-2 py-0.5 text-xs font-bold rounded bg-emerald-100 text-emerald-700 dark:bg-emerald-900/60 dark:text-emerald-300">LOW</span>'

        return f"""
<tr data-risk="{risk}" data-search="{row.file_path} {row.function_name} {row.language}" class="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/60">
  <td class="px-3 py-2 font-mono text-[10px] text-slate-500">{row.language}</td>
  <td class="px-3 py-2 font-mono text-xs text-slate-700 dark:text-slate-300">{row.file_path}</td>
  <td class="px-3 py-2 font-medium text-slate-900 dark:text-white">{row.function_name}</td>
  <td class="px-3 py-2 text-right font-mono text-xs text-slate-500">{row.start_line}-{row.end_line}</td>
  <td class="px-3 py-2 text-right font-mono">{row.complexity}</td>
  <td class="px-3 py-2 text-right">
    <div class="flex items-center justify-end gap-2">
      <span class="font-mono text-sm">{cov_label}</span>
      <div class="w-12">{cov_bar}</div>
    </div>
  </td>
  <td class="px-3 py-2 text-right font-mono {crap_color}">{crap_label}</td>
  <td class="px-3 py-2 text-center">{risk_badge}</td>
</tr>
"""

    rows_html = "\n".join(_row_html(r) for r in report.functions)

    # Top recommendations as nice cards
    recs_html = ""
    if report.recommendations:
        cards = []
        for r in report.recommendations[:6]:
            actions = "<br>".join(r.get("recommended_actions", [])[:2])
            risk = (r.get("risk_level") or "low").lower()
            badge = ("HIGH" if risk == "high" else "MODERATE" if risk == "moderate" else "LOW")
            color = ("red" if risk == "high" else "amber" if risk == "moderate" else "emerald")
            cards.append(f"""
<div class="rounded-xl border border-slate-200 dark:border-slate-700 p-3 bg-white/60 dark:bg-slate-900/60">
  <div class="flex items-center gap-2 mb-1">
    <span class="text-xs px-1.5 py-px rounded bg-{color}-100 text-{color}-700 dark:bg-{color}-900/50 dark:text-{color}-300 font-semibold">{badge}</span>
    <span class="font-mono text-xs text-slate-500">{r['file_path']}</span>
  </div>
  <div class="font-semibold text-sm mb-1 text-slate-900 dark:text-white">{r['function_name']}</div>
  <div class="text-xs text-slate-600 dark:text-slate-400 leading-snug">{actions}</div>
</div>
""")
        recs_html = "<div class='grid grid-cols-1 md:grid-cols-2 gap-3 mt-2'>" + "".join(cards) + "</div>"

    warnings_html = ""
    if report.warnings:
        lis = "".join(f"<li class='text-sm'>{w}</li>" for w in report.warnings)
        warnings_html = f"""
<div class="mt-6 rounded-2xl border border-amber-200 bg-amber-50 dark:bg-amber-950/40 dark:border-amber-900 p-4">
  <div class="font-semibold text-amber-700 dark:text-amber-300 mb-1">Warnings</div>
  <ul class="list-disc pl-5 text-amber-700 dark:text-amber-200">{lis}</ul>
</div>
"""

    # Full HTML document
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>crap4code report — {s.scanned_files} files, {s.functions_found} functions</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;600&amp;display=swap');
    :root {{ --font-sans: Inter, system-ui, sans-serif; }}
    body {{ font-family: var(--font-sans); }}
    .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }}
    .metric-value {{ font-feature-settings: "tnum"; }}
    table th {{ cursor: pointer; user-select: none; }}
    table th:hover {{ background-color: #f8fafc; }}
    .dark table th:hover {{ background-color: #0f172a; }}
  </style>
</head>
<body class="bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-200">
  <div class="max-w-7xl mx-auto px-4 py-8">
    <!-- Header -->
    <div class="flex items-end justify-between mb-6">
      <div>
        <div class="flex items-center gap-3">
          <div class="text-4xl font-semibold tracking-tighter">crap4code</div>
          <div class="px-2.5 py-1 rounded-full text-xs font-medium bg-slate-900 text-white dark:bg-white dark:text-slate-900">scan</div>
        </div>
        <div class="text-slate-500 dark:text-slate-400 text-sm mt-0.5">Cyclomatic complexity • CRAP • risk analysis</div>
      </div>
      <div class="text-right text-xs text-slate-400 dark:text-slate-500 mono">
        generated {now}<br>
        threshold <span class="font-semibold text-slate-600 dark:text-slate-300">{s.threshold}</span>
      </div>
    </div>

    <!-- Top stats -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
      <div class="rounded-3xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4">
        <div class="text-xs uppercase tracking-widest text-slate-500">Files scanned</div>
        <div class="text-4xl font-semibold tabular-nums mt-1">{s.scanned_files}</div>
      </div>
      <div class="rounded-3xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4">
        <div class="text-xs uppercase tracking-widest text-slate-500">Functions analyzed</div>
        <div class="text-4xl font-semibold tabular-nums mt-1">{s.functions_found}</div>
        <div class="text-[10px] text-emerald-600 dark:text-emerald-400 mt-0.5">threshold exceeded: <span class="font-semibold">{'yes' if s.threshold_exceeded else 'no'}</span></div>
      </div>
      <div class="rounded-3xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4">
        <div class="text-xs uppercase tracking-widest text-slate-500 mb-1">Risk distribution</div>
        <div class="flex items-center gap-4 text-sm">
          <div><span class="font-bold text-red-600 dark:text-red-400">{risk_high}</span> <span class="text-xs text-slate-500">high</span></div>
          <div><span class="font-bold text-amber-600 dark:text-amber-400">{risk_mod}</span> <span class="text-xs text-slate-500">mod</span></div>
          <div><span class="font-bold text-emerald-600 dark:text-emerald-400">{risk_low}</span> <span class="text-xs text-slate-500">low</span></div>
        </div>
        <div class="mt-2 h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden flex">
          <div class="bg-red-500 h-2" style="width:{risk_high/total_funcs*100}%"></div>
          <div class="bg-amber-500 h-2" style="width:{risk_mod/total_funcs*100}%"></div>
          <div class="bg-emerald-500 h-2" style="width:{risk_low/total_funcs*100}%"></div>
        </div>
      </div>
      <div class="rounded-3xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4 flex flex-col justify-between">
        <div>
          <div class="text-xs uppercase tracking-widest text-slate-500">Languages</div>
          <div class="mt-1 flex flex-wrap gap-1">
            {''.join(f'<span class="inline-block px-2 py-px text-xs rounded bg-slate-100 dark:bg-slate-800 font-mono">{k} <span class="text-slate-400">{v}</span></span>' for k,v in sorted(s.by_language.items()))}
          </div>
        </div>
        <div class="text-[10px] text-slate-400 mt-3">Changed scan: {'yes' if s.changed_only else 'no'}{f' (base {s.base_ref})' if s.base_ref else ''}</div>
      </div>
    </div>

    <!-- Filters -->
    <div class="flex flex-col md:flex-row md:items-center gap-3 mb-3">
      <div class="flex items-center gap-2">
        <span class="text-xs uppercase font-medium tracking-widest text-slate-500">Filter risk:</span>
        <button onclick="filterRisk('all')" class="risk-filter active px-3 py-1 text-xs rounded-full border border-slate-300 dark:border-slate-700 hover:bg-white dark:hover:bg-slate-900" data-filter="all">All</button>
        <button onclick="filterRisk('high')" class="risk-filter px-3 py-1 text-xs rounded-full border border-red-200 text-red-600 hover:bg-red-50 dark:hover:bg-red-950" data-filter="high">High</button>
        <button onclick="filterRisk('moderate')" class="risk-filter px-3 py-1 text-xs rounded-full border border-amber-200 text-amber-600 hover:bg-amber-50 dark:hover:bg-amber-950" data-filter="moderate">Moderate</button>
        <button onclick="filterRisk('low')" class="risk-filter px-3 py-1 text-xs rounded-full border border-emerald-200 text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-950" data-filter="low">Low</button>
      </div>
      <div class="flex-1">
        <input id="search-input" oninput="applyFilters()" type="text" placeholder="Search file or function..." 
               class="w-full md:w-80 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-2xl px-4 py-1.5 text-sm placeholder:text-slate-400 focus:outline-none focus:border-slate-400">
      </div>
      <button onclick="resetFilters()" class="text-xs px-3 py-1.5 rounded-2xl border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800">Reset</button>
    </div>

    <!-- The table -->
    <div class="overflow-auto rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
      <table id="results-table" class="min-w-full text-sm">
        <thead class="bg-slate-50 dark:bg-slate-950 text-slate-500 text-xs uppercase tracking-wider">
          <tr>
            <th onclick="sortTable(0)" class="px-3 py-3 text-left">lang</th>
            <th onclick="sortTable(1)" class="px-3 py-3 text-left">file</th>
            <th onclick="sortTable(2)" class="px-3 py-3 text-left">function</th>
            <th onclick="sortTable(3)" class="px-3 py-3 text-right">lines</th>
            <th onclick="sortTable(4)" class="px-3 py-3 text-right">cx</th>
            <th onclick="sortTable(5)" class="px-3 py-3 text-right">cov</th>
            <th onclick="sortTable(6)" class="px-3 py-3 text-right">CRAP</th>
            <th onclick="sortTable(7)" class="px-3 py-3 text-center">risk</th>
          </tr>
        </thead>
        <tbody id="table-body" class="divide-y divide-slate-100 dark:divide-slate-800">
          {rows_html}
        </tbody>
      </table>
    </div>

    <!-- Recommendations -->
    {f'''<div class="mt-8">
      <div class="font-semibold text-lg mb-2 tracking-tight">Priority Recommendations</div>
      {recs_html}
    </div>''' if recs_html else ''}

    {warnings_html}

    <!-- Footer / actions -->
    <div class="mt-8 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 text-xs text-slate-500 dark:text-slate-400">
      <div>
        Generated by <span class="font-semibold text-slate-600 dark:text-slate-300">crap4code</span> • 
        {s.functions_found} functions across {s.scanned_files} files • 
        config: {report.run_metadata.get('config_path') or '(none)'}
      </div>
      <div class="flex items-center gap-2">
        <button onclick="downloadJson()" 
                class="px-4 py-2 rounded-2xl border border-slate-200 dark:border-slate-700 hover:bg-white dark:hover:bg-slate-900 active:bg-slate-100 text-slate-600 dark:text-slate-300 text-xs font-medium">
          Download full JSON
        </button>
        <button onclick="window.print()" 
                class="px-4 py-2 rounded-2xl border border-slate-200 dark:border-slate-700 hover:bg-white dark:hover:bg-slate-900 active:bg-slate-100 text-slate-600 dark:text-slate-300 text-xs font-medium">
          Print / Save PDF
        </button>
      </div>
    </div>
  </div>

  <!-- Embedded data for the "Download JSON" button and future extensibility -->
  <script id="report-data" type="application/json">{data_json}</script>

  <script>
    // Tailwind script run
    function initTailwind() {{
      // No extra config needed for the play CDN in most cases
    }}

    let currentFilter = 'all';
    let currentSort = {{ col: 6, dir: 'desc' }}; // default sort by CRAP desc on load

    function applyFilters() {{
      const q = (document.getElementById('search-input').value || '').toLowerCase().trim();
      const rows = document.querySelectorAll('#table-body tr');
      rows.forEach(row => {{
        const matchesRisk = currentFilter === 'all' || row.dataset.risk === currentFilter;
        const matchesSearch = !q || row.dataset.search.toLowerCase().includes(q);
        row.style.display = (matchesRisk && matchesSearch) ? '' : 'none';
      }});
    }}

    function filterRisk(risk) {{
      currentFilter = risk;
      // update active styles on buttons
      document.querySelectorAll('.risk-filter').forEach(btn => {{
        const isActive = btn.dataset.filter === risk;
        btn.classList.toggle('active', isActive);
        if (risk === 'all') {{
          btn.classList.toggle('border-slate-300', isActive);
        }}
      }});
      applyFilters();
    }}

    function resetFilters() {{
      document.getElementById('search-input').value = '';
      currentFilter = 'all';
      document.querySelectorAll('.risk-filter').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('#table-body tr').forEach(r => r.style.display = '');
    }}

    function sortTable(colIndex) {{
      const tbody = document.getElementById('table-body');
      const rows = Array.from(tbody.querySelectorAll('tr'));
      const isNumeric = [3,4,5,6].includes(colIndex); // lines, cx, cov, CRAP

      const getVal = (row) => {{
        const cell = row.children[colIndex];
        if (!cell) return '';
        let v = cell.textContent.trim();
        if (isNumeric) {{
          const n = parseFloat(v.replace('%','').replace('N/A','NaN'));
          return isNaN(n) ? -1 : n;
        }}
        return v.toLowerCase();
      }};

      const dir = (currentSort.col === colIndex && currentSort.dir === 'asc') ? 'desc' : 'asc';
      currentSort = {{ col: colIndex, dir }};

      rows.sort((a, b) => {{
        let va = getVal(a), vb = getVal(b);
        if (va < vb) return dir === 'asc' ? -1 : 1;
        if (va > vb) return dir === 'asc' ? 1 : -1;
        return 0;
      }});

      rows.forEach(r => tbody.appendChild(r));
      applyFilters(); // re-apply after reorder
    }}

    function downloadJson() {{
      const script = document.getElementById('report-data');
      const blob = new Blob([script.textContent], {{ type: 'application/json' }});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'crap4code-report.json';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }}

    // Keyboard niceties
    function initKeyboard() {{
      document.addEventListener('keydown', (e) => {{
        if (e.key === '/' && document.activeElement.tagName === 'BODY') {{
          e.preventDefault();
          document.getElementById('search-input').focus();
        }}
        if (e.key.toLowerCase() === 'escape') {{
          const si = document.getElementById('search-input');
          if (document.activeElement === si) si.blur();
          else resetFilters();
        }}
      }});
      // initial sort hint
      console.log('%c[crap4code] Click column headers to sort. Use / to focus search.', 'color:#64748b');
    }}

    function init() {{
      initTailwind();
      initKeyboard();

      // Initial sort by CRAP (column 6) descending on first paint
      // (already in DOM order from Python, but make sure)
      const tbody = document.getElementById('table-body');
      // If you want guaranteed initial sort client-side, uncomment:
      // sortTable(6);

      // Default filter = all
      const allBtn = document.querySelector('.risk-filter[data-filter="all"]');
      if (allBtn) allBtn.classList.add('active', 'border-slate-400');

      // Allow Enter in search to do nothing special
      document.getElementById('search-input').addEventListener('keydown', (e) => {{
        if (e.key === 'Enter') e.target.blur();
      }});
    }}

    window.onload = init;
  </script>
</body>
</html>"""
    return html
