---
participant-id: agent:claude
participant: claude
role: agent
ticket: ticket-005
---
# Participant: claude (AI agent)

## Understanding

The `ignore` configuration was dead: parsed but never applied, so the project
self-check always scanned intentional violation fixtures.

## Actual changes

- `src/intract/project.py`: `is_ignored`, `ignore` parameter for `load_project_sources` and `validate_project`.
- `src/intract/cli.py`: `check` passes `config.ignore` in project mode.
- `tests/test_project_ignore.py`: four tests.

## Blockers

- `autogrammar/intract` is not in the Validator direct-PR registry (subactor/validator-agent#474).
