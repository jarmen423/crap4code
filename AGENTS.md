# crap4code Agent Notes

## Repo Purpose

`crap4code` is a Python-hosted CLI for measuring cyclomatic complexity, function-level coverage, CRAP score, and deterministic next-step recommendations across:

- Python
- JavaScript
- TypeScript
- Rust

## Primary Commands

Install for development:

```powershell
python -m pip install -e .[dev]
```

Run tests:

```powershell
python -m pytest -q
```

Write a sample config:

```powershell
crap4code init
```

Run a scan:

```powershell
crap4code scan
crap4code scan --format json
crap4code scan --changed --base-ref origin/main
```

## Important Project Rules

- Missing coverage must stay `indeterminate`; never invent a CRAP score.
- Recommendations should stay deterministic and auditable.
- Parser-backed language support is required for JavaScript, TypeScript, and Rust.
- Repo-local config is the source of truth for coverage commands and report paths.
