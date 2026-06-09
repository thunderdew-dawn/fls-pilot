# Mix Review Prompt

Use this when the user wants to review the current FL Studio mix.

## First Reads

- `fl://agent-briefing`
- `fl://status`
- `docs/agents/runtime-usage.md`
- `docs/agents/safety-contract.md`

## Workflow

1. Confirm bridge/session health.
2. Use read-only state first.
3. Run `fl_review_mix`.
4. If needed, run `fl_review_low_end_stereo`.
5. Report findings as:
   - critical mix risks
   - low-end/stereo issues
   - routing or gain-staging problems
   - safe next actions
6. Do not mutate FL Studio state unless the user explicitly approves a
   rollback-backed write.

## Stop Conditions

Stop and switch to read-only, dry-run, probe-only, or manual guidance when:

- bridge status is unclear;
- target project state is unclear;
- a suggested action would require unsupported API behavior;
- rollback/readback cannot be guaranteed;
- the user asks for rendering, save-as, plugin loading, or playlist clip edits.

## Response Shape

Return:

1. Session/bridge status.
2. Mix review summary.
3. Top risks in priority order.
4. Safe next actions.
5. Any unsupported or unverified behavior that must not be implied as complete.
