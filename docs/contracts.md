# crap4code Contracts

This document exists so a future agent can recover the v1 behavior quickly without re-deriving it from chat history.

## Language Support

- Python: standard library `ast`
- JavaScript: Tree-sitter JavaScript grammar
- TypeScript: Tree-sitter TypeScript grammar
- Rust: Tree-sitter Rust grammar

## Coverage States

- `measured`: the configured report covered at least one instrumented line in the function range
- `indeterminate`: no trustworthy function-range mapping was available

For the user-oriented explanation of why the `indeterminate` state exists, the situations that produce it, and its effects on CRAP scores / risk / recommendations (in plain terms), see the "Indeterminate Coverage — Why the State Exists" section in the user guide: [user-guide/concepts.md](./user-guide/concepts.md).

## Risk Levels

- `high`
- `moderate`
- `low`

Risk classification favors measured CRAP when available and falls back to complexity-only severity when coverage is indeterminate.

## Recommendation Rules

Recommendations are deterministic and ordered:

1. coverage trustworthiness guidance
2. testing guidance
3. complexity / refactor guidance

(See `src/crap4code/core/recommendations.py:enrich_rows` and the rules in `docs/user-guide/concepts.md`.)

## Function Filter (`--function`)

- Exact match on `function_name` only (not `container`).
- Repeatable; union of names.
- Applied after analysis and coverage mapping, before summaries and threshold evaluation.
- Duplicate names across files: all matching rows are included unless scope is narrowed with explicit source paths.
- No match (or empty intersection with `--baseline`) → exit 1 with actionable stderr.
- Unselected functions do not affect summary counts, recommendations, or exit 2.

## Coverage Overrides (`--coverage-report`, `--coverage-format`)

- CLI overrides do not mutate `.crap4code.toml`.
- Explicit `--coverage-report`: missing file → exit 1 (never fall back to config path).
- Format sniffing validates LCOV vs coverage.py XML when overrides are used.
- Config-only missing reports: soft warning + indeterminate coverage (unchanged).

## Compact Output (`--format compact`)

One line per function:

`file::function | lines=START-END | CX=N | coverage=N.N% | CRAP=N.NN | risk=LEVEL`

## Output & Exit Code Rules

- Always emit collected warnings (never silent).
- Exit 2 only on *measured* CRAP > threshold in the filtered result set (never on indeterminate).
- JSON is stable for agent consumption; table is for humans; compact is for shell one-liners.
