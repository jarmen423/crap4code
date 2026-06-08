# crap4code: Windows & Cross-Platform Usability Plan

**Status**: Living document. All phases (0/1/2/3) complete as of 2026-06-08. Released as v0.4.0 (see release-checklist.md and CHANGELOG.md). Phase 3 (Polish, DX, CI) landed on merge/phase3-land-and-verify: Dev1 (pytest DX), Dev4 (CI enhancements + minimal verify), release checklist expansion. (See Phase 3 Merge section at end.)
**Phase 0 foundations complete**: `__main__.py` + `--version` implemented on 2026-06-08. (See C1/C2 + Phase 0 section for details.)
**Goal**: Make `crap4code` pleasant and reliable for daily use on **Windows** (primary pain) **and** POSIX systems (macOS/Linux), without sacrificing the project's core values (small, auditable, deterministic, no fake coverage data, parser-backed, repo-local config as source of truth).
