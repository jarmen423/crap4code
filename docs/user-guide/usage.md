# Usage

This page documents the practical workflow, the two subcommands, important CLI flags, output formats, and cross-platform invocation patterns. It assumes you have read [getting-started.md](./getting-started.md) and [configuration.md](./configuration.md).

See root `README.md` for the shortest quick-start examples and `spec.md` for the formal CLI contract (flags, exit codes, output shape).

## Basic Invocation Patterns (Cross-Shell)

After `python -m pip install -e .[dev]` (or equivalent) you have a console script `crap4code`. The portable module forms also work:

```powershell
# Windows pwsh / cmd
crap4code scan --report-only
python -m crap4code scan --report-only
python -m crap4code.main scan --report-only

# POSIX (bash/zsh)
crap4code scan --report-only
python -m crap4code scan --report-only
```

The `python -m crap4code` form is enabled by `src/crap4code/__main__.py` (delegates to `main.py` → `cli.py:main`).

## The `init` Command

```powershell
crap4code init
crap4code init --force
crap4code init --config .crap4code.toml --force
```

- Writes (or refuses to overwrite) the canonical sample from `src/crap4code/core/config.py:sample_config_text()`.
- The generated file's header comments are the authoritative reference for the coverage command shell model.
- Use `--force` when you want to refresh the comments after an upgrade, then re-apply your custom paths/report settings.

## The `scan` Command — Flags and Behavior

```powershell
crap4code scan [paths...] [options]
```

Positional `paths...`:

- Zero or more files or directories.
- When present, they replace the config's `default_paths` / per-language `paths` for discovery.
- Example: `crap4code scan crates/foo crates/bar --lang rust`.

`--lang {python,javascript,typescript,rust}`:

- Limits the scan to a single language (must be both enabled in config and available in the runtime registry).
- If the requested language's grammar could not be loaded, a clear message is printed to stderr and exit 1 (no traceback). Example: "Rust support requires `pip install tree-sitter-rust`. These languages still work: python, javascript."
- Unrequested missing languages are silently omitted (no error).

`--changed`:

- Intersects discovered source files with the set of files changed vs. the base (HEAD or `--base-ref`).
- Uses `git` under the hood. If git is unavailable or you are not in a repo, a warning is emitted (see concepts and troubleshooting) and the intersection is empty (you will likely see the "No matching source files found." message + the warning on stderr).
- Useful in CI for "only analyze what this PR touched."

`--base-ref <ref>`:

- Example: `--base-ref origin/main`.
- Passed through to the git diff logic.

`--format {table,json}`:

- `table` (default): human-readable, risk-sorted, fixed-width columns + summary header line.
- `json`: stable, indented, sort_keys=True payload suitable for agents, jq, or CI assertions. Top-level keys: `summary`, `functions`, `recommendations`, `run_metadata`, `warnings`.

`--threshold <float>`:

- Overrides the value from config (or the built-in default 8.0).
- Only *measured* CRAP scores are compared (indeterminate rows never cause exit 2).

`--config <path>`:

- Use a non-default TOML file (absolute or relative to cwd).

`--report-only`:

- Skips `cleanup_artifacts` and any `coverage_command` execution.
- Still loads and maps the report named by `coverage_report` + `coverage_format` if present.
- Extremely useful while tuning config on Windows, in read-only CI contexts, or when you just want to re-analyze an existing coverage artifact without side effects.
- See root `README.md` and the safety-valve paragraph in the generated config comments.

## Typical Workflows

1. **Human daily / tuning** (while learning or editing the TOML):

   ```powershell
   crap4code scan --report-only
   # iterate on paths / coverage_report in .crap4code.toml
   ```

2. **Full with coverage refresh** (when you want the tool to drive generation):

   ```powershell
   crap4code scan   # will run configured coverage_command(s) for languages that have one
   ```

3. **Agent / CI JSON + threshold gate**:

   ```powershell
   crap4code scan --format json --changed --base-ref origin/main > scan.json
   # then in the same step or a gate: if the process exited 2, fail the build
   ```

4. **Language-specific one-off** (no TOML change):

   ```powershell
   crap4code scan lib/ --lang typescript --format json
   ```

5. **Monorepo with mixed languages**:

   Configure multiple language sections with their own `paths` lists; run without `--lang` to process all enabled/available languages in one invocation. Results are merged and globally risk-sorted.

## Output Examples (Shape Only)

Table (abbreviated):

```
scanned_files=3 functions=7 threshold=8.00 threshold_exceeded=no
language | file            | container | function   | lines | complexity | coverage | crap  | risk
python   | src/foo.py      | module    | risky_fn   | 10-25 | 14         | 35.0%    | 42.31 | high
...
```

JSON top level (stable):

```json
{
  "summary": {
    "scanned_files": 3,
    "functions_found": 7,
    "threshold": 8.0,
    "threshold_exceeded": false,
    ...
  },
  "functions": [ { "language": "...", "file_path": "...", "crap_score": 42.31, "coverage_state": "measured", ... } ],
  "recommendations": [ { "language": "...", "recommended_actions": ["..."] , ... } ],
  "run_metadata": { "coverage_commands_run": [...], "config_path": ".crap4code.toml" },
  "warnings": [ "Case-insensitive coverage path match used: ..." ]
}
```

See `src/crap4code/core/report.py` (`build_report`, `format_report`, `format_report_json`) and `models.py` for exact fields.

## Exit Codes (from spec.md and cli.py)

- `0` — success (including the informational "No matching source files found." case).
- `1` — invalid CLI usage or a coverage command that was configured and executed returned non-zero.
- `2` — at least one function had a *measured* CRAP score strictly greater than the (config or CLI) threshold.

Only measured scores participate in the threshold check (`is_threshold_exceeded` in `src/crap4code/core/thresholds.py`).

## Recommendations in Output

The top (up to 10) functions that have non-empty `recommended_actions` are extracted into the report's `recommendations` list (both table-adjacent and JSON). The actions themselves live on every function row and are produced by the deterministic rules in `enrich_rows` / `recommend_actions`.

## --report-only Is Your Friend

While you are:

- Learning the tool
- Debugging a new `coverage_command`
- Running in a CI job that must not mutate the workspace
- Just re-ranking after someone else regenerated coverage

...always prefer `--report-only`. It completely bypasses the cleanup + subprocess step while still giving you full mapping, CRAP, risk, and recs from whatever report artifact is already on disk.

## Relation to Sample Projects

The `tests/sample_projects/` trees (python_repo, javascript_repo, rust_repo, mixed_repo) are intentionally small checked-in fixtures containing source + pre-generated coverage artifacts. They allow release verification (`tests/test_sample_projects.py`) and end-to-end CLI tests to run without requiring every language toolchain + coverage generator on every CI matrix entry. They are excellent for experimenting locally too: `cd tests/sample_projects/rust_repo && crap4code scan --report-only`.

For the authoritative list of supported coverage inputs, see root `README.md` "Supported Coverage Inputs" (matches `spec.md`).

Next page: [troubleshooting.md](./troubleshooting.md) for the situations you will hit on real projects (workspaces, case differences, shell surprises, "no files", indeterminate results).
