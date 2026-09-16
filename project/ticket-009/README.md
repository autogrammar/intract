# Ticket 009: adopt wellmanifest/dsl shared command schemas

- **ID**: ticket-009
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Session execution authorization**: user requested continuation
  ("kontynuuj") of the declared TODO backlog (2026-09-16)
- **Created**: 2026-09-16

## Goal and scope

`TODO.md` carries one open item: "Adopt shared command schemas from
`wellmanifest/dsl` where applicable." The standard publishes five closed JSON
Schemas under `schemas/commands/` (`GENERATE`, `PATCH`, `QUERY`, `RESOLVE`,
`VALIDATE`). Applicability for intract's command surface:

- **VALIDATE** — `intract validate <path>` matches `{verb, path}` exactly.
- **QUERY** — `coverage`, `duplicates`, `graph`, `scan` are read-only target
  queries with an optional format, matching `{verb, target, format?}`.
- **GENERATE** — not adopted: `propose`/`engine suggest` take a file or
  structured input, not the required `text` field.
- **PATCH** — not applicable: intract applies no patches (pfix retired,
  ticket-004).
- **RESOLVE** — not applicable: no natural-language resolution
  (`llm.mode: none`).

Adoption is declarative: `standardsLock` re-pins `wellmanifest/dsl` to
`5f40ad5d228d6301bdbf4bb78e1646ebd3c2b95b` (the origin/main revision that
contains `schemas/commands/`), refreshes the manifest-schema and spec digests,
and binds the `dsl-commands/validate` and `dsl-commands/query` contracts.
`docs/commands.md` gains the CLI-to-shared-schema mapping and is added to
`ownedPaths`/`artifacts` as a digest-bound documentation artifact. Manifest
version bumps 0.5.14 -> 0.6.0 (additive per declared lifecycle policy).
`vocabularyKind` stays `documents`: the intract language itself has no command
sentences; the shared schemas describe the tool surface only.

## Acceptance criteria

- [x] AC-01: `standardsLock` pins `wellmanifest/dsl@5f40ad5` with correct
  sha256 digests for `dsl-manifest/v1`, `DSL_STANDARD.md`,
  `dsl-commands/validate` and `dsl-commands/query`.
- [x] AC-02: `docs/commands.md` documents the VALIDATE/QUERY mapping and the
  non-adopted verbs with reasons.
- [x] AC-03: `dsl_check.py validate` and `standards` pass on the head.
- [ ] AC-04: `./project/governance-check.sh` passes on the merged head.

## Participants

- Human participant: unresolved; no user-* file was created by this script.
- Agent participant: [ai-devin.md](ai-devin.md)
