from __future__ import annotations

from pathlib import Path
from typing import Protocol

from crap4code.core.models import FunctionMetrics


class Analyzer(Protocol):
    language: str

    def discover_files(self, explicit_paths: list[str], changed_only: bool) -> list[Path]:
        ...

    def analyze(self, files: list[Path]) -> list[FunctionMetrics]:
        ...
