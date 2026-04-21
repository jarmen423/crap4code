from __future__ import annotations

import re
from pathlib import Path

from crap4code.core.files import discover_source_files
from crap4code.core.models import FunctionMetrics

_FUNCTION_PATTERNS = (
    re.compile(r"^\s*function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("),
    re.compile(
        r"^\s*(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>"
    ),
)

_COMPLEXITY_PATTERN = re.compile(r"\b(if|for|while|catch|case)\b|\?|&&|\|\||\?\?")


class JSFamilyAnalyzer:
    def __init__(self, language: str) -> None:
        self.language = language

    def discover_files(self, explicit_paths: list[str], changed_only: bool) -> list[Path]:
        if self.language == "typescript":
            extensions = (".ts", ".tsx")
        else:
            extensions = (".js", ".jsx", ".mjs", ".cjs")

        return discover_source_files(
            explicit_paths, extensions=extensions, changed_only=changed_only
        )

    def analyze(self, files: list[Path]) -> list[FunctionMetrics]:
        rows: list[FunctionMetrics] = []
        for file_path in files:
            try:
                lines = file_path.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue

            for function_name, start, end in self._extract_functions(lines):
                complexity = 1
                for line in lines[start - 1 : end]:
                    complexity += len(_COMPLEXITY_PATTERN.findall(line))

                rows.append(
                    FunctionMetrics(
                        language=self.language,
                        file_path=file_path.as_posix(),
                        container="module",
                        function_name=function_name,
                        line=start,
                        complexity=complexity,
                        coverage_percent=None,
                        crap_score=None,
                    )
                )

        return rows

    def _extract_functions(self, lines: list[str]) -> list[tuple[str, int, int]]:
        functions: list[tuple[str, int, int]] = []
        for idx, line in enumerate(lines, start=1):
            name = None
            for pattern in _FUNCTION_PATTERNS:
                match = pattern.search(line)
                if match:
                    name = match.group(1)
                    break
            if not name:
                continue

            end = idx
            depth = 0
            opened = False
            for scan_idx in range(idx - 1, len(lines)):
                segment = lines[scan_idx]
                depth += segment.count("{")
                if segment.count("{"):
                    opened = True
                depth -= segment.count("}")
                end = scan_idx + 1
                if opened and depth <= 0:
                    break

            functions.append((name, idx, end))

        return functions
