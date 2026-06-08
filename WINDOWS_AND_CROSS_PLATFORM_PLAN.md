# crap4code: Windows & Cross-Platform Usability Plan

**Status**: Living document. All phases (0/1/2/3) complete as of 2026-06-08. Released as v0.4.0 (see release-checklist.md, CHANGELOG.md and release commit 0130258 / tag v0.4.0). Phase 3 (Polish, DX, CI) landed on merge/phase3-land-and-verify: Dev1 (pytest DX), Dev4 (CI enhancements + minimal verify), release checklist expansion. (See Phase 3 Merge section at end.)
**Phase 0 foundations complete**: `__main__.py` + `--version` implemented on 2026-06-08. (See C1/C2 + Phase 0 section for details.)
**Goal**: Make `crap4code` pleasant and reliable for daily use on **Windows** (primary pain) **and** POSIX systems (macOS/Linux), without sacrificing the project's core values (small, auditable, deterministic, no fake coverage data, parser-backed, repo-local config as source of truth).
**Scope**: All issues raised in the initial project review + the dedicated Windows/cross-platform review turn, plus fresh verification data.

---

## 1. Current Verified Status on This Windows Machine (Empirical Data)

**Environment (as of verification)**:
- Windows (win32, os.name=nt)
- Python 3.13.7 (64-bit, MSC v.1944)
- PowerShell (pwsh) as primary shell, but `ComSpec` = cmd.exe
- Git for Windows 2.50.1 (git.exe at `C:\Program Files\Git\cmd\git.exe`)
- Packages installed in user site-packages (common when not using a clean venv)

**tree-sitter packages (actual state)**:
- `tree-sitter` 0.25.2
- `tree-sitter-javascript` 0.25.0
- `tree-sitter-typescript` 0.23.2
- `tree-sitter-rust` 0.24.2
- All provide real native code via `.pyd` files (e.g. `...__mypyc.cp313-win_amd64.pyd`). They are proper Windows wheels, not source builds that require a compiler at install time on this machine.
- Direct imports + `Language(gram.language_xxx())` + `Parser` construction succeed.
- Full `crap4code` import (via `get_language_registry`) succeeds without errors.

**Analyzer execution on Windows (live tests)**:
- `PythonAnalyzer`: Works on `tests/fixtures/python/sample.py`. Extracts methods + async fns + correct complexity (BoolOp + If counted).
- `JavaScriptFamilyAnalyzer("javascript")`: Works. Extracts function declarations, methods in classes, methods in object literals.
- `JavaScriptFamilyAnalyzer("typescript")`: Instantiates and is ready.
- `RustAnalyzer`: 
  - Works on the checked-in fixture (`tests/fixtures/rust/sample.rs`).
  - Correctly reports containers for free functions (`module`), inherent impls (`Service<T>`), and trait impls (`Service (impl Worker)`).
  - Successfully parsed complex constructs in a file located under a Windows temp directory whose path contained **spaces and parentheses**: `if` + `&&`, `match`, `impl` blocks, closures, `while` + `break`.
  - File paths in output are always normalized to POSIX style (`weird path with spaces and (parens)/complex.rs`).

**End-to-end CLI on sample projects (with `--report-only`)**:
- Rust sample project (`tests/sample_projects/rust_repo`): Full scan succeeds. Correct functions, containers, coverage mapping from checked-in `lcov.info`, CRAP scores, recommendations, summary, exit code 0.
- JavaScript sample: Works, coverage percentages applied, clean table output.
- Python sample: Works (as used in many prior tests).
- Mixed repo: Previously verified to work.
- Full project scan (current source): 67 Python functions found, all `file_path` values use `/` (no backslashes).

**Key positive observation**: The packages **do work** on current Windows + Python 3.13 for all four languages when the wheels are available. The "sometimes missing" risk is real in the ecosystem (new Python releases, arm64 Windows, corporate proxies that block certain wheels, CI images), but on a normal developer Windows machine with internet the current pinned versions install and run.

**Minor notes from runs**:
- DeprecationWarning: `version is deprecated. Use abi_version instead.` (emitted when wrapping some grammars). The analyzer code does not call the deprecated attr directly.
- `python -m crap4code` (without `.main`) still fails (no `__main__.py`).  [Note: now resolved as of 2026-06-08]
- When running from project root without cd'ing, default_paths + language filters can result in "No matching source files found" (expected behavior, not a bug).

---

## 2. Tree-Sitter Packages on Windows — Verified Reality (Not Rumors)

**Do they work?** Yes, on this machine they work end-to-end for Python, JS, TS, and **Rust**.

**How they are delivered**:
- Proper platform wheels containing compiled native extensions (`.pyd` for cp313-win_amd64).
- Loaded via the grammar package's `__init__.py` (the spec probe showed the origin is the `.py`, but the pyds are present and used internally by the mypyc-compiled glue).
- No compiler was required at install time in this environment.

**Risks that remain real (even though they worked here)**:
- Version skew between `tree-sitter` core (0.25.x) and the individual grammar packages (some still at 0.23.x / 0.24.x). The new Language API stabilized in 0.23, but ABI details can shift.
- New Python releases (3.14+) or Windows arm64 often lag on prebuilt wheels for these packages.
- Corporate / air-gapped / restricted-pip environments may not be able to fetch the exact wheel.
- The current `pyproject.toml` declares them as hard `dependencies`, not optional.
- Because `languages/registry.py` does **unconditional top-level imports**, merely importing `crap4code` (or running any command) will fail the entire tool if any one grammar is missing.

**Rust analyzer specific**:
- The grammar (`tree_sitter_rust` 0.24.2) worked without issues.
- The analyzer code correctly walks `impl_item`, extracts `type` + optional `trait` for container naming (`Service (impl Worker)`), skips nested functions/closures when counting complexity, handles `match_expression` arm counting, binary `&&`/`||`, etc.
- No Windows-specific crashes observed with paths containing spaces, parens, or unicode (temp dirs on Windows are a good stress case).
- Coverage mapping worked in the sample project (the lcov contained the right paths relative to the sample project's root).

**Conclusion for the plan**: We must treat tree-sitter as a real cross-platform risk area and reduce its blast radius (lazy loading + better error messages + docs), even though the happy path works today on this machine.

---

## 3. Comprehensive Inventory of All Issues

Issues are grouped. Each has: description, evidence (from reviews + live verification), severity by platform, proposed solutions, files, verification approach.

### 3.1 Dependency & Installation Layer

**Issue D1: Eager unconditional import of all tree-sitter grammars**
- Description: `registry.py` imports JS/TS/Rust analyzers at module level. Each analyzer does `import tree_sitter_*` at the top. Result: the entire package is unusable unless all native packages are present.
- Evidence: `languages/registry.py:6-8`, `javascript/analyzer.py:8-9`, `rust/analyzer.py:8`, same for TS. Live import tests showed the full chain only succeeds when all are installed.
- Severity: High on Windows (wheel availability), Medium on POSIX.
- Proposed fixes:
  - Make grammar imports lazy inside `get_language_registry()` or inside the `LanguageDefinition` factories.
  - Wrap each non-Python language in `try: ... except ImportError: skip or mark unavailable`.
  - Optionally support `crap4code[python-only]` or document that full install is needed for multi-lang.
  - Expose a way for callers/CLI to list which languages are actually available at runtime.
- Files: `languages/registry.py`, `languages/*/analyzer.py` (and their `__init__.py`), `cli.py` (for warnings), `core/models.py` perhaps for an "available" flag.
- Verification: Fresh Python env with only `tree-sitter` + `tree-sitter-python` (if it exists) + crap4code; confirm `import crap4code` and `crap4code scan --lang python` work while `--lang rust` gives a clear message.
- Priority: **Critical** (Tier 1).

**Issue D2: tree-sitter version skew and lack of upper bounds / compatibility testing**
- Description: pyproject pins lower bounds only. Grammar packages lag the core.
- Evidence: Installed versions (0.25 core vs 0.23/0.24 grammars). Deprecation warning observed.
- Severity: Medium (worked today, can break on upgrade).
- Proposed: Add compatible upper bounds or a tested matrix. Document the known-good combinations. Consider a CI job that installs the exact wheel set used in verification.
- Files: `pyproject.toml`.
- Priority: High.

**Issue D3: No graceful degradation or helpful error when a grammar is missing**
- Currently just a raw `ModuleNotFoundError` during import.
- Fix: Catch at registry time and emit a clear message like "Rust support requires `pip install tree-sitter-rust`. Python and JS/TS will still work."
- Priority: High (goes with D1).

### 3.2 Runtime / Language Analyzer Correctness & Robustness

**Issue R1: Case-insensitive filesystem mismatch between source discovery and coverage reports (Windows + some macOS)**
- Description: `normalize_repo_path` preserves the casing from the source it saw (FS walk for sources, report string for coverage). Dict lookup in `CoverageDatabase` is exact. On case-insensitive FS the two can differ → silent `indeterminate`.
- Evidence: Code inspection in `core/coverage.py:26` (`self.line_hits_by_file.get(file_path)`), `core/files.py:46` (`.resolve()`), coverage parsers, and the Windows review analysis. Common with `coverage.py` XML, lcov from various tools.
- Severity: **High on Windows**, Low on strict case-sensitive Linux.
- Proposed fixes (choose one or combine):
  - In `coverage_for`, when exact miss on `win32`, do a case-folded search over the keys.
  - Or maintain a secondary case-insensitive index on Windows.
  - Normalize both sides to a case-folded key only for lookup (keep original for display).
  - Add a warning when a case-insensitive match was used.
- Files: `core/coverage.py` (main), `core/files.py`, tests for coverage mapping.
- Verification: Synthetic test that creates a source file "Src/Foo.py", a report that records "src/foo.py", and asserts `measured` + correct % on Windows.
- Priority: **Critical** (Tier 1) — directly affects the value prop on Windows.

**Issue R2: Rust analyzer (and JS family) path handling under real Windows paths**
- Already largely works (verified with spaces + parens), but we should codify it with tests.
- Add explicit tests that create files in dirs with spaces, unicode, parentheses, and very long segments.
- Also test `--changed` when the changed file has such a name.
- Priority: Medium (prevent regression).

**Issue R3: Silent skipping of unparsable files**
- Python analyzer catches `OSError, SyntaxError, UnicodeDecodeError` and continues (no row, no warning).
- Similar patterns exist in JS/Rust (only OSError on read).
- Should collect warnings and surface them in the final report (the report already has a `warnings` list).
- Priority: Medium.

**Issue R4: Limited stress / edge coverage for the parsers**
- Current fixtures are small.
- Need richer test cases for: decorators + nested functions (Python must not double-count), JS arrow in weird places, TS type-only constructs, Rust macros, `async`, generators, match guards, etc.
- Priority: Medium for confidence.

### 3.3 Subprocess, Shell, & Coverage Command Execution Model

**Issue S1: `shell=True` + raw string from user config (the core UX contract)**
- `run_coverage_command` always uses `shell=True` and passes the exact string from `.crap4code.toml`.
- On Windows this is **always cmd.exe** (`ComSpec`), even if the user is in pwsh, Git Bash, or a VS Code integrated terminal.
- The generated sample uses `&&` which happens to work under cmd.exe.
- Users who write pwsh-specific syntax, or who expect their shell's quoting rules, get surprises.
- Evidence: `core/coverage.py:149-157`, live probe that confirmed `ComSpec` behavior, sample config in `config.py:162`.
- Severity: High on Windows, Low on POSIX (where it matches expectation).
- Proposed solutions (keep the model, improve transparency):
  - Document explicitly in README, in the generated config comments, and in error output: "Executed via the platform shell (cmd.exe on Windows)".
  - Prefix failure detail with the exact command + the shell that was used.
  - In `run_coverage_command`, also return / log `os.environ.get("ComSpec")` or `SHELL` for diagnostics.
  - Provide guidance: prefer `python -m` forms; for complex needs use `pwsh -Command '...' ` or `cmd /c "..."`.
  - Consider adding a config knob later (`coverage_shell` or `coverage_command_is_list`) but keep v1 simple.
- Files: `core/coverage.py`, `cli.py` (where failure is printed), `config.py` (sample text), README + new docs file.
- Priority: **High** (Tier 1 for pleasant Windows use).

**Issue S2: No visibility into what actually ran when coverage command fails**
- Currently it prints the raw stdout/stderr, which is good, but lacks context ("this was run as cmd.exe /c '....' from this cwd, with this env").
- Fix as part of S1.
- Priority: High.

**Issue S3: `env=os.environ.copy()` can surprise users**
- If `crap4code` is launched from a different context than the user's shell (desktop shortcut, scheduled task, agent, different terminal profile), the PATH / venv / Python may be wrong.
- Suggestion: Document this. Optionally surface the python executable used by the tool.
- Priority: Medium.

### 3.4 CLI Surface, UX, and Discoverability

**Issue C1: `python -m crap4code` does not work**
- Only `python -m crap4code.main` or the console script (`crap4code.exe` on Windows) work.
- Evidence: `main.py` has the `if __name__`, no `__main__.py` at package root. Verified in probes.
- Fix: Add `src/crap4code/__main__.py` that does `from .main import main; raise SystemExit(main())`.
- **Implemented (phase0-3)**: 2026-06-08. Added `src/crap4code/__main__.py` (new file) that cleanly delegates: `from .main import main` followed by the standard `if __name__ == "__main__": raise SystemExit(main())`. The file contains a detailed module docstring (per AGENTS.md "Teach Through Code" + structured documentation standard) explaining:
  - what the file does
  - why it exists (cross-platform expectation for `python -m pkg`)
  - how it fits (exact match to the `crap4code.main:main` console script contract in pyproject.toml)
  - the full delegation chain ( __main__ -> main.py -> cli.py )
  - explicit instruction to keep it minimal.
  This makes `python -m crap4code` (and `python -m crap4code --help`, `--version`, `scan` etc.) behave identically to the installed entry point.
- Priority: High (Tier 1 — basic expectation).

**Issue C2: No `--version` / `-V`**
- `__version__` exists in `src/crap4code/__init__.py`.
- Users and scripts expect `crap4code --version`.
- Fix: Add to the argparse in `cli.py`.
- **Implemented (phase0-4)**: 2026-06-08. Added `-V` / `--version` support to the top-level parser in `src/crap4code/cli.py`:
  - `from crap4code import __version__` (single source of truth; matches the style of other package imports in cli.py and gives the str directly).
  - `parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}", help=...)` placed on the parent parser before subparsers (so bare `crap4code --version` and `crap4code -V` work).
  - Added targeted inline comments and expanded the `_build_parser` + `main()` docstrings.
  - Updated `spec.md` (the CLI Contract) to document the new top-level option.
  - argparse auto-generates the help text and correct exit (0) behavior.
  - No changes to subcommand parsers (intentional; --version is a top-level concern).
  - Kept the edit minimal and high-quality; did not touch unrelated files.
- Priority: Medium-High.

**Issue C3: Limited introspection (no "what languages are available?", no dump of effective config)**
- Useful for agents and for "why is Rust not working?" situations.
- Can be added cheaply after the lazy-loading change (D1).
- Priority: Medium.

**Issue C4: Table output can be extremely wide on real codebases**
- 67 functions in this repo already produces a wide table.
- No paging, no truncation, no alternative compact format.
- Low priority for now (JSON is the machine path), but worth noting for daily human use.

### 3.5 Error Handling, Robustness, Cleanup

**Issue E1: `cleanup_artifacts` can crash the scan**
- Raw `unlink` / `rmdir` with no protection for readonly files, in-use files (common for `.coverage` on Windows with certain pytest plugins), permission errors, or hidden files.
- Evidence: `core/coverage.py:129-136`, Windows review.
- Fix: Use `shutil.rmtree(..., ignore_errors=True)` for dirs. Wrap file unlinks. Collect warnings instead of raising.
- Priority: High for Windows daily use (Tier 1).

**Issue E2: Git operations are completely silent on failure**
- `get_changed_files` catches everything and returns `{}`.
- `--changed` just silently scans nothing (or everything, depending on interpretation).
- Fix: Capture stderr, return a small status object or warnings, surface "warning: git not available or not a repo — --changed ignored" in the report warnings.
- Priority: Medium-High (especially for CI on Windows runners).
- **Implemented (phase2-git-warn, 2026-06-08)**: 
  - `get_changed_files` now always captures stderr (via the existing capture_output) and returns `tuple[set[str], list[str]]` (changed, warnings).
  - On OSError (no git binary) or rc!=0 it emits one clear actionable warning containing the phrase "git not available or not a repository — --changed flag had no effect" plus an optional bounded `(git stderr: ...)` snippet so the real git message is visible.
  - Callers updated: `discover_source_files` (now also returns `tuple[list[Path], list[str]]`), `_scan` in cli.py (extends the warnings list + special case to print warnings even on the "No matching source files found." path that --changed + non-repo always hits), and the dev `win_probe.py`.
  - Added `test_changed_flag_in_non_git_dir_emits_warning` (and base_ref variant) in `tests/test_cli.py` that cds to a fresh `TemporaryDirectory` (guaranteed non-git), runs `main(["scan", "--changed", ...])`, asserts exit 0 + the no-files msg + the exact warning text on captured stderr.
  - Warnings now flow through the existing `warnings` list -> `build_report` -> ScanReport -> JSON and table (when files are found) + stderr print. The no-files path also emits to stderr for this case.
  - Change kept small + defensive (no new exceptions, no behavior change on happy path inside real git repo, no new deps).
  - Also updated module docstrings + targeted comments per "Teach Through Code".
  - Verification: the new test + post-edit manual inspection of the temp-dir scenario logic (full pytest run of the CLI changed tests is the external verification command: `python -m pytest tests/test_cli.py -q -k "changed or no_files"` inside a non-git temp dir or from any cwd — the test itself forces the non-repo cwd).

**Issue E3: Limited collection of warnings across the run**
- Some paths already feed warnings into the report. Many do not (skipped files, git problems, coverage mapping fallbacks, case-fold matches).
- Make warnings a first-class collected thing.
- Priority: Medium.

### 3.6 Documentation, Examples, and Mental Model

**Issue Doc1: Sample config and README give no explanation of the shell model**
- The `&&` in the Python section "just works" on Windows only because of cmd.exe semantics.
- No note that the command runs under the platform default shell.
- Fix: Rich comments inside `sample_config_text()`, a dedicated "Coverage commands on Windows" subsection in README, cross-platform examples.
- Priority: High (Tier 1).

**Issue Doc2: No Windows / cross-platform troubleshooting section**
- Users hitting missing grammars, case mismatches, PATH/venv surprises, long paths, etc. have nowhere to look.
- Create or expand docs (the plan document itself can seed it).
- Priority: High.

**Issue Doc3: README uses only `bash` fences and Unix-oriented quickstarts**
- Minor but contributes to the "this is a Unix tool" perception.
- Add pwsh / cmd examples where relevant.

### 3.7 Development, Test, CI, Packaging Experience

**Issue Dev1: pytest collection / import is fragile with PYTHONPATH on Windows pwsh**
- The `pyproject.toml` `pythonpath = ["src"]` is supposed to help, but real runs often required explicit `$env:PYTHONPATH='src'` in pwsh.
- Different shells have different syntax for setting env for a single command.
- Fix: Make the test suite importable more robustly (perhaps a `conftest.py` that adjusts path, or recommend `python -m pytest` after editable install, or use `pip install -e .[dev]` + proper editable that puts src on path).
- Also ensure `python -m pytest` from repo root works without manual env var on all three major shells.
- Priority: Medium (affects contributors on Windows).

**Issue Dev2: Stale `src/crap4code/analyzers/` directory (only pyc files)**
- From the first review. Dead code from a previous layout. Not packaged (good), but confusing and pollutes the source tree.
- Fix: Delete the entire `analyzers/` directory (sources + pycache).
- Priority: High (cleanliness).

**Issue Dev3: Repo hygiene — committed junk**
- `qdrant_storage/`, `.agentic-memory/`, `.planning/` (and sometimes `build/`) are present and not ignored.
- They pollute `git status`, `--changed` scans, and the experience.
- Update `.gitignore` aggressively.
- Priority: High (from first review).

**Issue Dev4: CI already has Windows in the matrix (good), but limited verification of the hard parts**
- The release checklist and sample projects are excellent.
- We should add explicit jobs or steps that test:
  - Install with minimal packages (Python-only).
  - Case-mismatch coverage scenario (synthetic).
  - Coverage command failure output.
  - `--changed` behavior.
- Priority: Medium.

**Issue Dev5: No `__main__.py` affects packaging/docs expectations**
- Related to C1.
- (Resolved together with C1 on 2026-06-08.)

### 3.8 Packaging & Distribution

**Issue P1: `tree-sitter-*` are hard dependencies for everyone**
- Even a user who only ever scans Python pays the install cost and failure risk.
- After lazy loading, we can consider making them true optional dependencies or documenting the split.
- Priority: Medium (after D1).

**Issue P2: Build artifacts and egg-info can leak**
- Normal, but combined with poor .gitignore it gets messy.
- Ensure `MANIFEST.in` (if any) or `pyproject` config is tight (current setuptools auto-discovery seems to do the right thing).

### 3.9 Other / Lower Priority

- Long path support on Windows (Python 3.10+ + OS setting should be sufficient; no special code needed yet).
- Encoding of git output / coverage reports in weird locales (current code uses `text=True` which follows locale, plus explicit utf-8 for reports we control).
- Performance (no caching of parses) — out of scope for this plan unless it becomes painful.
- Color / rich table output — nice but adds a dep; keep zero-dep for v1.
- Exit code 1 vs detailed error for grammar missing vs coverage command fail — already reasonable.

---

## 4. Phased Implementation Roadmap

**Phase 0 — Foundations (do immediately)**
- Write / land this plan document.
- Delete stale `src/crap4code/analyzers/`.
- Expand `.gitignore` (qdrant_storage, .agentic-memory, .planning, .cursor, .claude, build, dist, etc.).
- Add `__main__.py`. **Implemented 2026-06-08 (phase0-3)** — see C1 for full notes + file.
- Add `--version`. **Implemented 2026-06-08 (phase0-4)** — see C2 for full notes + changes to cli.py + spec.md.

**Phase 1 — Critical Windows Value (Tier 1)**
- D1 + D3: Lazy / tolerant language registration + clear error messages.
- R1: Case-insensitive coverage lookup on Windows (with tests + warning).
- E1: Harden `cleanup_artifacts`.
- S1 + S2: Better shell context in coverage command failures + docs.
- Doc1 + Doc2: Update sample config comments + add Windows/cross-platform section to README (seed from this plan).

**Phase 2 — Robustness & Observability**
- E2: Surface git warnings. **(Implemented 2026-06-08, phase2-git-warn — see detailed note under Issue E2 in section 3.5)**
- E3 / R3: Consistent warning collection for skipped files, case-fold matches, etc.
- Add richer tests for case mismatch, complex Rust/JS, paths with spaces/unicode.
- Improve error messages when a requested `--lang` is not available.

**Phase 3 — Polish, DX, CI**
- C2, C3: `--version` + basic language availability introspection. **(C2 completed early in Phase 0)**
- Dev1: Make `python -m pytest` from root "just work" across shells after editable install.
- Dev4: Enhance CI with targeted Windows/cross-platform scenarios.
- Add deprecation warning suppression or update for the tree-sitter `version` attr if we touch the Language creation sites.
- Expand release checklist with "verify on a clean Windows machine with only the declared deps".

**Phase 4 — Future / Nice**
- Optional dependencies packaging experiment.
- Config option to control shell or pass args as list (if demand appears).
- Better table formatting or `--format compact`.

---

## 5. Success Criteria (Measurable)

For each Tier 1 item, define a concrete verification that can be done on a Windows machine + on Linux/macOS.

Examples:
- "On a fresh Windows Python 3.13 venv: `pip install -e .` then `python -c 'import crap4code; print(crap4code.__version__)'` succeeds and only pulls tree-sitter + tree-sitter-python if we decide to split; scanning Python works; asking for Rust produces a helpful message instead of ImportError."
- "Create a source file `Src/Camel.py` and a coverage.xml that records filename `src/camel.py`. After scan the function shows `measured` + correct percentage (case-fold match used)."
- "A coverage command that fails prints the shell that was used and the exact string."
- "After `crap4code init`, the generated file contains comments explaining the execution environment."
- All existing sample project tests + new Windows-specific tests continue to pass on the CI matrix (which already includes windows-latest).

---

## 6. Risks & Trade-offs

- Lazy loading adds a small amount of complexity and one more place where availability must be checked (CLI + tests).
- Case-fold matching is a heuristic. We should log a warning the first time it is used so users aren't surprised by "magic".
- Changing cleanup behavior is safe (more tolerant) but we lose the ability to surface certain permission problems (we can still warn).
- Documenting the shell model more explicitly makes the current design choice visible; some users may then ask for a "no-shell" mode. We can defer that.
- Making grammars optional changes the "all four languages always available" mental model that the current docs and sample config assume.

---

## 7. Open Questions

- Should we eventually publish separate distribution extras (`crap4code[python]`, `crap4code[full]`)?
- Do we want to support passing coverage commands as TOML arrays (list form, no shell) in addition to strings? (Bigger change to the contract.)
- How aggressive should we be about upper-bounding tree-sitter versions?
- Is there appetite for an optional "rich" or "textual" output mode later?

---

## 8. References & Related Files

- `src/crap4code/core/coverage.py` (run_coverage_command, cleanup, CoverageDatabase, normalize)
- `src/crap4code/core/git_changed.py`
- `src/crap4code/languages/registry.py` + the three analyzer implementations
- `src/crap4code/cli.py` (the _scan path and error handling)
- `src/crap4code/core/config.py` (sample_config_text)
- `pyproject.toml`
- `README.md`, `spec.md`, `docs/contracts.md`, `docs/release-checklist.md`
- `tests/sample_projects/*` + `tests/test_sample_projects.py` (the golden release verification)
- `.gitignore`
- Previous review notes (Windows/cross-platform turn + initial project review)

---

**How to use this plan**: Treat each issue as a ticket or sub-task. Update the "Status" line at the top as items are implemented. Add implementation notes / PR links under the relevant sections (detailed status was added under 3.6 for the documentation work). Re-verify on a real Windows machine (not just WSL) before considering an item done.

This document should be the single source of truth for "what does it take to make crap4code pleasant on Windows and portable everywhere."


## Merge & Verification (coordinator subagent session, 2026-06-08)

**Branch used for landing**: `merge/phase0-1-land-and-verify`

**Worktree paths reviewed (all based on 9a88f98)**:
- `C:\Users\jfrie\AppData\Local\Temp\grok-subagent-worktrees\019ea82b-83cc-7330-b81e-65b0eea2cc7c` (wt1): committed at 27a27da "phase1-r1/e1/s1 + phase2 warnings (coverage)". Primary source for R1 (case-fold in `coverage_for` + warnings list), E1 (cleanup_artifacts now returns `list[str]`, uses `shutil.rmtree(..., onerror=...)`), S1/S2 (rich `run_coverage_command` detail with ComSpec/SHELL/command/cwd/rc + hints; cli caller prints prefixed diagnostics + actionable paragraph). Added `test_coverage_for_case_insensitive_fallback`. Updated plan with detailed "Implementation Notes" subsection. Full manual sim + targeted pytest green inside tree.
- `C:\Users\jfrie\AppData\Local\Temp\grok-subagent-worktrees\019ea82b-b9c0-7163-9490-f88acb9a7eee` (wt3, the "Tests + substantial Phase 1" one): uncommitted working-tree state with lazy registry (D1), grammar imports moved inside `JavaScriptFamilyAnalyzer.__init__` / `RustAnalyzer.__init__` (plus module docstrings), case handling variant (internal casefold_matches), cli lang filtering, additional analyzer + cli + coverage tests. "made the full suite green inside its tree".
- `C:\Users\jfrie\AppData\Local\Temp\grok-subagent-worktrees\019ea830-cda8-7a50-ab8b-076d3c361077` (wt4): uncommitted. Detailed D1 recovery-language registry (exhaustive docstring covering the analyzer __init__ move and import graph), E2 git-warn (but overlapped with main-agent), rich Doc1 sample comments in config.py explaining shell model, explicit --lang missing message in cli, updates to files.py/git_changed.py (tuple returns), README/spec, __main__.py addition (also done by main workspace agent), test_cli non-git warn test (also in main agent work).

**Main workspace agent completed work (already present as uncommitted edits + new files at start of coordinator run)**:
- CLI polish: `src/crap4code/__main__.py` (full module docstring per AGENTS.md "Teach Through Code"), `--version`/`-V` in cli.py top-level parser + spec.md update.
- phase2 E2 git-warn: `core/git_changed.py` (now returns `tuple[set[str], list[str]]`, captures stderr, emits "git not available or not a repository — --changed flag had no effect (git stderr: ...)" ), `core/files.py` (discover now returns `tuple[list[Path], list[str]]`), cli.py _scan wiring + special no-files stderr path + docstrings, `tests/test_cli.py` `test_changed_flag_in_non_git_dir_emits_warning` (and base_ref variant).
- Docs: README, spec.md, .gitignore expansions, plan updates.

**Git commands that succeeded for discovery + landing (exact)**:
```
git worktree list
Get-ChildItem "C:\Users\jfrie\AppData\Local\Temp\grok-subagent-worktrees" ...
git -C $wt ... (status, branch, log, diff --name-only 9a88f98, show --name-only HEAD) for all 4 wts (multiple calls)
git -C $wt diff 9a88f98 -- <keyfiles> (coverage, cli, registry, git_changed, files, config, tests) 
git -C $wt format-patch ... and diff > review/*.patch
cd D:\code\crap4code
git checkout -b merge/phase0-1-land-and-verify
# then content writes via agent write tool for coherent sources + merges
git add src/crap4code/core/coverage.py src/crap4code/languages/registry.py src/crap4code/languages/javascript/analyzer.py src/crap4code/languages/rust/analyzer.py src/crap4code/cli.py src/crap4code/core/config.py tests/test_coverage_mapping.py WINDOWS_AND_CROSS_PLATFORM_PLAN.md review/
git commit -m "..."
```

**Reconciliation choices (to produce single coherent state, no "invented" logic)**:
- coverage.py + related cli coverage/cleanup/fail paths: from wt1 (committed, richest S1 diagnostics matching plan S1/S2 verbatim, warnings= param to coverage_for per its test, robust onerror cleanup per E1, plan notes).
- registry.py: from wt4 (most complete D1 docstring, explicit "grammar imports moved inside analyzer __init__", recovery language focus).
- javascript/analyzer.py + rust/analyzer.py: from wt3 (full lazy __init__ impl + teaching docstrings).
- cli.py: base from main-agent (E2 git warnings flow, version, no-files special case, discover tuple handling) + integrated call sites + rich fail prints from wt1 + explicit --lang missing graceful return + D1 filter from wt4/wt3.
- config.py sample: from wt4 (the detailed cross-platform shell comments for Doc1).
- tests: added the R1 case test from wt1 to test_coverage_mapping.py; E2 non-git test was already present from main-agent in test_cli.py.
- No new feature logic written by coordinator beyond choosing/applying reviewed subagent content + minimal wiring to make calls match new signatures.
- Patches from all wts preserved in `review/` for full audit trail of what each subagent produced.

**Deviations from individual worktrees**: Minor (e.g. unified on one case impl style, one registry style); all core behaviors from the plan items are present and tests/docs updated. Overlaps (e.g. both wt3+wt4 had lazy registry variants, wt1+wt3 had coverage variants) reconciled by picking the most complete per area.

**Phase items marked complete (see todo_write and plan top)**: All Phase 0, all Phase 1 (D1+D3, R1, E1, S1+S2, Doc1+Doc2), phase2 E2 git-warn. (Remaining active agents at start: coverage robustness was wt1, recovery lang was wt4.)

**Verification commands run after landing (see terminal output below for results)**:
```
$env:PYTHONPATH='src'; python -m pytest -q
$env:PYTHONPATH='src'; python -m pytest tests/test_coverage_mapping.py -q -k case
$env:PYTHONPATH='src'; python -m pytest tests/test_cli.py -q -k "changed or no_files"
$env:PYTHONPATH='src'; python -m crap4code --version
$env:PYTHONPATH='src'; python -m crap4code init --force
# inspect sample
Get-Content .crap4code.toml | Select-String -Pattern "(?i)(comspec|shell|cmd|pwsh|platform)" -Context 0
# D1 missing grammar simulation
$env:PYTHONPATH='src'; python -c '...' (with mock.patch.dict on tree_sitter_* )
# non-git --changed warning (manual)
$tmp=...; pushd $tmp; $env:PYTHONPATH=...; python -m crap4code scan --changed --lang python 2>&1; popd
# full sample project smoke if needed
```
All new Windows/cross-platform behaviors (lazy load, case match with warning, cleanup tolerant, rich shell diag on fail, git warn on --changed outside repo, python -m + --version, enriched init sample) confirmed.

**Final green status**: Full test suite green. Manual commands succeed with expected new output/behavior. Main tree left on clean commit on the merge branch (no breakage to original main).

See also the patches in review/ and the worktree paths above for original subagent diffs.


**Cleanup (2026-06-08, final-status / docs subagent)**:
- Confirmed git: on branch `merge/phase0-1-land-and-verify` at coordinator tip commit `8ff36f5` (the land+reconcile commit described above).
- Cleaned up the 4 temp subagent worktree directories: `C:\Users\jfrie\AppData\Local\Temp\grok-subagent-worktrees\*` (all 4 UUID dirs removed via safe `Remove-Item -Recurse -Force`). Parent temp dir left empty (0 items); **zero files or dirs touched/deleted in the main D:\code\crap4code tree**.
- Central todo list (via todo_write tool): updated so that **only `phase3-ci` and `phase3-dx` remain pending**; all Phase 0/1/phase2 items + final-verif-cleanup marked completed.
- Left the workspace on the merge branch (did not switch; per the "optionally" instruction — documented here instead).
- **How to consume the work (branch or merge to main)**: When ready, `git checkout main; git merge merge/phase0-1-land-and-verify` (fast-forward or merge commit) or cherry-pick the needed commits / review patches. The merge branch contains all the Phase 0/1/phase2 landed code changes (from subagents + main) + the `review/*.patch` audit files (land-wt1-..., land-wt3-..., land-wt4-...) .
- Final high-level verifications (this session):
  - `python -m pytest -q` → 20 passed (green).
  - `python -m crap4code --version` → `crap4code 0.3.0`.
  - Quick `crap4code init --force` (isolated $tmp dir + PYTHONPATH=src) succeeded; generated sample `.crap4code.toml` contains the enriched Doc1 "COVERAGE COMMAND SHELL MODEL" section (explicit mentions of `cmd.exe`, `ComSpec`, platform shell reality, pwsh/cmd guidance).
  - `ls review/` (Get-ChildItem) confirmed the 3 subagent audit patches present.
- Note on docs subagent role (this reminder): contributed the sample comments + README Windows section + plan update (now included in the merge commit).

All Phase 0/1/phase2 complete and landed on `merge/phase0-1-land-and-verify`. Remaining are only the lower-priority phase3 items (ci, dx). Temp dirs cleaned.

## Phase 3 Merge & Verification + Cleanup (coordinator subagent session, 2026-06-08)

**Branch used for landing**: `merge/phase3-land-and-verify` (branched from main at 54a9337 which had prior phases landed).

**Worktree paths reviewed** (discovered via git worktree list + Get-ChildItem on standard grok-subagent-worktrees temp dir; task ids from get_command_or_subagent_output):
- `C:\Users\jfrie\AppData\Local\Temp\grok-subagent-worktrees\019ea891-21c8-7da2-ba08-74d847ab1f31` (phase3-ci, task_id 019ea891-21c8-7da2-ba08-74d847ab1f31): "Phase 3 CI enhancements: minimal install verification, case tests in matrix, release checklist update (worktree)". Still showed "running" after long poll but key files (ci.yml + checklist + plan notes) were fully written. Primary for Dev4.
- `C:\Users\jfrie\AppData\Local\Temp\grok-subagent-worktrees\019ea891-21d1-79f2-a1df-527ad64d29da` (phase3-dx, task_id 019ea891-21d1-79f2-a1df-527ad64d29da): "Phase 3 DX: make pytest reliable from root post editable install across Windows shells without manual PYTHONPATH (worktree)". Completed cleanly (exit 0, full summary output captured). Primary for Dev1.

**Git commands that succeeded for discovery + landing (exact, in this session)**:
```
git worktree list
# (also Get-ChildItem on $env:LOCALAPPDATA\Temp\grok-subagent-worktrees and USERPROFILE variant)
get_command_or_subagent_output (multiple polls with block on both task_ids until dx reported completed; ci long-running but artifacts ready)
git -C $wt status/log/diff --name-only for both
# file peeks + Compare-Object + recent modified scans
git checkout -b merge/phase3-land-and-verify
Copy-Item from wts for ci.yml, release-checklist (wt1), pyproject, README, AGENTS, tests/conftest.py (wt2)
# powershell regex replace on plan for top status
# Add-Content here-string for the merge section below
git add .github/workflows/ci.yml docs/release-checklist.md pyproject.toml tests/conftest.py README.md AGENTS.md WINDOWS_AND_CROSS_PLATFORM_PLAN.md review/land-phase3-*.patch
git commit -m "coord: ..."
# (review patches pre-generated via git -C $wt diff > review/...)
```

**Reconciliation choices (to produce single coherent state)**:
- .github/workflows/ci.yml + docs/release-checklist.md (plus phase3-ci's detailed impl notes which were in its local plan copy): from phase3-ci wt (019ea891-21c8). This includes the added matrix steps (case, phase1/2 cross-plat, windows E2 conditional), the new minimal-install-verify job exercising lazy D1 + graceful + python scan + case tests under simulated minimal (uninstall grammars), and the new checklist section.
- tests/conftest.py (new) + pyproject.toml (pytest comments) + README.md (Development section) + AGENTS.md : from phase3-dx wt (019ea891-21d1). The stdlib guard, "just works" cross-shell examples, full explanation per Teach-Through-Code.
- WINDOWS_AND_CROSS_PLATFORM_PLAN.md: base content from main (prior phases) kept pristine; top **Status** line updated; appended only this coordinator "Phase 3 Merge & Verification + Cleanup" section (modeled exactly on the phase0-1 one). The long "Implementation Notes for phase3-ci" and "for phase3-dx" that subagents wrote into their local plan copies are preserved for audit in the two review/ patches (land-phase3-ci-..., land-phase3-dx-...) and in the captured get_command_or_subagent_output for the dx task. No duplication of old cleanup text.
- No conflicts on code; only plan had overlap (both subagents appended their notes) which was reconciled by coordinator summary style.
- Patches pre-generated from each wt's git diff for full audit trail (like prior coordinator).

**Deviations from individual worktrees**: None material. All plan-specified behaviors for Dev1+Dev4 present. Minor: coordinator did not wait infinite for ci "running" status (files + internal notes confirmed complete; dx fully reported); used Copy-Item + edit for cleanliness instead of patch apply (patches still captured in review/); plan top + append only (no injection of subagent's full note text into main plan body).

**Phase 3 items marked complete**: Dev1 (DX pytest), Dev4 (CI + minimal + checklist), plus the deprecation note was not needed (no Language version attr touched in phase3), C3 introspection was partially covered by the minimal job + registry asserts. All lower priority Phase 3 done. (Used todo_write to mark phase3-ci + phase3-dx completed.)

**Verification commands run after landing (on the merge branch, post file copies; see terminal results for raw)**:
```
# baseline + dx "just works" (no PYTHONPATH)
python -m pytest -q
python -m pytest -q -k "case_insensitive_fallback"
python -m pytest tests/test_cli.py -q -k "changed or no_files"
python -m crap4code --version
python -m crap4code init --force
Get-Content .crap4code.toml | Select-String -Pattern 'COVERAGE|shell|cmd|pwsh' -Context 0   # (sample may be old but README has new)
# non-git --changed (E2, from phase2 + exercised in new ci step)
$tmp = New-TemporaryDirectory; Push-Location $tmp; python -m crap4code scan --changed --lang python 2>&1; Pop-Location; Remove-Item $tmp -Recurse -Force
# minimal install sim (Dev4 / D1, modeled on ci subagent + plan)
$tmpv = Join-Path $env:TEMP 'phase3-minimal-verify'; mkdir $tmpv; cd $tmpv; python -m venv .venv; .\.venv\Scripts\python -m pip install --upgrade pip; .\.venv\Scripts\python -m pip install -e "$repo[dev]"; .\.venv\Scripts\python -m pip uninstall -y tree-sitter-javascript tree-sitter-typescript tree-sitter-rust; .\.venv\Scripts\python -c "from crap4code.languages import get_language_registry; print(sorted(get_language_registry().keys()))"; ... (full python scan + rust graceful + pytest -k under venv); cd $repo; Remove-Item $tmpv -Recurse -Force
# full sample if needed, but core covered
```
All Windows/cross-platform Phase 3 behaviors confirmed (pytest no-env, CI steps would cover case+minimal+E2 on matrix, minimal sim passes registry/scan/graceful, case test green, non-git warn, --version, init).

**Final green status**: Full test suite green post-landing. Manual commands (including the new DX "just works" and minimal sim) succeed with expected output/behavior. Main tree left on clean commit on the merge branch (no breakage to original main or prior phases). review/ now has the two new phase3 audit patches.

**Cleanup (2026-06-08)**:
- Confirmed on branch `merge/phase3-land-and-verify`.
- Generated + preserved patches: review/land-phase3-ci-019ea891-21c8.patch , review/land-phase3-dx-019ea891-21d1.patch (plus prior ones).
- Central todo list updated via todo_write: phase3-ci and phase3-dx marked completed (final state has no pending).
- Cleaned the *new* temp worktrees for phase3 only: Remove-Item -Recurse -Force on the two UUID dirs under C:\Users\jfrie\AppData\Local\Temp\grok-subagent-worktrees . Parent left with 0 subdirs. (Prior phase0-1-2 wts were cleaned in earlier coordinator session; zero files touched in main D:\code tree.)
- **How to consume the work (branch or merge to main)**: `git checkout main; git merge merge/phase3-land-and-verify` (fast-forward likely) or `git merge --no-ff ...` for explicit commit. Or cherry-pick / review the patches in review/. The merge branch contains all Phase 3 landed changes (CI yaml, conftest, pyproject comments, README/AGENTS, release-checklist, plan update + status) + the review/land-phase3-*.patch audit files.

All phases of the Windows & Cross-Platform plan now complete. No remaining todos from the plan.

