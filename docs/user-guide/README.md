# crap4code User Guide

This user guide provides organized, durable explanations for using `crap4code`, a Python-hosted CLI for measuring cyclomatic complexity, function-level coverage, CRAP scores, and deterministic next-step recommendations.

It is designed for both humans (returning after months away) and coding agents. All explanations are self-contained where possible, reference the actual codebase for "teach through code," and follow the project's structured documentation and scannability standards (hierarchical outlines with bullets).

## Table of Contents

This guide uses a small set of focused sibling pages. They follow a recommended reading order and provide **hierarchical navigation** (bullets + numbered steps inside) plus cross-links to each other and to root-level docs.

Use the list below to jump; every page also contains "Next" / "See also" pointers back to siblings and to `README.md` (root), `spec.md`, `docs/contracts.md`, etc.

1. **[Getting Started](./getting-started.md)** — first-time setup, typical 2-month-later reminder workflow.
2. **[Configuration](./configuration.md)** — `.crap4code.toml` in depth (paths, coverage settings, shell model notes).
3. **[Concepts](./concepts.md)** — CRAP formula, coverage reports vs. formats, paths meaning, "no matching source files", warnings, indeterminate coverage, two-phase flow, design ties.
4. **[Usage](./usage.md)** — commands, CLI options (`--report-only`, `--changed`, `--format json`, etc.), cross-platform examples, basic + advanced workflows.
5. **[Troubleshooting](./troubleshooting.md)** — common issues (no files found, coverage warnings, workspace layouts, case sensitivity, shell surprises) with why they happen and how the design handles them.

**Back-links from this index (repo-root relative paths for the core references):**

- `README.md` (root) — quick start, install, Windows notes, output overview, development commands.
- `spec.md` — product goal, primary workflow, CLI contract, coverage contract, shared function fields, output contract.
- `docs/contracts.md` — language support, coverage states (`measured` / `indeterminate`), risk levels, recommendation rules (deterministic order).
- `docs/release-checklist.md` — pre-release verification, tagging, CI (reference only for release context).
- `AGENTS.md` and source files (for "teach through code" details).

(The detailed version of the above lives in the Scope section below; the list here serves as the primary hierarchical TOC for quick navigation.)

## Scope and Cross-References

- **Do not duplicate** full project history, the entire Windows/cross-platform plan, or release processes here. Those live in:
  - `README.md` (root) — quick start, install, Windows notes, output overview, development commands.
  - `spec.md` — product goal, primary workflow, CLI contract, coverage contract, shared function fields, output contract.
  - `docs/contracts.md` — language support, coverage states (`measured` / `indeterminate`), risk levels, recommendation rules (deterministic order).
  - `docs/release-checklist.md` — pre-release verification, tagging, CI (reference only for release context).
  - `WINDOWS_AND_CROSS_PLATFORM_PLAN.md` — full issue inventory and phased work (reference for context on guarantees and shell model).
  - `src/crap4code/core/config.py` — `sample_config_text()` (the authoritative, heavily-commented TOML that `crap4code init` writes).
- **Core guarantees** (repeated for durability; also in `AGENTS.md`, `docs/contracts.md`, `README.md`):
  - Missing coverage must stay `indeterminate`; the tool **never invents** a CRAP score.
  - Recommendations are deterministic and auditable (rule-based, not LLM-generated).
  - Parser-backed language support is required for JavaScript, TypeScript, and Rust (Python uses stdlib `ast`).
  - Repo-local `.crap4code.toml` (next to your source tree) is the single source of truth for paths, coverage commands, and report locations.
- **Project overview** (compiled from `spec.md`, `README.md`, contracts):
  - Helps reduce change risk in Python, JS/TS, Rust repos.
  - Measures: cyclomatic complexity + function-level coverage → CRAP + ranked risky functions + next-step guidance.
  - Operator model inspired by unclebob/crap4clj and crap4java: simple CLI, explicit/auditable coverage refresh, threshold-based exits for CI/agent loops.
  - Exit codes: `0` (success), `1` (CLI error or coverage command failure), `2` (threshold exceeded by any *measured* CRAP).

## Guide Structure (Table of Contents)

See the hierarchical Table of Contents (with sibling links + back-links) near the top of this page. The list below uses absolute repo-relative paths for clarity from anywhere in the repo (Scope section expands the cross-references).

- [docs/user-guide/getting-started.md](docs/user-guide/getting-started.md) — first-time setup, typical 2-month-later reminder workflow.
- [docs/user-guide/configuration.md](docs/user-guide/configuration.md) — `.crap4code.toml` in depth (paths, coverage settings, shell model notes).
- [docs/user-guide/concepts.md](docs/user-guide/concepts.md) — CRAP formula, coverage reports vs. formats, paths meaning, "no matching source files", warnings, indeterminate coverage, two-phase flow, design ties.
- [docs/user-guide/usage.md](docs/user-guide/usage.md) — commands, CLI options (`--report-only`, `--changed`, `--format json`, etc.), cross-platform examples, basic + advanced workflows.
- [docs/user-guide/troubleshooting.md](docs/user-guide/troubleshooting.md) — common issues (no files found, coverage warnings, workspace layouts, case sensitivity, shell surprises) with why they happen and how the design handles them.

## High-Level How It Works (Flow)

See `spec.md` "Primary Workflow" and `src/crap4code/cli.py` (`_scan`) for the implementation.

1. **Discovery** (`src/crap4code/core/files.py:discover_source_files`): Walk configured or explicit paths; filter by language extensions (recursive for dirs). Optionally intersect with git-changed files.
2. **Optional coverage refresh** (only if `coverage_command` present and not `--report-only`): Cleanup stale artifacts, then `subprocess.run(..., shell=True)` of the exact string from TOML (see `src/crap4code/core/coverage.py` and the header comments in the generated `.crap4code.toml`).
3. **Static analysis** (two-phase): Language adapters (parsers in `src/crap4code/languages/*/`) produce per-function ranges + cyclomatic complexity. See `src/crap4code/languages/python/analyzer.py` (AST visitor) and equivalent tree-sitter-based JS/TS/Rust for details.
4. **Coverage mapping** (`src/crap4code/core/coverage.py:CoverageDatabase.coverage_for` + `_apply_coverage` in cli): Load report (if `coverage_report` + `coverage_format` configured and file exists); map line hits onto the exact function line ranges from step 3. Uses normalized POSIX repo-relative keys.
5. **Scoring**: CRAP only when coverage state is `measured` (see formula in concepts). Risk + recommendations populated deterministically (`src/crap4code/core/recommendations.py:enrich_rows`).
6. **Output + exit**: Table (human, risk-sorted) or JSON (stable keys for agents/CI); print warnings to stderr; exit 2 if any measured CRAP > threshold.

Warnings (from git, coverage mapping, cleanup, config) are always collected and surfaced (in `ScanReport.warnings`, stderr, and JSON) — they are informational, not fatal (see `cli.py` and `core/report.py`).

## Next Steps

Run `crap4code init` (or with `--force`) in a project root to materialize the sample config. The comments inside the generated file are primary durable docs for the coverage execution model.

For the code itself as teaching surface: start with the files referenced above (all have module docstrings and targeted comments per the "Teach Through Code" standard in `AGENTS.md`).

See root `README.md` "Quick Start" and "Config" sections to get running immediately, then return here for deeper "why" and "what if".
