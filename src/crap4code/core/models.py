"""Shared data models for scans, coverage mapping, and reporting.

These models are deliberately explicit because the tool is meant to be consumed
by both humans and coding agents. A future agent should be able to open this
file and quickly learn which pieces of data are considered part of the stable
scan contract.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class FunctionMetrics:
    """Per-function metrics emitted by every language adapter.

    Attributes:
        language: Canonical language key used by the CLI and JSON output.
        file_path: Repo-relative POSIX-style path when possible.
        container: The surrounding class, impl, or module-like owner.
        function_name: Name reported to operators and agents.
        start_line: First source line belonging to the function definition.
        end_line: Last source line belonging to the function body.
        complexity: Cyclomatic complexity style score for the function.
        coverage_percent: Coverage for the function's line range, or ``None`` if
            the report could not determine a trustworthy value.
        coverage_state: Stable string explaining whether coverage is trustworthy.
        crap_score: CRAP score when coverage is measured, else ``None``.
        risk_level: Coarse severity bucket used for sorting and recommendations.
        recommended_actions: Ordered deterministic actions an agent or human
            should consider next.
    """

    language: str
    file_path: str
    container: str
    function_name: str
    start_line: int
    end_line: int
    complexity: int
    coverage_percent: float | None = None
    coverage_state: str = "indeterminate"
    crap_score: float | None = None
    risk_level: str = "low"
    recommended_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the function result."""

        return asdict(self)


@dataclass(slots=True)
class ScanSummary:
    """Aggregated counts that help operators understand a scan at a glance."""

    scanned_files: int
    functions_found: int
    threshold: float
    threshold_exceeded: bool
    changed_only: bool
    base_ref: str | None
    by_language: dict[str, int]
    risk_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable summary payload."""

        return asdict(self)


@dataclass(slots=True)
class ScanReport:
    """Top-level report contract used by table and JSON renderers."""

    summary: ScanSummary
    functions: list[FunctionMetrics]
    recommendations: list[dict[str, Any]]
    run_metadata: dict[str, Any]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Return the stable JSON payload for ``--format json``."""

        return {
            "summary": self.summary.to_dict(),
            "functions": [row.to_dict() for row in self.functions],
            "recommendations": self.recommendations,
            "run_metadata": self.run_metadata,
            "warnings": self.warnings,
        }
