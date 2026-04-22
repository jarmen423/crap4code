def calculate_crap(complexity: int, coverage_ratio: float | None) -> float | None:
    if coverage_ratio is None:
        return None
    cc = float(complexity)
    uncovered = 1.0 - coverage_ratio
    return (cc * cc * (uncovered ** 3)) + cc
