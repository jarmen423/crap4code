"""Executable module for ``python -m crap4code.main``."""

from __future__ import annotations

from .cli import main as cli_main


def main() -> int:
    """Run the top-level CLI."""

    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
