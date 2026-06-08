# Release Checklist

Repo path: `D:\code\crap4code`

## Pre-Release

- run `python -m pip install -e .[dev]`
- run `python -m pytest -q`
- run `python -m build`
- run `python -m twine check dist/*`
- confirm `README.md`, `spec.md`, and `docs/contracts.md` still match the CLI behavior
- confirm `docs/user-guide/README.md` (the guide index) has working hierarchical TOC + sibling links (to getting-started.md, configuration.md, concepts.md, usage.md, troubleshooting.md) and back-links to root `README.md` / `spec.md` / `docs/contracts.md` etc.
- confirm checked-in sample repos under `tests/sample_projects/` still pass their release-readiness tests

## Tagging

- bump version in `pyproject.toml` and `src/crap4code/__init__.py`
- commit the release changes
- create a tag like `v0.3.0`
- push the commit and tag

## GitHub Actions

- CI workflow: test matrix plus package build and twine validation
- Release workflow: build artifacts, create GitHub release, optionally publish to PyPI if a token exists

## Cross-Platform / Windows Verification (phase3-ci / Dev4)

- Test minimal/python-only install scenario:
  - `python -m pip install -e .[dev]`
  - `python -m pip uninstall -y tree-sitter-javascript tree-sitter-typescript tree-sitter-rust`
  - `python -c "from crap4code.languages import get_language_registry; print(sorted(get_language_registry().keys()))"`  (must be only ['python'])
  - Verify full scan works for python (e.g. in a temp dir with a .py file + `python -m crap4code scan --lang python --report-only`)
  - `python -m crap4code scan --lang rust` fails gracefully with message containing "Rust support requires `pip install tree-sitter-rust`"
- Verify case tests and graceful language loading:
  - `python -m pytest -q -k "case_insensitive_fallback"`
  - `python -m pytest -q -k "unavailable_lang or changed_flag_in_non_git_dir_emits_warning"`
- Run on clean Windows without full grammars (CI minimal job + local):
  - Use a fresh Windows checkout + python; repeat the minimal uninstall + registry + python-scan + rust-graceful checks above.
  - Confirm the E2 non-git --changed warning test runs: `python -m pytest -q -k "changed_flag_in_non_git_dir_emits_warning"`
- The enhanced CI (ci.yml) now includes the matrix case/phase1 tests + explicit windows non-git step + dedicated minimal-install-verify job.

## Release v0.4.0 (executed 2026-06-08)
- Version bumped 0.3.0 -> 0.4.0 in pyproject.toml + src/crap4code/__init__.py
- CHANGELOG.md created (comprehensive Keep a Changelog entry for Phases 0-3 Windows/cross-platform completion, drafted/prepared by subagent 019ea90e-57f6-7aa0-9a8c-d42541b111ac using plan + git history + patches + reads)
- Pre-release local verification (per checklist): `python -m pip install -e .[dev]`, `python -m pytest -q` (21 passed), `python -m build`, `python -m twine check dist/*` (PASSED)
- Committed as 0130258f0b865502ed2f980f38ccf3e9fe43ccfc "chore(release): bump to 0.4.0 and update changelog"
- Annotated tag: `git tag -a v0.4.0 -m "Release v0.4.0 - Windows and cross-platform improvements per plan"`
- Pushed: `git push origin main --tags` (SUCCESS; main 9a88f98..0130258 + new tag v0.4.0)
- GitHub release workflow (`.github/workflows/release.yml`) triggered automatically by tag push (on: push tags v*). Job: build-release on ubuntu-latest (checkout, pip -e.[dev], pytest, build, twine check, softprops/action-gh-release with generate_release_notes + dist/* artifacts, conditional pypa publish if PYPI_API_TOKEN secret present).
- Current PyPI: still 404 (no project yet; will be first publish via workflow if token configured in repo secrets).
- Untracked files (probes, mcps/, temps, user .crap4code.toml) left untouched per "handle untracked" guidance.
- See CHANGELOG.md (root), full plan, review/*.patch for audit, docs/release-checklist.md .

## YAML Workflow Parse Error - Diagnosis Note (added 2026-06-08 by workflow-validator subagent, parallel to fixer)
- Root cause: phase3-ci (see review/land-phase3-ci-019ea891-21c8.patch and WINDOWS_AND_CROSS_PLATFORM_PLAN.md impl notes) added a complex inline verification under the new "minimal-install-verify" job:
  - name: Verify python scan works + --lang rust fails gracefully (real minimal)
    run: |
      python - << 'PYEOF'
import contextlib   <--- col 0 (outdented)
... (50+ lines of python at col 0)
PYEOF
- The opener "python - << 'PYEOF'" line is indented (under run: | block scalar, ~10 spaces), but the payload + closer "PYEOF" are at column 0 in .github/workflows/ci.yml .
- This violates YAML block scalar indentation rules (all continuation lines of | must be >= the indent of the block's first content line; lesser indent ends the scalar prematurely and makes following content invalid in the jobs/steps mapping/sequence).
- Confirmed locally via:
  - read_file + grep ^ patterns showing "import contextlib" and "PYEOF" with 0 leading ws while run:/python line have indent.
  - The landed patch shows the + lines for code starting immediately after + (no ws).
  - Remote raw on main matches.
- Exact reproduction of yaml.safe_load failure (using PyYAML): ParserError / ScannerError around the "import" line or "while parsing a block mapping" / "did not find expected key" / "could not find expected ':' " (depending on exact pyyaml version; GH parser gives equivalent "Invalid workflow file: .github/workflows/ci.yml#L71" + "Unexpected value" or "A mapping was not expected").
- Impact on ALL runs: GitHub parses/validates *every* .github/workflows/*.yml on *any* push (including tag pushes that only intend to trigger release.yml, and doc pushes to main). A single bad file (ci.yml) causes the entire check/run to fail with "YAML file errors", "workflow failed to start", conclusion=failure -- even for release runs. Confirmed by API: recent runs e.g. 27167220355 (release.yml), 27167220057 (ci.yml), 27167209207 etc. all conclusion=failure; their /jobs endpoints return 0 jobs (pre-dispatch parse failure, no jobs created).
- release.yml itself: clean, no issues (standard steps, correct 2-space indents, valid if:, no heredoc, matrix n/a). See full read.
- Other potential problems checked (none other fatal):
  - if: conditions (e.g. if: matrix.os == 'windows-latest') correctly placed under step, good.
  - matrix: and ${{ matrix.* }} refs correct in test job.
  - New phase3-ci steps (case tests, cross-plat -k, windows E2 conditional, minimal job steps) have correct step-level indentation and structure; only the one heredoc payload inside | is broken.
  - No secret if: issues (the one in release is common pattern).
  - No tab chars or other obvious.
- Minimal diff fix options (for the parallel fixer):
  1. Preferred (teach-through-code, robust): extract the ~50 line verify to e.g. scripts/verify_minimal.py (with module docstring, structured comments per AGENTS), then in ci.yml: run: python scripts/verify_minimal.py  (simple, no yaml heredoc, committed+testable code).
  2. In-place minimal: wrap the heredoc command with python -c + textwrap.dedent(stdin) shim + indent the entire payload+PYEOF lines in ci.yml to match the run block indent; update the opener to python -c "import sys,textwrap;exec(textwrap.dedent(sys.stdin.read()))" << 'PYEOF'  (then payload indented).
  3. Avoid future: never use << 'XXX' inside yaml | for multi-line code blocks with top-level (0-indent) content; use committed scripts or exec(dedent('''...''')) with yaml-indented code.
- The fix from parallel fixer subagent (whatever chosen) will make ci.yml valid yaml again; all future pushes (incl release tags) will then have clean workflow runs (assuming other content ok). This note added to checklist for audit + future release awareness.
- See also: .github/workflows/ci.yml:69 (the run: |), raw on github, the phase3-ci patch, jobs=0 on the 27167... runs from GH API.
