from __future__ import annotations

from pathlib import Path
import subprocess


_GIT_COMMANDS = (
    ("git", "diff", "--name-only", "--diff-filter=ACMRTUXB"),
    ("git", "diff", "--name-only", "--cached", "--diff-filter=ACMRTUXB"),
    ("git", "ls-files", "--others", "--exclude-standard"),
)


def get_changed_files() -> set[str]:
    changed: set[str] = set()
    for command in _GIT_COMMANDS:
        try:
            proc = subprocess.run(command, check=False, capture_output=True, text=True)
        except OSError:
            continue
        if proc.returncode != 0:
            continue
        for line in proc.stdout.splitlines():
            line = line.strip()
            if line:
                changed.add(Path(line).as_posix())
    return changed
