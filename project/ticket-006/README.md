# Ticket 006: Skip agent-state dirs in project scans

- **ID**: ticket-006
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Session execution authorization**: user requested autonomous execution ("Wpisz intract + fix .worktrees", 2026-09-15)
- **Created**: 2026-09-15

## Goal and scope

`load_project_sources` recursively scans every source-like file and skips only
`.git`, `.venv`, `venv`, `__pycache__`, `node_modules`, `dist` and `build`. On a
checkout that carries ticket worktrees (`.worktrees/`, Wellmanifest Worktrees v5)
or agent runtime state (`.subactor/`), `intract check .` scans those nested trees
too, so local self-checks double-report findings from unrelated ticket branches
(`.worktrees/<ticket>/examples/**`) and can fail on contracts that do not belong
to the primary checkout.

This ticket adds `.worktrees` and `.subactor` to the shared `SKIP_DIRS` in
`src/intract/project.py` (covering `check`, `validate`, `coverage`, `graph` and
`duplicates`, which all consume `load_project_sources`) and to the parallel list
in `src/intract/scan_artifacts.py`, which already skips tool dirs such as
`.intract` and `.pyqual`.

The branch also records the closure of ticket-005 (delivered via merged PR #2,
`7cbf55e`), because the adopted allocator reads README status and ticket-005's
stale `IN_PROGRESS` reserved the `core` workstream.

## Acceptance criteria

- [x] AC-01: `load_project_sources` excludes files under `.worktrees/` and `.subactor/` at any depth (covered by `tests/test_project_ignore.py`).
- [ ] AC-02: full test suite passes.
- [ ] AC-03: `python -m intract check .` on a checkout containing `.worktrees/` and `.subactor/` reports no results from those trees.
- [ ] AC-04: `./project/governance-check.sh` passes on the published head.

## Participants

- Human participant: unresolved; no user-* file was created by this script.
- Agent participant: [ai-devin.md](ai-devin.md)
