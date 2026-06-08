# crap4code Agent Notes

## Repo Purpose

`crap4code` is a Python-hosted CLI for measuring cyclomatic complexity, function-level coverage, CRAP score, and deterministic next-step recommendations across:

- Python
- JavaScript
- TypeScript
- Rust

## Primary Commands

Install for development (works on pwsh/cmd/bash; see phase3-dx / Dev1 for history):

```powershell
python -m pip install -e .[dev]
```

Run tests (now reliably works from repo root with no manual PYTHONPATH on any shell,
both after the editable install *and* before it, thanks to the guarded conftest):

```powershell
python -m pytest -q
```

(Equivalent cross-shell "one liner": `python -m pip install -e .[dev] && python -m pytest -q`)

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

See also `tests/conftest.py` (module docstring), `pyproject.toml` (pytest section comments),
`README.md` (Development section), and `WINDOWS_AND_CROSS_PLATFORM_PLAN.md` (Dev1 + phase3-dx)
for the full story on making dev/test commands robust across Windows shells.
