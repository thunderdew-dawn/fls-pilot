# Write Safety Contract

Date: 2026-06-11

Agent/Author: Codex

Topic: Canonical write-safety contract for persistent FL Studio changes.

Affected File/API: `src/fls_pilot/operations.py`,
`src/fls_pilot/safety.py`, `scripts/audit_tool_safety.py`, FastMCP tool
annotations.

Context: GitHub issue #63 made the persistent-write contract a v3.0 P0 release
blocker. This branch is a breaking fork release, so legacy `write-safe`
vocabulary was removed from current public annotations and registry specs.

Observation: Persistent FL Studio project mutations are now classified as
`write-safe-required`. Operation-registry specs reject persistent-write classes
without explicit snapshot and restore builders. `safe_write` and
`safe_write_group` return before/after state plus `change_id`, rollback unit,
and undo guidance. The static audit reports `write-safe-required` and
`--fail-on-gaps` fails for both direct write gaps and unresolved
`needs-review` tools.

Tested Values: `read-only`, `transient`, `server-state`, `external-write`,
`write-safe-required`, direct unsafe `CMD_MIXER_SELECT_TRACK`, safe
`CMD_SET_TEMPO`, legacy `write-safe` registry class, grouped mixer mute writes.

Result: Implementation verified offline. The latest static audit reports
84 `write-safe-required`, 71 `read-only`, 5 `transient`, 4 `server-state`,
2 `external-write`, 0 `write-gap`, and 0 `needs-review` tool definitions.

Confidence Level: implementation_verified

Source/Method: Static audit, operation-registry tests, grouped-write tests,
and targeted audit regression tests.

Reproduction Steps:
1. Run `.venv/bin/python scripts/audit_tool_safety.py --fail-on-gaps`.
2. Run `.venv/bin/python scripts/audit_tool_safety.py --fail-on-missing-safety-docs --format json`.
3. Run `.venv/bin/python -m pytest tests/test_operation_registry.py tests/test_safe_write_group.py tests/test_tool_safety_audit.py`.

Known Pitfalls:
- Historical KB and verification-history entries may still mention
  `write-safe` as past evidence; current code and docs use
  `write-safe-required`.
- Piano Roll writes remain undo-backed and cannot provide structured note
  readback until a return channel is proven.
- Offline tests verify the contract shape; live FL Studio smoke testing still
  matters for API/build-specific behavior.

Open Questions: Repeat rollback-safe live smoke tests when FL Studio is
available for any changed persistent-write behavior.

Next Recommended Action: Keep future persistent-write tools registry-backed,
annotated `write-safe-required`, and covered by the safety audit.
