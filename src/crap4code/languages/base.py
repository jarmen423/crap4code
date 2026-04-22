"""Language adapter protocol."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from crap4code.core.models import FunctionMetrics


@dataclass(frozen=True, slots=True)
class LanguageDefinition:
    """Resolved runtime information for a supported language."""

    key: str
    extensions: tuple[str, ...]
    analyzer: "Analyzer"


class Analyzer(Protocol):
    """Protocol implemented by every language-specific analyzer."""

    language: str
    extensions: tuple[str, ...]

    def analyze(self, root: Path, files: list[Path]) -> list[FunctionMetrics]:
        """Analyze source files and return per-function metrics."""
