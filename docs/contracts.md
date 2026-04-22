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

## Risk Levels

- `high`
- `moderate`
- `low`

Risk classification favors measured CRAP when available and falls back to complexity-only severity when coverage is indeterminate.

## Recommendation Rules

Recommendations are deterministic and ordered:

1. coverage trustworthiness guidance
2. testing guidance
3. complexity reduction guidance
4. prioritization guidance

This keeps the output stable for agents and CI assertions.
