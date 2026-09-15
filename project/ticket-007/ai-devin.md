---
participant-id: agent:devin
participant: devin
role: agent
ticket: ticket-007
---
# Participant: devin (AI agent)

## Understanding

The fleet governance pack here (0.14.0) predates Git-derived ticket lifecycle.
Stale `IN_PROGRESS` projections in `project/ticket-*/README.md` exhaust
workstream slots even after their changes reached `main`. The 0.20.32 pack plus
a target-owned activity override resolves ticket activity from Git ancestry and
the terminal-receipt registry instead of README state alone.

## Execution plan

1. Repair `.gitignore` so managed `.github/` targets are trackable.
2. Adopt `wellmanifest/new-project` 0.20.32 (`goal governance adopt --upgrade`).
3. Add `.governance/ticket-activity.override.json` (`git-ancestry`).
4. Repair `.git/new-project/terminal-receipts.json` to the
   `terminal-receipt-registry/v1` schema (receipt for ticket-004 bound to
   `c5b85ed`).
5. Verify resolver classifies delivered tickets inactive and run governance
   check.

## Actual changes

- `.gitignore`: narrowed blanket `.github/` ignore so managed files are
  trackable; adoption appended canonical `.worktrees`/`.subactor` entries.
- Managed pack files upgraded to 0.20.32 (`.governance/**`, `project/` scripts,
  `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, agent-host files).
- `.governance/ticket-activity.override.json`: `missingPolicy: git-ancestry`.
- `project/ticket-001/README.md`: closed as DONE with delivery evidence (the
  original adoption landed on `main`; stale projection blocked the governance
  workstream).

## Blockers

- None.
