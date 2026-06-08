# crap4code

`crap4code` is a Python-hosted CRAP analyzer for Python, JavaScript, TypeScript, and Rust.

It is designed for both humans and coding agents that need a verifiable way to:

- measure cyclomatic complexity
- map coverage onto real function ranges
- compute CRAP scores where coverage is trustworthy
- rank risky functions
- get deterministic recommendations about where to add tests or simplify code

The operator model intentionally leans toward `unclebob/crap4clj` and `unclebob/crap4java`:

- keep the CLI simple
- make coverage refresh explicit and auditable
- treat missing coverage as indeterminate, not as fake precision
- use threshold-based exits for CI and agent loops

## Install

```bash
python -m pip install -e .[dev]
```

The same command works on Windows (cmd / pwsh), macOS, and Linux. After installation you get a `crap4code` console script. You can also invoke portably with:

```powershell
# Windows PowerShell or cmd
python -m crap4code.main init
python -m crap4code.main scan --report-only
```

```bash
# POSIX shells
python -m crap4code.main init
python -m crap4code.main scan --report-only
```

## Quick Start

Write a sample config (safe: refuses to overwrite unless you pass `--force`):

```powershell
# Windows
crap4code init
# or
crap4code init --force --config .crap4code.toml
```

```bash
# POSIX
crap4code init
```

Scan with table output (human readable, sorted by risk):

```bash
crap4code scan
crap4code scan --lang python
crap4code scan --lang typescript --changed --base-ref origin/main
```

Scan with machine-readable JSON (for agents / CI):

```bash
crap4code scan --format json
```

Read an existing report without re-running any coverage commands (very useful on Windows while tuning):

```bash
crap4code scan --report-only
```

## Config

`crap4code` looks for a repo-local `.crap4code.toml` by default (next to your source tree). This is the single source of truth for paths, coverage commands, and report locations. Repo-local config makes behavior easy for humans *and* coding agents to audit in CI or agent loops.

Each language section can define:

- `paths`
- `coverage_command`
- `coverage_report`
- `coverage_format`
- `stale_artifacts`

Coverage strategy (deterministic, no invention of data):

- if `coverage_command` is configured and `--report-only` is not used, the tool deletes stale artifacts, runs the command (via platform shell), then ingests the report
- if no command runs but a report exists, the tool ingests the report
- if no trustworthy report exists, coverage is reported as `indeterminate` and CRAP stays `N/A` (core guarantee)

Run `crap4code init` (or `crap4code init --force`) to get a heavily-commented sample `.crap4code.toml`. The generated file contains the authoritative explanation of the shell execution model for `coverage_command` strings, cross-platform guidance, and examples. Read the comments in the generated file — they are the primary durable documentation for this area.

See also the "Windows and Cross-Platform Notes" section below for PATH, shell, and case-sensitivity realities.

## Output

Table output includes:

- language
- file
- container
- function
- line range
- complexity
- coverage
- CRAP
- risk

JSON output includes:

- `summary`
- `functions`
- `recommendations`
- `run_metadata`
- `warnings`

## Exit Codes

- `0` success
- `1` invalid CLI usage or coverage command failure
- `2` threshold exceeded

## Supported Coverage Inputs

- Python: `coverage.py` XML
- JavaScript / TypeScript: LCOV
- Rust: LCOV

## Sample Repos

Checked-in sample repos live under `tests/sample_projects/` and are used for release-readiness verification:

- `python_repo`
- `javascript_repo`
- `rust_repo`
- `mixed_repo`

These repos keep small source trees plus coverage artifacts so CI can verify report parsing and end-to-end CLI behavior without requiring every language toolchain to generate fresh coverage each run.

## Windows and Cross-Platform Notes

**Current status**: Core functionality (all four language analyzers, coverage ingestion, CRAP scoring, deterministic recommendations, table + JSON output, `--changed`, `--report-only`, etc.) has been verified end-to-end on a real Windows machine (Python 3.13, PowerShell as daily driver + Git for Windows + cmd.exe as the subprocess shell). See the living plan document for the exact verification data, environment details, and full issue list.

This section is practical and honest about remaining limitations. The project prioritizes "never invent coverage data" and "deterministic/auditable" over pretending everything is seamless.

### Tree-Sitter Grammar Installation (JS / TS / Rust)

- The non-Python analyzers depend on `tree-sitter-javascript`, `tree-sitter-typescript`, and `tree-sitter-rust`.
- These are delivered as **real platform wheels** with native extensions (`.pyd` files on Windows). On a typical connected Windows dev box they install cleanly with no compiler required.
- Verified working (Python 3.13 win-amd64) for complex constructs, paths containing spaces/parentheses, and full end-to-end scans against sample projects.
- **Real risks / limitations (be honest with yourself and your team)**:
  - Wheel availability often lags behind new Python releases (3.14+) and especially Windows arm64.
  - Restricted / corporate / air-gapped / proxy pip environments can fail to fetch one or more of the grammar packages.
  - Version skew between the core `tree-sitter` package and the individual grammar packages exists today and can produce deprecation warnings or break on upgrades.
  - Currently these are *hard* dependencies: if any grammar is missing you get an import-time failure even for `crap4code scan --lang python`. (Lazy + tolerant loading + better error messages are Tier-1 planned work.)
- Python analysis (standard library `ast` only) has no tree-sitter dependency.
- For diagnosis: the probe/verify scripts in the repo root (`verify_tree_sitter_windows.py`) can be useful on your own machine.

If a grammar is unavailable you will see a clear `ModuleNotFoundError` (or the improved message after the planned D1/D3 work). The tool will not silently fall back.

### Coverage Commands on Windows (Shell Model)

`coverage_command` values are executed exactly as written via:

```python
subprocess.run(command, cwd=root, shell=True, ...)
```

- **Windows**: `shell=True` means **cmd.exe** (the `ComSpec` value), *even if you are running crap4code inside pwsh, bash, or an IDE terminal*.
- **POSIX** (Linux/macOS): the platform default (usually `/bin/sh` semantics).
- Your interactive shell's quoting rules, aliases, functions, or profile do **not** apply to the string in the TOML.

The sample produced by `crap4code init` deliberately demonstrates a working `&&` chain under cmd.exe and uses `python -m` forms so the Python that runs crap4code (and its venv) is reused by the coverage step.

**Practical advice**:
- Stick to `python -m coverage ... && python -m ...` style when possible.
- If you truly need pwsh syntax, wrap it: `pwsh -Command '...'`.
- The full authoritative guidance, quoting examples, and warnings live in the **comment block at the top of the generated `.crap4code.toml`** — read it.
- Failures currently print the raw output + the command string. Improved "this ran under cmd.exe from this cwd with this env" diagnostics are planned.

**Safety valve**: Always prefer `crap4code scan --report-only` while you are learning the tool, debugging a new coverage command, or running in read-only CI contexts. It completely skips `cleanup_artifacts` + command execution.

### Case-Insensitive Filesystem Risk for Coverage Mapping

Windows filesystems (and some macOS setups) are case-insensitive. This interacts with coverage mapping in a subtle but important way:

1. Source discovery walks the real directory tree and records paths via `normalize_repo_path` (repo-relative, always using `/` separators, casing taken from the OS walk).
2. Coverage report parsers (for `coverage.py` XML and LCOV) also call `normalize_repo_path` on the filenames *inside the report*.
3. `CoverageDatabase.coverage_for` does an exact `dict` lookup by the normalized key.

**If the report records `src/foo.py` but the FS walk saw `Src/Foo.py` (or vice versa), you get an exact-match miss → `indeterminate` for that file.**

The tool **mitigates** the risk as follows:

- Consistent normalization to POSIX-style repo-relative keys on *both* the source side and the report side.
- **Never invents** a coverage percentage or CRAP score. Missing or unmappable coverage stays `indeterminate` (this is a core product guarantee, not a bug).
- File paths shown in output are the normalized ones, so you can compare them directly against the report.

**Current honest limitation**: There is not yet an automatic case-fold fallback search on Windows (see R1 in the plan). You may therefore see more `indeterminate` rows than a human would expect when casing differs between your coverage tool's output and the on-disk names. When this matters, compare the exact strings in the report vs. what `crap4code` prints for the `file` column.

A future improvement will add a case-insensitive lookup pass (with a warning emitted the first time it is used) while still preserving the "no fake data" rule.

### PATH, venv, and Launch Environment

- The coverage command (and the whole crap4code process) receives a copy of the environment that launched the Python interpreter running crap4code.
- Desktop shortcuts, some IDE "run" buttons, scheduled tasks, and certain CI step definitions can have a surprising PATH or no venv activated.
- Result: `python -m coverage` inside your `coverage_command` may resolve to a different Python than you expect.

**Recommendation**: Activate the venv in your terminal, then invoke `crap4code` (the script) or `python -m crap4code.main`. The `python -m` forms *inside* your coverage_command help, but the outer invocation still determines the starting env.

### Other Cross-Platform / Windows Notes

- All internal and output paths use POSIX `/` separators (via `.as_posix()`). This keeps JSON reports and recommendations stable whether the scan ran on Windows or Linux.
- `--changed` relies on `git`. Git for Windows works; if `git` is not on PATH the flag is effectively ignored today (future work will surface this as a warning in the report).
- Long paths are generally fine on modern Windows + Python 3.10+; no special handling yet.
- Cleanup of stale artifacts is deliberately tolerant of missing files; on Windows certain `.coverage` files can be locked by other processes (in-progress improvements make this more robust).
- The plan document (`WINDOWS_AND_CROSS_PLATFORM_PLAN.md`) is the single source of truth for the full inventory, phased roadmap, success criteria, and verification steps. It is updated with implementation status as work lands.

For the most up-to-date status on any of the above, read the plan and then re-run `crap4code init --force` to see the latest comments that will be emitted.

## Development

```bash
python -m pip install -e .[dev]
python -m pytest -q
python -m build
python -m twine check dist/*
```

## Release Flow

- normal pushes run CI
- version tags like `v0.3.0` run the release workflow
- the release workflow builds the package, runs `twine check`, uploads artifacts, and can publish to PyPI if the repo has `PYPI_API_TOKEN` configured

## Notes

- Python uses the standard library `ast` (no external parser dependency for Python).
- JavaScript, TypeScript, and Rust require Tree-sitter grammar wheels (native code; see Windows section for risks).
- Recommendations and CRAP calculations are deterministic rules, not LLM-generated. They are fully auditable from the function metrics.
- Missing coverage is always treated as `indeterminate`; the tool will never synthesize a CRAP score.
