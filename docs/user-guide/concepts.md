# Concepts

This page explains the mental model, data flow, and design decisions so that a user (or future agent) can understand output, warnings, and configuration choices without chat history. It is compiled from the implementation (`src/crap4code/...`), `spec.md`, `docs/contracts.md`, root `README.md`, and `AGENTS.md`.

Cross-reference: `docs/contracts.md` for the formal states, risk levels, and recommendation ordering. `spec.md` for the shared function contract and output shape.

## Project Overview and Why It Exists

`crap4code` produces a verifiable, auditable picture of change risk:

- Cyclomatic complexity per function (parser-based for JS/TS/Rust; stdlib `ast` for Python).
- Function-level coverage mapped onto the exact ranges the parser reported.
- CRAP score (only when coverage data is trustworthy).
- Risk bucket + ordered, deterministic next-step recommendations.
- Machine-readable JSON + human table, plus threshold-based exit code for CI/agent use.

Core product guarantees (enforced throughout the code and repeated in `AGENTS.md`, contracts, README, and plan):

- Missing or untrustworthy coverage → `indeterminate` (never synthesize a percentage or CRAP).
- Recommendations are deterministic rule-based (see `src/crap4code/core/recommendations.py`); order is stable for agents and test assertions.
- Repo-local `.crap4code.toml` is the source of truth.
- Non-Python languages require real parser (tree-sitter) support — no regex or "best effort" text scanning.

It is intentionally *not* a coverage tool itself. It consumes a coverage "receipt" produced by your test runner / coverage runner.

## The CRAP Formula (Briefly)

Defined in `src/crap4code/core/crap_score.py`:

```python
def calculate_crap(complexity: int, coverage_ratio: float | None) -> float | None:
    if coverage_ratio is None:
        return None
    cc = float(complexity)
    uncovered = 1.0 - coverage_ratio
    return (cc * cc * (uncovered ** 3)) + cc
```

- Only called when coverage state is `measured` (a real percentage was obtained for the function's line range).
- Higher complexity + higher fraction uncovered → CRAP grows quickly (the cubic term on uncovered is the "risk amplifier").
- Result is a float (shown with 2 decimals in table output; `N/A` when `None`).
- Threshold default is 8.0 (see `src/crap4code/core/thresholds.py`); any *measured* CRAP > threshold → exit code 2.
- When coverage is indeterminate the risk level and recommendations fall back to complexity-only rules (see below).

The formula is the classic CRAP metric (Change Risk Anti-Patterns) adapted for this tool.

## Two-Phase Analysis

1. **Static phase (complexity + function ranges)**:
   - Language adapter's `analyze(root, files)` walks each file with a parser.
   - Produces `FunctionMetrics` rows with `start_line`, `end_line`, `complexity`, container, name, etc.
   - Python: stdlib `ast` + custom `NodeVisitor` that counts decision nodes, BoolOp arity, comprehensions, while skipping nested functions/classes (see `src/crap4code/languages/python/analyzer.py`).
   - JS/TS/Rust: tree-sitter grammars (grammar imports deliberately moved inside analyzer `__init__` for lazy/tolerant loading — `src/crap4code/languages/registry.py` and the per-language analyzer files).
   - All paths normalized to POSIX repo-relative via `normalize_repo_path`.

2. **Mapping phase (coverage onto ranges)**:
   - If a report + format are configured and the file exists, `load_coverage_database` builds a `CoverageDatabase` (line-hit dicts per normalized file).
   - For each function row, `coverage_for(file_path, start, end)` does:
     - Exact lookup by normalized key.
     - On miss: case-fold fallback search (with warning recorded the first time a pair is used). This addresses Windows (and some macOS) case-insensitive filesystem realities.
     - Then intersect the function's line range with the hit lines; if any instrumented lines fall in the range, compute percentage of those lines that were hit at least once.
     - If file unknown, or range contains zero instrumented lines in the report → `("indeterminate", None)`.
   - Only after a successful measured mapping is `calculate_crap` called.
   - See `src/crap4code/core/coverage.py:CoverageDatabase`, `load_coverage_database`, `_parse_*`, `coverage_for`, and `_apply_coverage` in `cli.py`.

The separation is deliberate: parsers give trustworthy ranges; coverage tools give trustworthy execution data; the tool only combines them when both sides align exactly (or via the explicit, warned case-fold).

## Coverage Reports — What They Are

A coverage report is a side-effect artifact produced by your test/CI tooling (e.g. `coverage.xml` from `coverage.py`, `lcov.info` from `cargo-llvm-cov`, `nyc`, etc.). It records, for source files the coverage tool instrumented:

- Which lines (or branches) were executed at least once during the test run.
- It is a "receipt," not a live measurement performed by crap4code.

Why needed for real CRAP:

- Complexity alone tells you "this function has many branches."
- Without execution data you cannot know whether those branches were ever exercised by tests.
- CRAP combines the two so you can prioritize "complex *and* poorly tested."

Without a usable report:

- You still get every function, its complexity, a complexity-only risk level, and deterministic recommendations (including the reminder "Coverage is indeterminate. Configure or generate a coverage report before trusting CRAP.").
- `coverage_percent` = `None`, `crap_score` = `None`, `coverage_state` = `"indeterminate"`.
- Table shows "N/A" for coverage and crap.
- This is **by design** (see contracts: "Missing or unmappable coverage is `indeterminate`"; "Indeterminate coverage never produces a fake CRAP score").

## Coverage Formats — The "Language" of the Report File

Specified via `coverage_format` in the TOML (per language). This selects the parser inside `load_coverage_database`:

- `"coverage.py-xml"`: `coverage.py` XML report (Python projects). Parsed via `xml.etree.ElementTree` looking for `<class filename="...">` + `<line number="..." hits="...">`.
- `"lcov"`: LCOV text format (common for Rust via llvm-cov/tarpaulin, JS/TS via nyc/istanbul, etc.). Parsed by looking for `SF:` (source file) and `DA:line,hits` records.

Example tiny LCOV snippet (from `tests/sample_projects/rust_repo/coverage/lcov.info`):

```
SF:src/sample.rs
DA:1,1
DA:2,0
...
end_of_record
```

The `coverage_report` value is the path to this file. Both keys must be present for the tool to attempt loading; otherwise the database is `None` and everything stays indeterminate.

If the configured report path does not exist at scan time, or the format is unknown, or mapping produces no hits for any function → warning is emitted (see below) and state remains indeterminate. The scan itself succeeds (exit 0 or 2 only on measured CRAP).

## "No Matching Source Files Found."

Printed by `cli.py` when, after walking all candidate roots (explicit CLI paths or config `paths` / `default_paths`) and filtering by language extensions, the final set is empty. Then returns exit code 0.

This is **normal and not an error**. Common causes:

- Running from repo root when config still has `default_paths = ["src"]` but your sources live at `.` or `crates/`.
- Using `--changed` outside a git repo or with a base ref that yields no intersection (git warnings will also be emitted on stderr in this path).
- Explicitly passing a directory that contains no files with the expected suffix for the selected language(s).
- All files were filtered out by the changed-only logic.

The message is informational. Warnings collected during discovery (especially git-related) are still printed to stderr even on this early-exit path (phase2 E2 improvement).

Fix: edit `paths` in `.crap4code.toml` or pass explicit paths on the CLI (e.g. `crap4code scan . --lang rust`).

See `src/crap4code/core/files.py` and the special handling at the end of `_scan` in `cli.py`.

## Warnings — Informational, Collected, Auditable

Warnings are a first-class list accumulated across:

- Config parse problems.
- Git/changed discovery failures (e.g. "git not available or not a repository — --changed flag had no effect (git stderr: ...)").
- Coverage report "not available or could not be mapped".
- Case-insensitive coverage path fallback used.
- Stale artifact cleanup problems (individual files or rmtree onerror).

They appear in three places:

- Inside the `ScanReport` (JSON under `"warnings"`, and the table summary header does not hide them).
- Printed to stderr after the main table/JSON output (or even on the "no files" path).
- Passed through `build_report` (see `src/crap4code/core/report.py`).

They are **never fatal** to the scan (the design favors observability and "continue with what you have" over hard failure). This is why a coverage misconfiguration produces a warning + indeterminate rows rather than exit 1.

See contracts: risk classification "favors measured CRAP when available and falls back to complexity-only severity when coverage is indeterminate."

## Indeterminate Coverage — Why the State Exists

From `docs/contracts.md`:

- `measured`: the configured report covered at least one instrumented line in the function range.
- `indeterminate`: no trustworthy function-range mapping was available.

Reasons a function ends up indeterminate (even when a report file was present):

- The report did not mention the file at all (after normalization).
- The function's line range contained zero lines that the coverage tool had instrumented (common for very small functions or header-only constructs).
- Case mismatch on a case-insensitive filesystem and the fallback did not (or has not yet) apply.
- Report format/path not configured.

The state is carried on every `FunctionMetrics` row (`coverage_state` defaults to `"indeterminate"`). It drives:

- Whether `crap_score` is computed.
- The text of the first recommendation (the "configure coverage" reminder).
- Risk fallback in `classify_risk`.
- Display ("N/A").

This is a core guarantee, not a bug or missing feature. The tool refuses to pretend it has data it does not.

## Risk Levels and Recommendations (Rule-Based)

See full rules in `src/crap4code/core/recommendations.py` and `docs/contracts.md`:

- Risk prefers measured CRAP when present (>30 high, >8 moderate, else low); otherwise uses complexity thresholds (≥12 high, ≥6 moderate).
- Recommendations are appended in a fixed order (coverage guidance first, then testing, then complexity reduction, then prioritization). The list for the top 10 risky functions is included in both table-adjacent output and the JSON `recommendations` array.
- Deterministic and stable across runs on the same inputs.

## Output Contracts (Summary)

- Table: header summary line + aligned columns, sorted by measured CRAP desc then complexity desc.
- JSON: stable top-level `{"summary": {...}, "functions": [...], "recommendations": [...], "run_metadata": {...}, "warnings": [...]}` (see `spec.md` and `models.py:ScanReport.to_dict`).
- `run_metadata` includes the exact coverage commands that were executed (if any) and the config path used — great for audit.

## Design Ties (Why Warnings Are Informational, Why Paths Are Directories, etc.)

- "Never invent data" → coverage mapping is strict (exact or explicitly-warned fallback) → many rows stay indeterminate until the user configures the right report + paths.
- "Deterministic and auditable for agents/CI" → rule-based recs, stable sort keys, warnings collected rather than logged to random places, repo-local TOML, JSON with full provenance.
- "Explicit coverage refresh" → `coverage_command` is opt-in and skipped by `--report-only`; cleanup is best-effort.
- Windows/cross-platform honesty → shell model is documented in the generated config (not hidden), case handling is explicit + warned, discovery normalizes paths uniformly.
- See `WINDOWS_AND_CROSS_PLATFORM_PLAN.md` sections on R1 (case), S1/S2 (shell diagnostics), E2 (git warnings), Doc1/Doc2 for the history that produced the current observable behavior.

For the exact data shapes passed between phases, open `src/crap4code/core/models.py` (the docstring on `FunctionMetrics` is an excellent durable summary of the contract).

This concepts page plus the generated `.crap4code.toml` comments plus the referenced source files should let a future reader reconstruct the full picture without prior conversation.
