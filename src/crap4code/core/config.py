"""Configuration loading and sample config generation.

The config is intentionally small and repo-local. This keeps the tool easy to
audit in CI and easy for coding agents to reason about without hidden global
state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import tomllib

from crap4code.core.thresholds import DEFAULT_THRESHOLD


DEFAULT_CONFIG_NAME = ".crap4code.toml"


@dataclass(slots=True)
class ScanSettings:
    """Settings that apply to every language unless overridden by CLI flags."""

    default_paths: list[str] = field(default_factory=lambda: ["src"])
    threshold: float = DEFAULT_THRESHOLD
    format: str = "table"


@dataclass(slots=True)
class LanguageSettings:
    """Per-language runtime settings.

    The CLI resolves these settings before dispatching to a language adapter.
    They define where to scan and how, if at all, coverage should be refreshed.
    """

    enabled: bool = True
    paths: list[str] = field(default_factory=list)
    coverage_command: str | None = None
    coverage_report: str | None = None
    coverage_format: str | None = None
    stale_artifacts: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ProjectConfig:
    """Resolved configuration used by a scan run."""

    root: Path
    config_path: Path | None
    scan: ScanSettings
    languages: dict[str, LanguageSettings]


def _as_list(value: object, default: list[str]) -> list[str]:
    if value is None:
        return list(default)
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(value)
    raise ValueError(f"Expected a list of strings, got {value!r}")


def _language_settings(data: dict[str, object] | None) -> LanguageSettings:
    """Convert a TOML section into strongly typed language settings."""

    section = data or {}
    enabled = section.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ValueError("Language 'enabled' must be a boolean")

    coverage_command = section.get("coverage_command")
    coverage_report = section.get("coverage_report")
    coverage_format = section.get("coverage_format")

    for value, label in (
        (coverage_command, "coverage_command"),
        (coverage_report, "coverage_report"),
        (coverage_format, "coverage_format"),
    ):
        if value is not None and not isinstance(value, str):
            raise ValueError(f"Language '{label}' must be a string when present")

    return LanguageSettings(
        enabled=enabled,
        paths=_as_list(section.get("paths"), []),
        coverage_command=coverage_command,
        coverage_report=coverage_report,
        coverage_format=coverage_format,
        stale_artifacts=_as_list(section.get("stale_artifacts"), []),
    )


def load_project_config(root: Path, config_path: str | None, languages: list[str]) -> ProjectConfig:
    """Load repo-local config or fall back to deterministic defaults.

    Args:
        root: Working directory that scan operations should treat as repo root.
        config_path: Optional explicit config path from the CLI.
        languages: Canonical language keys that the current build supports.
    """

    resolved_path: Path | None = None
    if config_path:
        candidate = Path(config_path)
        resolved_path = candidate if candidate.is_absolute() else root / candidate
    else:
        candidate = root / DEFAULT_CONFIG_NAME
        if candidate.exists():
            resolved_path = candidate

    document: dict[str, object] = {}
    if resolved_path and resolved_path.exists():
        document = tomllib.loads(resolved_path.read_text(encoding="utf-8"))

    scan_section = document.get("scan", {})
    if scan_section and not isinstance(scan_section, dict):
        raise ValueError("[scan] must be a table")

    scan = ScanSettings(
        default_paths=_as_list(
            scan_section.get("default_paths") if isinstance(scan_section, dict) else None,
            ["src"],
        ),
        threshold=float(
            scan_section.get("threshold", DEFAULT_THRESHOLD)
            if isinstance(scan_section, dict)
            else DEFAULT_THRESHOLD
        ),
        format=str(scan_section.get("format", "table")) if isinstance(scan_section, dict) else "table",
    )

    language_settings: dict[str, LanguageSettings] = {}
    for language in languages:
        raw = document.get(language)
        if raw is not None and not isinstance(raw, dict):
            raise ValueError(f"[{language}] must be a table")
        language_settings[language] = _language_settings(raw)

    return ProjectConfig(
        root=root,
        config_path=resolved_path,
        scan=scan,
        languages=language_settings,
    )


def sample_config_text() -> str:
    """Return the canonical sample config used by ``crap4code init``."""

    return """# Repo-local configuration for crap4code.
# Keep commands and paths explicit so both humans and coding agents can verify
# exactly how coverage is generated for each language.

[scan]
default_paths = ["src"]
threshold = 8.0
format = "table"

[python]
enabled = true
paths = ["src", "tests"]
coverage_command = "python -m coverage run -m pytest && python -m coverage xml -o coverage.xml"
coverage_report = "coverage.xml"
coverage_format = "coverage.py-xml"
stale_artifacts = [".coverage", "coverage.xml"]

[javascript]
enabled = true
paths = ["src"]
coverage_report = "coverage/lcov.info"
coverage_format = "lcov"
stale_artifacts = ["coverage/lcov.info"]

[typescript]
enabled = true
paths = ["src"]
coverage_report = "coverage/lcov.info"
coverage_format = "lcov"
stale_artifacts = ["coverage/lcov.info"]

[rust]
enabled = true
paths = ["src"]
coverage_report = "coverage/lcov.info"
coverage_format = "lcov"
stale_artifacts = ["coverage/lcov.info"]
"""
