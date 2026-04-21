# crap4code

`crap4code` is a Python-hosted CLI scaffold for multi-language CRAP analysis inspired by `unclebob/crap4java`.

## MVP status

This initial PR establishes the shared architecture and a working CLI with analyzers for:

- Python (AST-based function discovery + complexity)
- TypeScript (JS-family heuristic analyzer)
- JavaScript (JS-family heuristic analyzer)
- Rust (heuristic analyzer)

Coverage ingestion is intentionally optional/stubbed in this MVP. The architecture is ready for future coverage adapters.

## Install / run locally

```bash
python -m pip install -e .
crap4code scan --help
```

## Usage

```bash
# scan all languages under src/
crap4code scan

# scan a single language
crap4code scan --lang python
crap4code scan --lang typescript
crap4code scan --lang javascript
crap4code scan --lang rust

# changed files only
crap4code scan --lang python --changed

# explicit files/directories
crap4code scan --lang python src tests/sample.py
```

## Exit codes

- `0` success
- `1` invalid CLI usage
- `2` threshold exceeded

## Current limitations

- Coverage integration is not yet implemented (coverage/CRAP columns show `N/A` without coverage input)
- JS/TS and Rust analyzers are intentionally heuristic in this first PR
- Python analyzer is the strongest reference implementation in this MVP
