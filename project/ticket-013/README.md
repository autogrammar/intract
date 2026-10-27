# Ticket 013: Publish versioned intent scan artifacts for search with precise source bindings (#10)

- **ID**: ticket-013
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-10-27

## Goal and scope

Implement versioned intent scan artifacts (`intract.scan/v1`) for `semcod/search` and `autogrammar/todo2code` consumption (Issue #10 / `INTR-007` / `PLF-20321`), including explicit intent/domain/input/output/effect/forbid/preconditions, stable symbol IDs/hashes/spans, validated source bindings (`verified`, `stale`, `missing`, `unknown`), declared vs inferred distinction (`basis`), coverage exposure, golden fixtures, and fail-closed enforcement on forbidden effects.

## Acceptance criteria

- [x] AC-01: Emit versioned scan envelope (`intract.scan/v1`) with coverage, summary, and enriched rows containing explicit `intent`, `domain`, `inputs`, `outputs`, `effects`, `forbidden`, and `preconditions`.
- [x] AC-02: Compute stable `symbol_id`, `contract_hash`, `source_hash`, and line `span`, validating source binding and keeping `declared` vs `inferred` and `verified`/`stale`/`missing`/`unknown` evidence distinct.
- [x] AC-03: Provide golden fixtures consumed by Search and fail closed on forbidden effect violations (`--fail-on-forbidden-effects` / `fail_on_forbidden_effects=True`).

## Authorization

SESSION_EXECUTION_AUTHORIZATION: the owner requested autonomous execution, testing, and resolution of blocking backlog tasks (`PLF-20321` / `INTR-007`). This authorizes implementation and invoking the declared protected delivery route; it is not trusted merge approval.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
