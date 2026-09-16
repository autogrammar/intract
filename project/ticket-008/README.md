# Ticket 008: refresh generated project analysis

- **ID**: ticket-008
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Session execution authorization**: user requested continuation
  ("kontynuuj") and explicitly approved committing both the dirty drift and the
  planfile sync workflow under a new ticket (2026-09-16)
- **Created**: 2026-09-16

## Goal and scope

The primary checkout accumulated uncommitted drift that the governance gate
reports as GOV-TICKET-001 (implementation paths changed without an active
ticket):

- Regenerated `project/` analysis artifacts (`calls.*`, `map.toon.yaml`,
  `flow.*`, `compact_flow.*`, `evolution/analysis/project.toon.yaml`,
  `context.md`, `prompt.txt`, `index.html`, `mermaid.export`,
  `planfile-tickets.yaml`, `README.md`).
- `.env.example`: `LLM_MODEL` default changed to
  `openrouter/qwen/qwen3.7-plus`.
- `.github/workflows/planfile-github-sync.yml`: untracked planfile -> GitHub
  issues sync, previously hidden by the blanket `.github/` ignore that
  ticket-007 narrowed.

None of these paths belonged to any workstream's `ownedPaths`, so this ticket
first extends the `governance` workstream to own generated `project/` outputs,
`.env.example` and the planfile sync workflow (precedent: ticket-002 added
`testql-scenarios/**` to `core`), then commits the drift.

## Acceptance criteria

- [x] AC-01: `governance` workstream `ownedPaths` covers the generated
  `project/` artifacts, `.env.example` and
  `.github/workflows/planfile-github-sync.yml`.
- [x] AC-02: all previously dirty paths are committed on
  `ticket/008-refresh-generated-analysis` inside `intent.json` `allowedPaths`.
- [ ] AC-03: `./project/governance-check.sh` passes on the merged head.

## Participants

- Human participant: unresolved; no user-* file was created by this script.
- Agent participant: [ai-devin.md](ai-devin.md)
