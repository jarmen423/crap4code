"""File discovery helpers shared by all language adapters.

This module walks the filesystem for source files (respecting explicit paths
vs. config default_paths and language extensions) and optionally intersects
with git-changed files when the --changed / --base-ref flags are used.

The intersection logic lives in core/git_changed.py. As of phase2-git-warn,
get_changed_files (and therefore this function when changed_only=True) can
return non-fatal warning messages. Those are returned alongside the file list
so the CLI can feed them into the shared warnings collection used by reports
and stderr output. See cli.py:_scan and the E2 section of the plan.
"""

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
) -> tuple[list[Path], list[str]]:
    """Discover candidate source files for a language adapter.

    Args:
        root: Repo root used for relative path resolution.
        explicit_paths: CLI-supplied file or directory arguments.
        default_paths: Config-resolved paths used when no explicit paths exist.
        extensions: File suffixes owned by the language adapter.
        changed_only: Whether to intersect discovered files with git-changed
            paths.
        base_ref: Optional base ref for CI-style changed-file diffs.

    Returns:
        A 2-tuple: (discovered_files, warnings).

        - discovered_files: the list of Path objects after filtering.
        - warnings: list of diagnostic strings (empty on the happy path).
          When changed_only=True and git operations cannot determine a change
          set (no git, not a repo, bad ref, etc.), this will contain a message
          such as "git not available or not a repository — --changed flag had
          no effect (git stderr: ...)" and the file list will be the empty
          intersection. The warnings are later merged into the scan report
          (see build_report + cli._scan) so they appear in both human table
          output, --format json, and on stderr.

    The return of warnings (instead of only the list) is the minimal API
    surface change required to implement observable git failures per the plan
    while keeping all other discovery behavior identical.
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
        return files, []

    changed, git_warnings = get_changed_files(root=root, base_ref=base_ref)
    filtered = [path for path in files if normalize_repo_path(path, root) in changed]
    return filtered, git_warnings
