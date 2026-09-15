---
participant-id: agent:devin
participant: devin
role: agent
ticket: ticket-006
---
# Participant: devin (AI agent)

## Understanding

Project scans (`check`, `validate`, `coverage`, `graph`, `duplicates`) share
`load_project_sources`, whose `SKIP_DIRS` did not include `.worktrees` or
`.subactor`. Local checkouts carrying ticket worktrees or agent state therefore
double-report contracts from nested trees; observed in a local SARIF run where
every finding appeared twice, once under `.worktrees/ticket-003--*/`.

## Execution plan

1. Record closure of merged ticket-005 to release the `core` workstream.
2. Add `.worktrees` and `.subactor` to `SKIP_DIRS` in `src/intract/project.py`
   and `src/intract/scan_artifacts.py`.
3. Cover the behavior in `tests/test_project_ignore.py`.

## Actual changes

- `project/ticket-005/README.md`: closed as delivered via merged PR #2.
- `src/intract/project.py`: `SKIP_DIRS` += `.worktrees`, `.subactor`.
- `src/intract/scan_artifacts.py`: `SKIP_DIRS` += `.worktrees`, `.subactor`.
- `tests/test_project_ignore.py`: `test_load_project_sources_skips_agent_state_dirs`.

## Blockers

- None.
