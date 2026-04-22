"""Deterministic risk classification and next-step recommendations."""

from __future__ import annotations

from crap4code.core.models import FunctionMetrics


def classify_risk(row: FunctionMetrics) -> str:
    """Bucket a function into a stable severity band."""

    if row.crap_score is not None:
        if row.crap_score > 30.0:
            return "high"
        if row.crap_score > 8.0:
            return "moderate"
        return "low"

    if row.complexity >= 12:
        return "high"
    if row.complexity >= 6:
        return "moderate"
    return "low"


def recommend_actions(row: FunctionMetrics) -> list[str]:
    """Return deterministic operator guidance for a single function."""

    actions: list[str] = []

    if row.coverage_state != "measured":
        actions.append(
            "Coverage is indeterminate. Configure or generate a coverage report before trusting CRAP."
        )

    if row.coverage_percent is not None and row.coverage_percent < 60.0:
        actions.append("Add or strengthen tests for this function before attempting a risky refactor.")

    if row.complexity >= 10:
        actions.append("Reduce branching by extracting decision-heavy paths into smaller helpers.")
    elif row.complexity >= 6:
        actions.append("Review nested conditionals and simplify control flow where behavior can stay unchanged.")

    if row.crap_score is not None and row.crap_score > 30.0:
        actions.append("Treat this as a top refactor candidate once test coverage is trustworthy.")
    elif row.crap_score is not None and row.crap_score > 8.0:
        actions.append("Schedule a targeted cleanup after the highest-risk functions are addressed.")

    return actions


def enrich_rows(rows: list[FunctionMetrics]) -> list[FunctionMetrics]:
    """Populate risk and recommendation fields in-place for report rendering."""

    for row in rows:
        row.risk_level = classify_risk(row)
        row.recommended_actions = recommend_actions(row)
    return rows
