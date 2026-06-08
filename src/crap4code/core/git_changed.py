"""Git changed-file helpers for local and CI-style scans.

This module is intentionally small and defensive. It never raises to callers
and previously swallowed all git failures (OSError for missing binary, non-zero
rc for "not a repo", bad refs, etc.), returning an empty set with zero
observability. That made `--changed` silently do nothing (common on Windows CI
runners or when running from a temp dir outside any git worktree).

Phase 2 (E2) change: we now capture stderr on all paths, and return warnings
alongside the changed set so the CLI can surface them in the report.warnings
(JSON + table) and on stderr. The warning text is chosen to be actionable for
both humans and agents.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Only for type checkers; runtime uses the tuple annotation which works
    # with from __future__ annotations.
    pass


_LOCAL_GIT_COMMANDS = (
    ("git", "diff", "--name-only", "--diff-filter=ACMRTUXB"),
    ("git", "diff", "--name-only", "--cached", "--diff-filter=ACMRTUXB"),
    ("git", "ls-files", "--others", "--exclude-standard"),
)


def get_changed_files(root: Path, base_ref: str | None = None) -> tuple[set[str], list[str]]:
    """Return changed repo-relative paths using either local or CI semantics.

    Returns a tuple of (changed_paths_set, warnings_list).

    The warnings_list is empty on success. On any git-related failure it
    contains one (or more, if somehow multiple distinct failures) clear
    diagnostic message(s). These are propagated by discover_source_files into
    the CLI's warnings list so they appear in structured output and on stderr.

    This change implements Issue E2 / phase2-git-warn from the Windows &
    cross-platform plan: "Git operations are completely silent on failure".

    Failure modes covered defensively (no assumptions about environment):
    - OSError: git binary not present on PATH (or exec denied). Common if
      Git for Windows not installed or PATH issues on the agent runner.
    - returncode != 0: not a git repository, or the specific git command
      failed (e.g. bad --base-ref, shallow clone issues, permission, etc.).
      The stderr from git is captured and a snippet is included so the
      *exact* reason is visible to the user/agent (e.g. the classic
      "fatal: not a git repository (or any of the parent directories): .git").

    Stderr (not just rc) is the key for observability on Windows CI.

    The function still never raises; it is safe for callers in any cwd.
    """

    changed: set[str] = set()
    git_warnings: list[str] = []

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
        except OSError as exc:
            # Git binary not found (or other OS-level exec failure).
            # We warn only on the first such event; all commands would fail
            # identically if the binary is absent.
            if not git_warnings:
                git_warnings.append(
                    f"git not available or not a repository — --changed flag had no effect (OSError: {exc})"
                )
            continue

        if completed.returncode != 0:
            # Git ran but the command failed (most common: not a repo at all,
            # which produces rc=128 + stderr containing "fatal: not a git
            # repository..."). Include a bounded stderr snippet for diagnosis.
            if not git_warnings:
                stderr_snippet = (completed.stderr or "").strip()
                msg = "git not available or not a repository — --changed flag had no effect"
                if stderr_snippet:
                    # Keep the snippet reasonably short but useful.
                    snippet = stderr_snippet[:300]
                    msg = f"{msg} (git stderr: {snippet})"
                git_warnings.append(msg)
            continue

        for raw_line in completed.stdout.splitlines():
            line = raw_line.strip()
            if line:
                changed.add(Path(line).as_posix())

    return changed, git_warnings
