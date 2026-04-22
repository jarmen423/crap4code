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
