# Execution Scaffold

This repo uses wave-style execution artifacts so parallel work can be tracked by write scope instead of vague topics.

## Structure

- `ROADMAP.md`: wave overview
- `tasks.json`: task registry
- `handoffs/`: per-wave handoff files

## Rules

- lock contracts before parallel implementation
- split by disjoint write scope
- require handoffs before a wave is considered complete
