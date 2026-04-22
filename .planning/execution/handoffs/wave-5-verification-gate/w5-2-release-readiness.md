# W5-2 Handoff

## Status

- `done`

## What Changed

- Added GitHub Actions for CI and tag-triggered releases.
- Added checked-in sample repos for Python, JavaScript, Rust, and mixed-language end-to-end validation.
- Added release checklist documentation and bumped the package to `0.3.0`.

## Files

- .github/workflows/ci.yml
- .github/workflows/release.yml
- docs/release-checklist.md
- tests/sample_projects/**

## Verification

- .\.venv\Scripts\python -m pytest -q: pass
- .\.venv\Scripts\python -m build: pass
- .\.venv\Scripts\python -m twine check dist/*: pass

## Blockers Or Risks

- The GitHub release workflow can publish to PyPI only if `PYPI_API_TOKEN` is configured in the repository secrets.
- Tree-sitter wheel availability still matters for target Python/platform combinations.

## Next Thread Should Know

- The intended first release tag after this pass is `v0.3.0`.
- Checked-in sample repos are the fastest way to verify CLI behavior without generating fresh coverage artifacts.
