# Project Organizer Prompt

Use this when the user wants names, colors, routes, channel organization, or a
project cleanup plan.

## First Reads

- `fl://agent-briefing`
- `fl://status`
- `docs/agents/runtime-usage.md`
- `docs/concepts/safety-contract.md`

## Workflow

1. Confirm bridge/session health.
2. Read current channels, mixer, and playlist metadata through capped resources
   or domain tools.
3. Run `fl_plan_project_cleanup`.
4. Present the plan before mutation.
5. Apply only one approved cleanup step at a time with
   `fl_apply_project_cleanup_step`, and only when rollback/readback are clear.

## Stop Conditions

Stop when target selection, color mapping, routing destination, readback, or
rollback is unclear. Do not delete patterns/clips or edit playlist clip
placement.

## Response Shape

Return:

1. Current organization summary.
2. Proposed groups/routes/colors/names.
3. Safe step queue.
4. Rollback/readback notes for any write-safe step.
