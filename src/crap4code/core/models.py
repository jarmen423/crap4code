from dataclasses import dataclass


@dataclass(slots=True)
class FunctionMetrics:
    language: str
    file_path: str
    container: str
    function_name: str
    line: int
    complexity: int
    coverage_percent: float | None = None
    crap_score: float | None = None
