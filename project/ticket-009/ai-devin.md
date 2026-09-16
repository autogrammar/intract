participant-id: agent:devin
participant: devin
role: agent
ticket: ticket-009
---
# Participant: devin (AI agent)

## Understanding

The TODO backlog item asks to adopt `wellmanifest/dsl` shared command schemas
where applicable. Sibling DSLs (vql, testql, doql, nlp2dsl) vendor the schemas
into `dsl2*` packages because their grammar sentences are commands. Intract is
a `documents`-kind DSL — its sentences are contracts — so the applicable
surface is the CLI/MCP command layer, and the correct binding mechanism is the
manifest `standardsLock`, not vendored files (no `schemas/**` workstream
ownership exists; declaring the pin keeps the change inside the integration
workstream).

## Execution plan

1. Evaluate each shared schema against the CLI surface.
2. Re-pin `standardsLock` to `wellmanifest/dsl@5f40ad5` (revision containing
   `schemas/commands/`), refresh digests, add `dsl-commands/validate` and
   `dsl-commands/query` contracts.
3. Document the mapping in `docs/commands.md`; bind it in
   `ownedPaths`/`artifacts`; bump manifest version to 0.6.0.
4. Check off `TODO.md`; run `dsl_check validate`/`standards` and
   `governance-check`.

## Actual changes

- `dsl-manifest.json`: version 0.6.0; `ownedPaths`/`artifacts` +=
  `docs/commands.md` (sha256 bound); `standardsLock` re-pinned to 5f40ad5 with
  four contract digests (manifest schema, spec, validate, query).
- `docs/commands.md`: "Wspólne schematy komend" section with the
  VALIDATE/QUERY mapping table and non-adoption reasons for
  GENERATE/PATCH/RESOLVE.
- `TODO.md`: item marked done.

SESSION_EXECUTION_AUTHORIZATION: "kontynuuj" — continue the declared TODO
backlog autonomously.

## Blockers

- None.
