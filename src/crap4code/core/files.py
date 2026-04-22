"""File discovery helpers shared by all language adapters."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from crap4code.core.coverage import normalize_repo_path
from crap4code.core.git_changed import get_changed_files


def discover_source_files(
    root: Path,
    explicit_paths: Iterable[str],
    *,
    default_paths: Iterable[str],
    extensions: tuple[str, ...],
    changed_only: bool = False,
    base_ref: str | None = None,
) -> list[Path]:
    """Discover candidate source files for a language adapter.

    Args:
        root: Repo root used for relative path resolution.
        explicit_paths: CLI-supplied file or directory arguments.
        default_paths: Config-resolved paths used when no explicit paths exist.
        extensions: File suffixes owned by the language adapter.
        changed_only: Whether to intersect discovered files with git-changed
            paths.
        base_ref: Optional base ref for CI-style changed-file diffs.
    """

    candidates: list[Path] = []
    roots = [Path(item) for item in explicit_paths] if explicit_paths else [Path(item) for item in default_paths]

    for candidate_root in roots:
        resolved_root = candidate_root if candidate_root.is_absolute() else root / candidate_root
        if resolved_root.is_file():
            candidates.append(resolved_root)
            continue
        if resolved_root.is_dir():
            candidates.extend(resolved_root.rglob("*"))

    files = sorted(
        {
            candidate.resolve()
            for candidate in candidates
            if candidate.is_file() and candidate.suffix.lower() in extensions
        }
    )

    if not changed_only:
        return files

    changed = get_changed_files(root=root, base_ref=base_ref)
    return [path for path in files if normalize_repo_path(path, root) in changed]
