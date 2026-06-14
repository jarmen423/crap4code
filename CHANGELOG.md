# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## [0.5.0] - 2026-06-14

### Added
- `--function NAME` (repeatable) on `scan`: exact function-name filter after analysis and coverage mapping. Summaries, recommendations, threshold evaluation, and exit 2 apply only to selected rows. Duplicate names across files return all matches unless narrowed with explicit source paths. No match → exit 1.
- `--coverage-report PATH`: one-off override for the configured coverage report (absolute or repo-relative). Does not mutate `.crap4code.toml`. Missing explicit path → exit 1 (no fallback to config).
- `--coverage-format {lcov,coverage.py-xml}`: override configured format with content sniff validation when used with explicit overrides.
- `--format compact`: one plain line per function (`file::function | lines=... | CX=... | coverage=... | CRAP=... | risk=...`) for shell-friendly targeted remediation after external coverage regeneration.
- `format_report_compact()` in `core/report.py`; strict coverage loading via `CoverageReportError` in `core/coverage.py`.
- Optional `run_metadata` keys: `coverage_report_override`, `coverage_format_override`, `function_filter`.
- Checked-in `tests/fixtures/python/coverage.xml` paired with `tests/fixtures/python/sample.py`.
- Expanded CLI tests for targeted workflow, rust_repo compact smoke, and `--limit` positive validation.

### Changed
- `--format` choices now include `compact`; `--limit` rejects non-positive values.
- Documented targeted remediation workflow in `README.md`, `docs/user-guide/usage.md`, `spec.md`, and `docs/contracts.md`.

### Added (carried from prior unreleased work, now released in 0.5.0)
- `--baseline <prior.json>` flag on `scan`. Loads a previous `--format json` report, filters the result set to only functions that existed in it, attaches `baseline_crap_score` / `baseline_coverage_percent` snapshots on the matching rows, and records `baseline_path` + `baseline_matched` in the summary / run_metadata. Rich TUI and self-contained HTML render deltas in the CRAP column. Composes with explicit paths, `--changed`, `--report-only`, and the new targeted flags.

## [0.4.0] - 2026-06-08

**This is the release completing the full Windows & Cross-Platform Usability Plan (Phases 0-3).** All major improvements from the plan are included. See `WINDOWS_AND_CROSS_PLATFORM_PLAN.md` (the "Phase 3 Merge & Verification + Cleanup" section and prior merge sections) for the complete history, verification commands, and audit trail (patches under `review/`). Core guarantees remain unchanged: missing coverage is always `indeterminate` (never invented), recommendations are deterministic/auditable, parser-backed language support for JS/TS/Rust, and repo-local config is the source of truth.

### Added
- `python -m crap4code` (and all subcommands: `--version`, `init`, `scan`, etc.) now works identically to the installed `crap4code` / `crap4code.exe` console script. New minimal `src/crap4code/__main__.py` provides the standard Python cross-platform entry point. (Phase 0, Issue C1; full module docstring + delegation chain documented per project "Teach Through Code" standards.)
- Top-level `-V` / `--version` flag (e.g. `crap4code --version` or `crap4code -V`). Uses the single source of truth `__version__` from `crap4code/__init__.py`. Works at bare invocation before any subcommand. Updated `spec.md` (CLI contract). (Phase 0, Issue C2.)
- CI "minimal-install-verify" job (runs on ubuntu-latest but exercises real missing grammars): after full `[dev]` install, uninstalls `tree-sitter-javascript`/`tree-sitter-typescript`/`tree-sitter-rust`; asserts registry contains only `["python"]`; confirms `crap4code scan --lang python --report-only` succeeds in a temp project; confirms `--lang rust` fails gracefully (exit 1, message contains "Rust support requires `pip install tree-sitter-rust`"). (Phase 3, Dev4.)
- Expanded release checklist (`docs/release-checklist.md`) with dedicated "Cross-Platform / Windows Verification (phase3-ci / Dev4)" section: minimal/python-only install sim, case tests, graceful lang loading, E2 non-git --changed warning, fresh Windows checkout verification steps. (Phase 3.)
- Pytest DX guard in `tests/conftest.py` (stdlib-only, ~40 LOC): makes the canonical dev commands `python -m pip install -e .[dev] && python -m pytest -q` and plain `python -m pytest -q` (even pre-install on a fresh clone) reliably succeed from repo root on **pwsh, cmd, bash, zsh** etc. with **no manual `PYTHONPATH`** setting. The guard is conditional (only acts on `ImportError`), test-only, and fully compatible with lazy registry / python-only sims. Exhaustive module docstring + cross-references to plan/AGENTS/README/pyproject. (Phase 3, Dev1 / phase3-dx.)
- Rich, actionable diagnostics when a `coverage_command` fails: now includes the platform shell actually used (`ComSpec` / cmd.exe on Windows even if you launched from pwsh; platform default on POSIX), the exact command string, cwd, return code, plus hints. Failures in CLI surface a prefixed block + paragraph. (Phase 1, Issues S1/S2.)
- Warning emission (visible in table summary, JSON `warnings`, and stderr) the first time a case-insensitive fallback match is used during coverage mapping. (Phase 1, R1.)
- Graceful handling + clear message when `--lang <unavailable>` is requested after lazy loading (or in a minimal install). (Phase 1/2, D3 + registry work.)
- Helpful warnings for `--changed` / `--base-ref` when git is unavailable or the cwd is not a git repository (including the common "E2" non-git temp dir case on Windows CI). Warning text: "git not available or not a repository — --changed flag had no effect" (plus bounded `(git stderr: ...)` when available). Warnings flow to `ScanReport.warnings` and are printed to stderr even on the "No matching source files found." early-exit path. New tests (`test_changed_flag_in_non_git_dir_emits_warning` and base-ref variant in `tests/test_cli.py`). (Phase 2, Issue E2.)
- More tolerant `cleanup_artifacts` (used before running coverage commands): now uses `shutil.rmtree(..., onerror=...)` for dirs and wrapped unlinks for files; collects warnings instead of raising. Prevents scan aborts on Windows due to in-use/readonly `.coverage` files, permission issues, etc. Warnings surface in the report. (Phase 1, Issue E1.)
- Case-insensitive filesystem support for coverage mapping (R1): `CoverageDatabase.coverage_for` now performs a case-folded fallback search (on win32 and when needed) so a source discovered as `Src/Foo.py` correctly matches a report entry `src/foo.py` (and vice versa). Exact-match remains preferred; a warning is emitted on fallback. Synthetic test `test_coverage_for_case_insensitive_fallback`. Paths in output/JSON remain the normalized POSIX-style originals. (Phase 1, R1.)
- Hygiene / repo cleanliness (Phase 0 + Dev3): aggressive `.gitignore` updates (qdrant_storage/, .agentic-memory/, .planning/, .cursor/, .claude/, build/, dist/, etc.); removal of stale `src/crap4code/analyzers/` tree (and other committed junk from prior planning). Cleaner clones, `git status`, and `--changed` behavior.
- Additional root-level diagnostic scripts for Windows users (`win_probe.py`, `verify_tree_sitter_windows.py`) to inspect tree-sitter wheel state, imports, and analyzer behavior on their machine.
- Consistent first-class `warnings` collection and propagation across git, coverage, language availability, case mapping, config, etc. (Phases 1-2, E3/R3/etc.)

### Changed
- **Lazy / tolerant tree-sitter grammar loading (the biggest install-time reliability win for Windows and minimal setups)**: Grammar imports (`tree_sitter_javascript`, `tree_sitter_typescript`, `tree_sitter_rust`) moved out of module top-level into `JavaScriptFamilyAnalyzer.__init__` / `RustAnalyzer.__init__`. The registry (`languages/registry.py`) now wraps instantiation in `try/except ImportError` (and similar for the language filter in CLI). `get_language_registry()` returns only the languages whose grammars successfully loaded at runtime (Python is always present via stdlib `ast`; it has no tree-sitter dep). Importing `crap4code` (or running `crap4code scan --lang python`) no longer hard-fails if any one of the JS/TS/Rust wheels is missing or incompatible. Clear per-language messages for requested unavailable languages. Full end-to-end verified in minimal sims (CI job + manual + release checklist). Detailed docstrings in registry.py, analyzer.py files, and cli.py. (Phase 1, Issues D1 + D3; also P1 groundwork.)
- Dev/test commands and cross-shell reliability now documented as first-class in multiple places (README "Development" section with pwsh/cmd and POSIX examples + "Why ... now just works" subsection; AGENTS.md; pyproject.toml `[tool.pytest.ini_options]` comments; `tests/conftest.py` module docstring). The `pythonpath = ["src"]` entry is retained for compatibility; the new guard is the belt-and-suspenders. (Phase 3, Dev1.)
- README extensively expanded with a practical "Windows and Cross-Platform Notes" section (tree-sitter wheel realities/risks/limitations, Coverage Commands on Windows (Shell Model), Case-Insensitive Filesystem Risk for Coverage Mapping, PATH/venv/Launch Environment, Other notes). Quickstarts, install, and examples now show pwsh/cmd alongside bash. References the plan document as the source of truth. (Phase 1, Doc1/Doc2/Doc3.)
- `crap4code init` sample (from `sample_config_text()` in `core/config.py`) now contains a large, authoritative "COVERAGE COMMAND SHELL MODEL (cross-platform reality)" comment block plus practical advice, `python -m` recommendations, `&&` notes, --report-only guidance, and Windows-specific warnings. This is the primary durable docs for the `shell=True` execution model. (Phase 1, Doc1.)
- CI workflow (`.github/workflows/ci.yml`): the existing test matrix (ubuntu + windows-latest, all supported Pythons) now additionally runs targeted case-mismatch tests, phase1/2 cross-platform tests (`unavailable_lang`, `no_files_found`, `changed_flag_in_non_git_dir_emits_warning`), and a conditional windows E2 git-warning verification. New dedicated lightweight `minimal-install-verify` job (see Added). (Phase 3, Dev4.)
- Internal path handling: all repo-relative and output paths continue to use POSIX `/` (via `.as_posix()`) for stable JSON/reports/recommendations across OSes. `normalize_repo_path` and coverage lookup updated for case fallback while preserving original casing for display.
- Warning surfacing: many more paths (git, case, lang availability, cleanup, config parse) now feed into the existing `warnings` list → `build_report` → `ScanReport` (JSON + table) + stderr print in CLI. The no-files path was specially updated to still emit git warnings. (Phases 1-2.)
- AGENTS.md, README, and plan now cross-reference each other for the full story on Dev1 (pytest DX) + phase3-dx.

### Fixed
- `python -m crap4code` previously raised "No module named crap4code.__main__". Now succeeds and is the documented portable invocation form (works before/after install, on all shells, no PATH surprises). (C1)
- Coverage mapping on case-insensitive filesystems (Windows primary, some macOS) could produce silent `indeterminate` coverage (and thus N/A CRAP) when the casing of a path in the coverage report differed from the casing discovered by walking the source tree (e.g. `Src/Foo.py` vs `src/foo.py` from lcov or coverage.xml). Now resolved via case-fold fallback + warning while still obeying "never invent data". (R1)
- `cleanup_artifacts` could raise (crashing the entire scan) on Windows when `.coverage` or other stale artifacts were locked/in-use/readonly (common with certain pytest plugins or concurrent processes). Now robust and warning-based. (E1)
- `--changed` (and `--base-ref`) previously failed silently (scanned nothing or everything) outside a git repo / without git on PATH. Now emits a clear, actionable warning visible to humans and agents. (E2; includes the exact test scenario used in CI on windows-latest.)
- Top-level package import (and thus `crap4code scan --lang python`) previously required *all* tree-sitter grammar packages even if you only cared about Python. Individual grammar failures are now isolated; only the affected language is unavailable. (D1)
- Dev experience friction: `python -m pytest` (and the install-then-test sequence) from repo root frequently required shell-specific `PYTHONPATH=src` incantations on Windows (pwsh/cmd) even after `pip install -e .[dev]`, due to src-layout + editable install realities. Eliminated by the guarded conftest (works pre- and post-install, on all shells). (Dev1)
- Various minor robustness / observability gaps around git, unparsable files, language availability, and subprocess context that were catalogued in the plan (see sections 3.x for the full inventory).

### Documentation
- `WINDOWS_AND_CROSS_PLATFORM_PLAN.md`: living document; top status line, full phased roadmap (0-4), success criteria, detailed issue inventory (D/R/S/C/E/Doc/Dev/P), implementation notes, two coordinator "Merge & Verification + Cleanup" sections (with exact git commands, worktree paths, reconciliation choices, verification command transcripts, and final green status), plus cleanup notes. Patches for all landed work preserved under `review/`.
- README.md: new Windows/cross-platform section (with honest limitations + mitigations), expanded Development section (cross-shell commands + rationale), Release Flow, Install/Quick Start examples for pwsh/cmd, references to the plan and generated config comments.
- `docs/release-checklist.md`: new Cross-Platform / Windows Verification section with concrete commands matching the plan's Dev4/minimal/CI expectations.
- `AGENTS.md`: updated Primary Commands + Important Project Rules with cross-shell notes and references to conftest/plan/README for the Dev1 story.
- `spec.md`: documented the new top-level `--version` / `-V`.
- `pyproject.toml`: extensive comments under `[tool.pytest.ini_options]` explaining the history of Dev1, why the guard was added, how it interacts with the existing pythonpath entry, and verification commands.
- All new and heavily-changed modules (`__main__.py`, `tests/conftest.py`, `languages/registry.py`, `languages/*/analyzer.py`, `core/coverage.py`, `core/git_changed.py`, `core/files.py`, `cli.py`, `core/config.py`, etc.) contain structured module docstrings, public function/class docstrings (Google-style where Python), and targeted inline comments explaining purpose, cross-platform rationale, side effects, integration points, and "why this change" (per AGENTS.md "Teach Through Code" + Structured Documentation Standard). Future agents or contributors can open the files and understand the work without chat history.
- Added root probe scripts with their own documentation for on-machine Windows tree-sitter diagnosis.

See also the checked-in sample projects under `tests/sample_projects/` (still used for release-readiness) and `tests/test_sample_projects.py`.

**Prior release (v0.3.0)**: Initial multi-language CRAP v1 implementation (Python/JS/TS/Rust analyzers, coverage mapping for XML+LCOV, CRAP scoring + deterministic recs, CLI with `--changed`/`--report-only`/`--format json`, repo-local TOML config, CI/release scaffolding, sample projects). The 0.4.0 release focuses on making that foundation pleasant and reliable on Windows and across shells/CI/install scenarios.

---

*For the full context behind every item above, read `WINDOWS_AND_CROSS_PLATFORM_PLAN.md`. The plan was the single source of truth; this changelog is the user-facing summary.*
