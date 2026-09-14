# Ticket 003: Declare DSL manifest decision protocol for wellmanifest/dsl gate

- **ID**: ticket-003
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: VALIDATION
- **Session execution authorization**: user requested an audit of autogrammar projects against wellmanifest guidelines and implementation of the selected improvements (2026-09-13)
- **Created**: 2026-09-13

## Goal and scope

`dsl-manifest.json` fails the current `wellmanifest/dsl` conformance gate
(`src/dsl_check.py validate`, revision `5f40ad5d228d6301bdbf4bb78e1646ebd3c2b95b`):

```text
DSL-MANIFEST-001 ERROR: llm misses fields: decisionProtocol
DSL-LLM-001 ERROR: llm.decisionProtocol is invalid
```

The standard requires `llm.decisionProtocol=none` when `llm.mode=none`.
This ticket declares that value. It changes no DSL syntax, semantics, runtime
code or LLM authority, so the manifest version stays unchanged.

## Scope extension (2026-09-14)

The `integration` workstream owns `pyproject.toml`. The repository's
`[tool.intract] ignore` list is added here so the `intract` job can become a
required publication check (user decision 2026-09-14, subactor/validator-agent#474).
It depends on ticket-005 (autogrammar/intract#2) for the ignore implementation.
This branch also records the closure of ticket-004, delivered as `c5b85ed`,
whose stale `IN_PROGRESS` status reserved the same workstream and path.

## Acceptance criteria

- [x] AC-01: `llm.decisionProtocol` is `none`, matching `llm.mode=none`.
- [x] AC-02: `python3 src/dsl_check.py validate --root <checkout> <checkout>/dsl-manifest.json`
  from `wellmanifest/dsl@5f40ad5` reports `DSL-PASS: passed (0 errors)`.
- [x] AC-03: `pyproject.toml` declares `[tool.intract] ignore` for the intentional negative fixtures; with ticket-005 (#2) the repository self-check reports `Violations: 0`.
- [ ] AC-04: `./project/governance-check.sh` passes on the published head.

## Participants

- Human participant: unresolved; no user-* file was created by this script.
- Agent participant: [ai-claude.md](ai-claude.md)
