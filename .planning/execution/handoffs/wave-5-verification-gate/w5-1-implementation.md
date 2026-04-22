# W5-1 Handoff

## Status

- `done`

## What Changed

- Rebuilt the CLI around config-driven coverage ingestion, deterministic recommendations, and parser-backed language adapters.
- Added package, docs, and planning scaffolding so future work can continue from repo artifacts instead of chat context.

## Files

- src/crap4code/**
- tests/**
- .planning/execution/**

## Verification

- .\.venv\Scripts\python -m pip install -e .[dev]: pass
- .\.venv\Scripts\python -m pytest -q: pass
- .\.venv\Scripts\python -m crap4code.main scan --lang python --format json --report-only src: pass

## Blockers Or Risks

- JavaScript, TypeScript, and Rust rely on Tree-sitter wheels being available for the target Python/platform combination.
- Coverage execution is config-driven; repo consumers still need to provide real coverage commands and reports for their own projects.

## Next Thread Should Know

- Tree-sitter language wheels are expected runtime dependencies for JavaScript, TypeScript, and Rust.
- Coverage is intentionally indeterminate when a configured report is missing instead of being guessed.
