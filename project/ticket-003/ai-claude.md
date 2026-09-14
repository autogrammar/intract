---
participant-id: agent:claude
participant: claude
role: agent
ticket: ticket-003
---
# Participant: claude (AI agent)

## Understanding

The manifest predates the `decisionProtocol` field that `wellmanifest/dsl`
made mandatory for every LLM section. With `llm.mode=none` the only valid
value is `none`.

## Execution plan

1. Add `"decisionProtocol": "none"` to the `llm` object.
2. Run the `wellmanifest/dsl` gate and the repository governance gate.

## Actual changes

- `dsl-manifest.json`: added `llm.decisionProtocol=none`.

## Blockers

- None.
