"""Coverage ingestion, cleanup, and per-function range mapping."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import subprocess
import xml.etree.ElementTree as ET


@dataclass(slots=True)
class CoverageDatabase:
    """Line-hit database derived from a coverage report.

    The database is intentionally language-agnostic. Language adapters are
    responsible for producing trustworthy function ranges, and this class maps
    those ranges onto the coverage line hits emitted by coverage tools.
    """

    line_hits_by_file: dict[str, dict[int, int]]

    def coverage_for(self, file_path: str, start_line: int, end_line: int) -> tuple[str, float | None]:
        """Return a stable coverage state and percentage for a function range."""

        lines = self.line_hits_by_file.get(file_path)
        if not lines:
            return ("indeterminate", None)

        relevant = [hits for line, hits in lines.items() if start_line <= line <= end_line]
        if not relevant:
            return ("indeterminate", None)

        covered = sum(1 for hits in relevant if hits > 0)
        percent = (covered / len(relevant)) * 100.0
        return ("measured", percent)


def normalize_repo_path(path: str | Path, root: Path) -> str:
    """Normalize any path into a repo-relative POSIX path when possible."""

    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        return candidate.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return candidate.resolve().as_posix()


def _parse_coverage_xml(report_path: Path, root: Path) -> CoverageDatabase:
    """Read ``coverage.py`` XML into a line-hit database."""

    tree = ET.parse(report_path)
    line_hits_by_file: dict[str, dict[int, int]] = {}

    for class_node in tree.findall(".//class"):
        filename = class_node.attrib.get("filename")
        if not filename:
            continue
        normalized = normalize_repo_path(filename, root)
        bucket = line_hits_by_file.setdefault(normalized, {})
        for line_node in class_node.findall("./lines/line"):
            line_number = line_node.attrib.get("number")
            hits = line_node.attrib.get("hits")
            if not line_number or not hits:
                continue
            bucket[int(line_number)] = int(hits)

    return CoverageDatabase(line_hits_by_file=line_hits_by_file)


def _parse_lcov(report_path: Path, root: Path) -> CoverageDatabase:
    """Read LCOV into a line-hit database for JS/TS and Rust workflows."""

    line_hits_by_file: dict[str, dict[int, int]] = {}
    current_file: str | None = None

    for raw_line in report_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("SF:"):
            current_file = normalize_repo_path(line[3:], root)
            line_hits_by_file.setdefault(current_file, {})
            continue
        if line.startswith("DA:") and current_file:
            line_number, hits = line[3:].split(",", maxsplit=1)
            line_hits_by_file[current_file][int(line_number)] = int(hits)
            continue
        if line == "end_of_record":
            current_file = None

    return CoverageDatabase(line_hits_by_file=line_hits_by_file)


def load_coverage_database(
    root: Path,
    report_path: str | None,
    report_format: str | None,
) -> CoverageDatabase | None:
    """Load a coverage database when the configured report exists.

    Unknown or missing coverage reports are treated as absent instead of causing
    the whole scan to fail because agents still benefit from complexity-only
    guidance with an explicit indeterminate coverage warning.
    """

    if not report_path or not report_format:
        return None

    candidate = Path(report_path)
    resolved = candidate if candidate.is_absolute() else root / candidate
    if not resolved.exists():
        return None

    normalized_format = report_format.strip().lower()
    if normalized_format == "coverage.py-xml":
        return _parse_coverage_xml(resolved, root)
    if normalized_format == "lcov":
        return _parse_lcov(resolved, root)
    raise ValueError(f"Unsupported coverage format: {report_format}")


def cleanup_artifacts(root: Path, artifact_paths: list[str]) -> None:
    """Delete configured stale artifacts before running coverage."""

    for artifact in artifact_paths:
        candidate = Path(artifact)
        resolved = candidate if candidate.is_absolute() else root / candidate
        if resolved.is_dir():
            for nested in sorted(resolved.rglob("*"), reverse=True):
                if nested.is_file():
                    nested.unlink(missing_ok=True)
                elif nested.is_dir():
                    nested.rmdir()
            resolved.rmdir()
        elif resolved.exists():
            resolved.unlink()


def run_coverage_command(root: Path, command: str) -> tuple[bool, str]:
    """Run a configured coverage command.

    Returns:
        A tuple of ``(success, detail)`` where detail contains either the
        command's stdout/stderr or the spawn failure.
    """

    try:
        completed = subprocess.run(
            command,
            cwd=root,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
    except OSError as exc:
        return (False, str(exc))

    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
    return (completed.returncode == 0, output)
