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

Repo path: `D:\code\crap4code`

## Quick Start

Write a sample config:

```bash
crap4code init
```

Scan with table output:

```bash
crap4code scan
crap4code scan --lang python
crap4code scan --lang typescript --changed --base-ref origin/main
```

Scan with machine-readable JSON:

```bash
crap4code scan --format json
```

Read an existing report without re-running coverage:

```bash
crap4code scan --report-only
```

## Config

`crap4code` looks for a repo-local `.crap4code.toml` by default.

Each language can define:

- `paths`
- `coverage_command`
- `coverage_report`
- `coverage_format`
- `stale_artifacts`

Coverage strategy:

- if `coverage_command` is configured and `--report-only` is not used, the tool deletes stale artifacts, runs the command, then ingests the report
- if no command runs but a report exists, the tool ingests the report
- if no trustworthy report exists, coverage is reported as indeterminate and CRAP stays `N/A`

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

## Development

```bash
python -m pip install -e .[dev]
python -m pytest -q
```

## Notes

- Python uses the standard library `ast`.
- JavaScript, TypeScript, and Rust use Tree-sitter grammars.
- Recommendations are deterministic rules, not LLM-generated advice.
