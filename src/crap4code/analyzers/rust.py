from __future__ import annotations

import re
from pathlib import Path

from crap4code.core.files import discover_source_files
from crap4code.core.models import FunctionMetrics

_FN_PATTERN = re.compile(r"^\s*(?:pub\s+)?(?:async\s+)?fn\s+([A-Za-z_][A-Za-z0-9_]*)\b")
_IMPL_PATTERN = re.compile(r"^\s*impl(?:<[^>]+>)?\s+([A-Za-z_][A-Za-z0-9_]*)")
_COMPLEXITY_PATTERN = re.compile(r"\b(if|match|for|while|loop)\b|&&|\|\|")


class RustAnalyzer:
    language = "rust"

    def discover_files(self, explicit_paths: list[str], changed_only: bool) -> list[Path]:
        return discover_source_files(
            explicit_paths, extensions=(".rs",), changed_only=changed_only)

    def analyze(self, files: list[Path]) -> list[FunctionMetrics]:
        rows: list[FunctionMetrics] = []
        for file_path in files:
            try:
                lines = file_path.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue

            current_impl = "module"
            impl_depth = 0
            for idx, line in enumerate(lines, start=1):
                impl_match = _IMPL_PATTERN.search(line)
                if impl_match:
                    current_impl = impl_match.group(1)
                    impl_depth = line.count("{") - line.count("}")
                    if impl_depth <= 0:
                        current_impl = "module"
                        impl_depth = 0
                    continue

                if impl_depth > 0:
                    impl_depth += line.count("{") - line.count("}")
                    if impl_depth <= 0:
                        current_impl = "module"
                        impl_depth = 0

                match = _FN_PATTERN.search(line)
                if not match:
                    continue

                function_name = match.group(1)
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

                complexity = 1
                for body_line in lines[idx - 1 : end]:
                    complexity += len(_COMPLEXITY_PATTERN.findall(body_line))

                rows.append(
                    FunctionMetrics(
                        language="rust",
                        file_path=file_path.as_posix(),
                        container=current_impl,
                        function_name=function_name,
                        line=idx,
                        complexity=complexity,
                        coverage_percent=None,
                        crap_score=None,
                    )
                )

        return rows
