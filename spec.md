# crap4code v1 Spec

## Product Goal

Provide a Python-hosted CLI that helps humans and coding agents reduce change risk in Python, JavaScript, TypeScript, and Rust repositories by measuring:

- cyclomatic complexity
- function-level coverage
- CRAP score
- deterministic next-step recommendations

## Primary Workflow

1. discover source files
2. optionally refresh coverage artifacts through an explicit configured command
3. parse functions and compute complexity
4. map coverage onto function line ranges
5. compute CRAP where coverage is trustworthy
6. emit ranked output in table or JSON form
7. return exit code `2` when any measured CRAP score exceeds the threshold

## CLI Contract

### `crap4code init`

- writes `.crap4code.toml`
- refuses to overwrite without `--force`

### `crap4code scan`

Supported flags:

- `paths...`
- `--lang {python,javascript,typescript,rust}`
- `--changed`
- `--base-ref <git-ref>`
- `--format {table,json}`
- `--threshold <float>`
- `--config <path>`
- `--report-only`

## Coverage Contract

- Python coverage input: `coverage.py` XML
- JavaScript / TypeScript coverage input: LCOV
- Rust coverage input: LCOV
- Missing or unmappable coverage is `indeterminate`
- Indeterminate coverage never produces a fake CRAP score

## Shared Function Contract

Each function row includes:

- `language`
- `file_path`
- `container`
- `function_name`
- `start_line`
- `end_line`
- `complexity`
- `coverage_percent`
- `coverage_state`
- `crap_score`
- `risk_level`
- `recommended_actions`

## Recommendation Contract

Recommendations must be deterministic and auditable. They are derived from measured complexity, coverage state, coverage percentage, and CRAP score.

Examples:

- add tests first
- reduce branching
- simplify nested conditionals
- configure or generate coverage before trusting CRAP

## Output Contract

### Table

Human-readable ranking sorted by:

1. measured CRAP descending
2. complexity descending when CRAP is indeterminate

### JSON

Stable top-level keys:

- `summary`
- `functions`
- `recommendations`
- `run_metadata`
- `warnings`
