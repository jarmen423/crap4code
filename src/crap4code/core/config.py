"""Project config loading (repo-local .crap4code.toml) and sample generation.

Repo-local config is the source of truth for:
- which languages are enabled
- per-language source paths + optional coverage commands/reports
- global scan defaults (default_paths, format, threshold)
- stale artifact cleanup list

The sample produced by ``crap4code init`` is heavily commented so that a
human (or agent) can understand the execution model, cross-platform shell
realities, and the exact contract without reading source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tomllib

from crap4code.languages import get_language_registry


DEFAULT_CONFIG_NAME = ".crap4code.toml"


@dataclass(slots=True)
class ScanSettings:
    default_paths: list[str] = field(default_factory=lambda: ["src"])
    format: str = "table"
    threshold: float = 15.0


@dataclass(slots=True)
class LanguageSettings:
    enabled: bool = True
    paths: list[str] | None = None
    coverage_command: str | None = None
    coverage_report: str | None = None
    coverage_format: str | None = None
    stale_artifacts: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ProjectConfig:
    scan: ScanSettings
    languages: dict[str, LanguageSettings]
    config_path: Path | None = None


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def load_project_config(
    root: Path,
    config_path: str | None,
    languages: list[str] | None = None,
) -> ProjectConfig:
    """Load (or synthesize) the effective project config.

    If no config file is found or loadable, a default config is synthesized
    from the languages currently advertised by the registry. This keeps the
    tool usable out-of-the-box while still respecting a repo-local file as
    the single source of truth when present.
    """
    if languages is None:
        languages = list(get_language_registry().keys())

    candidate_paths: list[Path] = []
    if config_path:
        p = Path(config_path)
        candidate_paths.append(p if p.is_absolute() else root / p)
    else:
        candidate_paths.append(root / DEFAULT_CONFIG_NAME)

    raw: dict[str, Any] | None = None
    used_path: Path | None = None
    for cand in candidate_paths:
        if cand.exists():
            try:
                raw = _load_toml(cand)
                used_path = cand
                break
            except Exception:
                # Malformed config: treat as absent so we fall back to defaults
                # (the caller/CLI can decide to surface or fail later).
                pass

    scan = ScanSettings()
    lang_settings: dict[str, LanguageSettings] = {}

    if raw:
        scan_section = raw.get("scan", {}) or {}
        if "default_paths" in scan_section:
            scan.default_paths = list(scan_section["default_paths"])
        if "format" in scan_section:
            scan.format = str(scan_section["format"])
        if "threshold" in scan_section:
            scan.threshold = float(scan_section["threshold"])

        for lang in languages:
            section = raw.get(lang, {}) or {}
            ls = LanguageSettings(
                enabled=bool(section.get("enabled", True)),
                paths=list(section.get("paths", [])) if section.get("paths") is not None else None,
                coverage_command=section.get("coverage_command"),
                coverage_report=section.get("coverage_report"),
                coverage_format=section.get("coverage_format"),
                stale_artifacts=list(section.get("stale_artifacts", [])),
            )
            lang_settings[lang] = ls
    else:
        # No config (or unreadable): synthesize enabled entries for every
        # language the current registry can provide. This is the "just works"
        # path and is exactly what `crap4code init` materializes.
        for lang in languages:
            lang_settings[lang] = LanguageSettings()

    # Ensure every registry language has an entry (defensive).
    for lang in languages:
        lang_settings.setdefault(lang, LanguageSettings())

    return ProjectConfig(scan=scan, languages=lang_settings, config_path=used_path)


def sample_config_text() -> str:
    """Return the canonical sample config used by ``crap4code init``.

    The returned TOML is heavily commented to serve as both a working
    example and durable documentation. It teaches the coverage execution
    model, path expectations, and cross-platform considerations directly
    in the file that users will edit.

    Key teaching points embedded:
    - coverage_command (when present) is executed with shell=True.
    - On Windows this means cmd.exe (via ComSpec); on POSIX it is the
      platform default (/bin/sh or equivalent). Users are in their
      terminal shell (pwsh, bash, zsh, etc.) but the command string is
      interpreted by the platform's "default" shell for subprocess.
    - Prefer ``python -m`` forms so the active Python/venv is used.
    - ``&&`` chaining works under cmd.exe (and POSIX sh), which is why
      the Python sample uses it.
    - Other languages in the sample default to "use a pre-existing report"
      because many JS/TS/Rust projects generate coverage in their normal
      CI/test scripts rather than on every crap4code run.
    - Use --report-only during exploration or when you want to avoid
      mutating coverage state.
    """

    return """# Repo-local configuration for crap4code.
# Keep commands and paths explicit so both humans and coding agents can verify
# exactly how coverage is generated for each language.
#
# IMPORTANT: COVERAGE COMMAND SHELL MODEL (cross-platform reality)
# -----------------------------------------------------------
# If a language section has a "coverage_command", the EXACT string value
# is passed to subprocess.run(..., shell=True, cwd=root, env=os.environ.copy()).
#
# - On Windows (os.name == "nt"): this ALWAYS uses cmd.exe (the value of
#   the ComSpec environment variable), *regardless* of whether you launched
#   crap4code from PowerShell (pwsh), Git Bash, WSL, or a VS Code terminal.
# - On POSIX (Linux/macOS): this uses the platform default shell (typically
#   /bin/sh via the system's popen / subprocess implementation).
#
# This is the deliberate v1 design (keeps the contract simple: a single
# string the user can copy-paste and audit). It is NOT your interactive
# shell's syntax or quoting rules.
#
# PRACTICAL GUIDANCE:
# - Prefer "python -m ..." forms (as shown below). This uses the Python
#   that is running crap4code and respects the current venv / PATH.
# - "&&" chains work under cmd.exe (and sh). The sample below relies on this.
# - If you need PowerShell-specific features, wrap explicitly:
#     coverage_command = "pwsh -Command 'python -m coverage run ... ; python -m ...'"
# - For cmd.exe-specific needs you can be explicit: "cmd /c \\"...\\""
# - Quoting/escaping must be valid for cmd.exe (Windows) or sh (POSIX).
# - The env is a copy of whatever environment crap4code itself was launched
#   with. If you run crap4code from a desktop shortcut, scheduled task,
#   or CI step that has a different PATH/venv, coverage will see that env.
#
# SAFETY: Use \\"--report-only\\" (CLI flag) to read an existing report
# without executing any coverage_command. This is recommended while you
# are learning the tool or debugging config on Windows.
#
# See also:
# - WINDOWS_AND_CROSS_PLATFORM_PLAN.md (sections on S1/S2, Doc1/Doc2)
# - README.md "Windows and Cross-Platform Notes" section
# - The run_coverage_command implementation in core/coverage.py

[scan]
default_paths = ["src"]
format = "table"
threshold = 15.0

[python]
enabled = true
paths = ["src", "tests"]
# coverage_command is executed via the platform default shell (cmd.exe on
# Windows, /bin/sh-equivalent on POSIX). See the header comments above.
coverage_command = "python -m pytest --cov=src --cov-report=xml:coverage.xml --cov-report=term-missing -q && python -m coverage xml -o coverage.xml"
coverage_report = "coverage.xml"
coverage_format = "coverage.py-xml"
stale_artifacts = [".coverage", "coverage.xml", "htmlcov"]

[javascript]
enabled = true
paths = ["src"]
# Many JS/TS projects produce lcov as part of their normal test/CI script.
# Prefer running your project's own coverage step once, then invoke
# crap4code with --report-only to avoid duplicate work / side effects.
coverage_report = "coverage/lcov.info"
coverage_format = "lcov"
stale_artifacts = []

[typescript]
enabled = true
paths = ["src"]
coverage_report = "coverage/lcov.info"
coverage_format = "lcov"
stale_artifacts = []

[rust]
enabled = true
paths = ["src"]
# Rust projects commonly use cargo-tarpaulin or llvm-cov producing lcov.
coverage_report = "coverage/lcov.info"
coverage_format = "lcov"
stale_artifacts = []
"""


def _validate_language_section(name: str, section: dict[str, Any]) -> None:
    """Light validation used by tests (not part of the public loader contract)."""
    allowed = {"enabled", "paths", "coverage_command", "coverage_report", "coverage_format", "stale_artifacts"}
    unknown = set(section.keys()) - allowed
    if unknown:
        raise ValueError(f"Unknown keys in [{name}] section: {sorted(unknown)}")
