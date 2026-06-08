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

## Output & Exit Code Rules

- Always emit collected warnings (never silent).
- Exit 2 only on *measured* CRAP > threshold (never on indeterminate).
- JSON is stable for agent consumption; table is for humans.
