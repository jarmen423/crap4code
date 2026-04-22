# crap4code MVP Architecture Spec

## Goals

Provide a single CLI and shared core for CRAP analysis across Python, TypeScript, JavaScript, and Rust.

## Package layout

- `src/crap4code/cli.py`: argument parsing and scan workflow
- `src/crap4code/main.py`: executable entry point
- `src/crap4code/core/`: shared models, CRAP formula, reporting, file discovery, changed-file detection, thresholds
- `src/crap4code/analyzers/`: language adapters implementing a shared analyzer protocol

## Shared model

Per-function rows include:

- language
- file path
- container (class/module/impl where available)
- function/method name
- line
- complexity
- coverage percent (optional)
- CRAP score (optional)

## CRAP formula

`CRAP = CC^2 * (1 - coverage)^3 + CC`

Coverage is represented as a ratio in `[0.0, 1.0]` in the scoring function.

## Analyzer abstraction

Analyzers implement:

- language-specific file discovery
- optional changed-file filtering via shared git helper
- minimal per-function metric extraction

## Language adapters

- Python: AST traversal (`ast`) and basic cyclomatic complexity counting
- JS/TS: shared heuristic function extraction + complexity token counting
- Rust: heuristic `fn` extraction + complexity token counting

## Reporting & threshold

- report rows are sorted by descending CRAP, null CRAP last
- default threshold is `8.0`
- threshold breach returns exit code `2`

## Future coverage integration

Planned follow-up work:

- Python: coverage.py XML adapter
- JS/TS: Istanbul/NYC JSON or LCOV adapter
- Rust: llvm-cov/tarpaulin adapter
- per-function line-range coverage mapping in each adapter
