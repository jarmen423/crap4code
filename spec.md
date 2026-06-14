# crap4code Spec

## Product Goal

A small, auditable CLI that computes per-function CRAP scores (Change Risk Anti-Patterns) from complexity + trustworthy coverage, surfaces risky functions, and emits deterministic recommendations. Primary consumers: humans doing risk assessment and agents/CI that need stable JSON + clear exit codes.

## Primary Workflow (the "two phase" model)

1. Discover source files (by configured paths + extensions for the requested languages).
2. (Optional but recommended for real CRAP) Run the user's `coverage_command` (if present and not `--report-only`), producing a report artifact.
3. Parse each discovered file with the appropriate language analyzer to extract function/method ranges + cyclomatic complexity.
4. Load the coverage report (if configured + present) and map line-hit data onto the exact function ranges.
5. For every function that had trustworthy coverage data, compute CRAP; always compute risk + recommendations.
6. Emit table (sorted by risk) or JSON; exit 2 if any *measured* CRAP exceeds threshold.

Warnings are collected throughout and always emitted (to stderr + in JSON `warnings`); they are informational.

## CLI Contract

`crap4code [global-options] <command> [command-options]`

Global:

- `-h/--help`
- `-V/--version`
- `--config <path>` (default: `.crap4code.toml` next to cwd or walk up)

Commands:

- `init [--force] [--config <path>]`
- `scan [paths...] [--lang <lang>] [--changed] [--base-ref <git-ref>] [--format {table,json,html,compact}] [--threshold <float>] [--config <path>] [--report-only] [--baseline <prior.json>] [--function NAME] [--coverage-report PATH] [--coverage-format {lcov,coverage.py-xml}] [--limit N] [--full] [--output FILE]`

Supported flags:

- `--lang <python|javascript|typescript|rust>` (single value; default: all enabled languages)
- `--changed` (intersect discovered files with git diff vs base)
- `--base-ref <git-ref>`
- `--format {table,json,html,compact}`
- `--threshold <float>`
- `--config <path>`
- `--report-only`
- `--baseline <prior.json>` — filter output + attach deltas for exactly the functions present in a previous JSON report (the "just the parts you worked on vs baseline" workflow). See docs/user-guide/usage.md.
- `--function NAME` (repeatable) — exact `function_name` match after analysis and coverage mapping. When the same name appears in multiple files, all matches are included; pass an explicit source path to disambiguate. Exit 1 when no match. Summaries, recommendations, threshold, and exit 2 apply only to selected rows.
- `--coverage-report PATH` — override configured report path for this scan (absolute or repo-relative). Does not mutate TOML. Missing explicit path → exit 1 (no fallback to config).
- `--coverage-format {lcov,coverage.py-xml}` — override configured format; validated against the report file when combined with `--coverage-report` or when overriding format alone.
- `--limit N` — positive integer; rich table truncation only (ignored for compact).
- `--full` — show all functions in rich table.
- `--output FILE` — write report; `.html`/`.json` infer format when `--format` omitted.

## Coverage Contract

- Python coverage input: `coverage.py` XML
- JavaScript / TypeScript coverage input: LCOV
- Rust coverage input: LCOV
- Missing or unmappable coverage is `indeterminate`
- Indeterminate coverage never produces a fake CRAP score
- See `docs/user-guide/concepts.md` for user-friendly explanations of coverage reports, formats, indeterminate coverage, and the mapping process.

## Shared Function Contract

Each function row includes:

- `language`
- `file_path`
- `container`
- `function_name`
- `start_line`
- `end_line`
- `complexity`
- `coverage_percent`
- `coverage_state`
- `crap_score`
- `risk_level`
- `recommended_actions`
- (optional, only with `--baseline`) `baseline_crap_score`, `baseline_coverage_percent`

## Output Contract (table)

Human table is risk-sorted (high risk first). Columns are stable. `coverage` and `crap` show `N/A` + warning when `indeterminate`.

## Output Contract (compact)

One plain line per function (no Rich, summary, recommendations, or ANSI on stdout):

`file::function | lines=START-END | CX=N | coverage=N.N% | CRAP=N.NN | risk=LEVEL`

Use `coverage=N/A` and `CRAP=N/A` when indeterminate. Warnings remain on stderr.

## Output Contract (json)

Stable top-level keys for agents:

- `summary`
- `functions[]`
- `recommendations[]`
- `run_metadata`
- `warnings[]`

Exit codes:

- 0: success (all measured CRAP <= threshold in the filtered result set, or no measured functions)
- 1: CLI error, coverage command failed, `--function` no match, or invalid/missing explicit `--coverage-report` / format mismatch
- 2: one or more *measured* functions in the filtered result set exceeded threshold

See `src/crap4code/cli.py`, `core/report.py`, `core/models.py`, `core/recommendations.py`, `core/coverage.py`, and the language analyzers for the implementation.
