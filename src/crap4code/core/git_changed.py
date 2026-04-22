"""Git changed-file helpers for local and CI-style scans."""

from __future__ import annotations

from pathlib import Path
import subprocess


_LOCAL_GIT_COMMANDS = (
    ("git", "diff", "--name-only", "--diff-filter=ACMRTUXB"),
    ("git", "diff", "--name-only", "--cached", "--diff-filter=ACMRTUXB"),
    ("git", "ls-files", "--others", "--exclude-standard"),
)


def get_changed_files(root: Path, base_ref: str | None = None) -> set[str]:
    """Return changed repo-relative paths using either local or CI semantics."""

    changed: set[str] = set()
    commands = (
        (("git", "diff", "--name-only", f"{base_ref}...HEAD", "--diff-filter=ACMRTUXB"),)
        if base_ref
        else _LOCAL_GIT_COMMANDS
    )

    for command in commands:
        try:
            completed = subprocess.run(
                command,
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError:
            continue

        if completed.returncode != 0:
            continue

        for raw_line in completed.stdout.splitlines():
            line = raw_line.strip()
            if line:
                changed.add(Path(line).as_posix())

    return changed
