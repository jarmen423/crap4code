# crap4code

`crap4code` is a Python-hosted CRAP analyzer for Python, JavaScript/TypeScript, and Rust.

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
crap4code scan --format html > report.html   # beautiful shareable browser report
```

Read an existing report without re-running any coverage commands (very useful on Windows while tuning):

```bash
crap4code scan --report-only
```

See `docs/user-guide/README.md` (and `docs/user-guide/getting-started.md`) for organized walkthroughs and "after a break" reminders.

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

- For detailed, organized explanations of core concepts (CRAP metric, coverage reports & formats, what 'paths' means, 'no matching source files', warnings, indeterminate coverage, etc.), usage workflows (including after a break), and troubleshooting, see `docs/user-guide/` (start with `docs/user-guide/README.md` as the guide index — it has a hierarchical table of contents with back-links — then concepts.md and configuration.md).

See also the "Windows and Cross-Platform Notes" section below for PATH, shell, and case-sensitivity realities.

## Output

Table output includes:
