# Release Checklist

Repo path: `D:\code\crap4code`

## Pre-Release

- run `python -m pip install -e .[dev]`
- run `python -m pytest -q`
- run `python -m build`
- run `python -m twine check dist/*`
- confirm `README.md`, `spec.md`, and `docs/contracts.md` still match the CLI behavior
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
