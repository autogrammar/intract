# Ticket 005: Honor configured ignore patterns in project checks

- **ID**: ticket-005
- **Owner**: unresolved:human
- **Status**: DONE
- **Workflow state**: DONE
- **Delivered**: merged via PR #2 (`7cbf55e`); implementation `c954d07`, plan `ffa7d24`; `main` self-check green since 2026-09-14T20:01Z
- **Session execution authorization**: user requested autonomous execution of publication-blocker fixes (2026-09-14)
- **Created**: 2026-09-14

## Goal and scope

`IntractConfig.ignore` is parsed from `[tool.intract]`, `.intract.yaml` or
`intract.config.yaml`, but no project scan used it. The `intract` CI job runs
`python -m intract check . --format sarif` on the whole repository and fails on
the intentional negative fixtures (`examples/markdown-generator/violation`,
`examples/web-app/iterations/v2-violation`,
`examples/integration_tests/02_typescript_violation_planfile`), so the job is
red on `main` and cannot be a required publication check.

This ticket makes `load_project_sources` and `validate_project` accept ignore
patterns and passes the configured list from `intract check` in project mode.
Declaring the repository's own ignore list in `pyproject.toml` belongs to the
`integration` workstream and follows separately.

The branch also records the closure of ticket-002 (delivered as `7f23edc`),
because the adopted allocator reads README status.

## Acceptance criteria

- [x] AC-01: `tests/test_project_ignore.py` covers glob, directory and `/**` patterns, source loading, project validation and the CLI reading `[tool.intract] ignore`.
- [x] AC-02: full suite passes (92 tests).
- [x] AC-03: with the planned `[tool.intract] ignore` list, `python -m intract check .` reports `Violations: 0` and exits 0.
- [ ] AC-04: `./project/governance-check.sh` passes on the published head.

## Participants

- Human participant: unresolved; no user-* file was created by this script.
- Agent participant: [ai-claude.md](ai-claude.md)
