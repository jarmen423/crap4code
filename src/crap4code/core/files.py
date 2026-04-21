from __future__ import annotations

from pathlib import Path
from collections.abc import Iterable

from .git_changed import get_changed_files


def _normalize(path: Path, cwd: Path) -> str:
    try:
        return path.resolve().relative_to(cwd.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def discover_source_files(
    explicit_paths: Iterable[str],
    *,
    extensions: tuple[str, ...],
    default_root: str = "src",
    changed_only: bool = False,
) -> list[Path]:
    cwd = Path.cwd()
    candidates: list[Path] = []

    roots = [Path(p) for p in explicit_paths] if explicit_paths else [Path(default_root)]

    for root in roots:
        if root.is_file():
            candidates.append(root)
            continue
        if root.is_dir():
            candidates.extend(root.rglob("*"))

    files = sorted(
        {
            p.resolve()
            for p in candidates
            if p.is_file() and p.suffix.lower() in extensions
        }
    )

    if changed_only:
        changed = get_changed_files()
        files = [p for p in files if _normalize(p, cwd) in changed]

    return files
