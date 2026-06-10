# AGENTS.md

This is the repository entry point for AI-assisted work in `thunderdew-dawn/fls-pilot`.
Choose the smallest role-specific context path before reading more files.

## Choose Your Role First

### A) Use FLStudioPilot With FL Studio

Use this path when the task is to run or guide workflows such as Mix Review,
Routing Review, Project Organizer, audio analysis, MIDI export, bridge/session
health checks, or other user-facing MCP workflows.

Read:

- `docs/agents/runtime-usage.md`
- `docs/agents/safety-contract.md`

Optional, only when needed:

- `docs/agents/knowledgebase-protocol.md` when the task involves FL Studio API
  behavior, mixer/plugin parameters, MIDI, automation, REC events, ranges,
  mappings, or reusable findings.
- `docs/agents/prompts/mix-review.md` when the user asks for a mix review.
- `docs/agents/prompts/routing-review.md` when the user asks for routing review.
- `docs/agents/prompts/project-organizer.md` when the user asks for project
  cleanup or organization.

Do not read the GitHub playbook unless the task involves issues, PRs, releases,
roadmap state, CI, security, or repository maintenance.

### B) Develop Or Maintain The Repository

Use this path when changing code, tests, docs, scripts, controller files,
Knowledgebase files, workflows, packaging, or project behavior.

Read:

- `docs/agents/development.md`
- `docs/concepts/safety-contract.md`
- `docs/agents/knowledgebase-protocol.md`
- `docs/engineering/standards.md`
- `docs/project/ROADMAP.github.md`

For live FL Studio verification, also follow:

- `docs/agents/runtime-usage.md`

### C) Work On GitHub Planning, PRs, Releases, Security, Or Roadmap

Use this path when triaging issues, planning slices, reviewing PRs, preparing
releases, handling CI failures, Dependabot, CodeQL, hotfixes, reverts, API
probes, documentation-only changes, or backports.

Read:

- `docs/agents/github-playbook.md`
- `docs/project/ROADMAP.github.md`

Use the focused prompt files in `docs/agents/prompts/` when applicable.

## Universal Hard Rules

- Prefer high-level MCP tools over raw FL API calls.
- Check the Knowledgebase before FL state, mixer/plugin parameters, automation,
  REC events, or MIDI work.
- Do not guess FL Studio API ranges, normalized values, dB/Hz mappings, REC
  event IDs, track indices, plugin parameter indices, or valid ranges.
- No persistent FL write without scoped snapshot, smallest practical write,
  readback verification where supported, changelog entry, and rollback path.
- If API support, bridge status, target selection, readback, rollback, or value
  evidence is unclear, switch to read-only, dry-run, probe-only, or manual
  guidance.
- Do not ship plugin loading/insertion, playlist clip editing, pattern or clip
  deletion, project open/new/save-as/render automation, raw escape hatches,
  broad UI automation, unsafe automation recording, or full-FLP restore claims
  as user-facing tools.
- Preserve all user and uncommitted changes. Never revert unrelated work.
- Use English for commits, code comments, docstrings, and repository
  documentation.
