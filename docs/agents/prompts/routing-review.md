# Routing Review Prompt

Use this when the user wants to review routing, mixer organization, bus setup,
or send/return structure in the current FL Studio project.

## First Reads

- `fl://agent-briefing`
- `fl://status`
- `docs/agents/runtime-usage.md`
- `docs/concepts/safety-contract.md`

## Workflow

1. Confirm bridge/session health.
2. Use read-only state first.
3. Run `fl_review_routing`.
4. If cleanup is requested, run `fl_plan_routing_cleanup` before any mutation.
5. Treat cleanup as a plan unless the user explicitly approves a rollback-backed
   write step.

## Stop Conditions

Stop when target selection, track indexing, rollback, readback, or API support
is unclear. Do not guess routing targets or silently rewrite mixer structure.

## Response Shape

Return:

1. Current routing risks.
2. Bus/send/grouping issues.
3. Proposed cleanup steps.
4. Which steps are read-only, dry-run, or write-safe-required.
