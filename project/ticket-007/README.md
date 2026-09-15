# Ticket 007: Adopt git-derived ticket lifecycle

- **ID**: ticket-007
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Session execution authorization**: user requested sequential continuation
  ("kontynuuj") of the approved lifecycle-pilot work — autonomous adoption of
  the current `wellmanifest/new-project` pack within allowedPaths
- **Created**: 2026-09-15

## Goal and scope

Upgrade the adopted `wellmanifest/new-project` governance pack in this
repository from 0.14.0 to the current standard revision (0.20.32) and enable
target-owned Git-derived ticket activity via
`.governance/ticket-activity.override.json` (`missingPolicy: git-ancestry`), so
tickets whose delivery is already present on `main` stop occupying workstream
slots without rewriting historical README statuses.

## Acceptance criteria

- [x] AC-01: Adoption upgraded to `wellmanifest/new-project` 0.20.32.
- [x] AC-02: `.governance/ticket-activity.override.json` selects
      `git-ancestry` as `missingPolicy`.
- [x] AC-03: The adopted activity resolver classifies tickets delivered on
      `main` (ticket-001, ticket-003, ticket-006) as inactive via Git ancestry.
- [x] AC-04: `./project/governance-check.sh` passes.

## Participants

- Human participant: unresolved; no user-* file was created by this script.
- Agent participant: [ai-devin.md](ai-devin.md)
