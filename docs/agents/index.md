# Agents

This section gives agents the smallest useful context for the task at hand.
Do not load every agent document by default. Choose the role first.

## Role Paths

### Use FLStudioPilot With FL Studio

For user-facing runtime workflows such as Mix Review, Routing Review, Project
Organizer, bridge/session checks, audio analysis, or MIDI export, read:

- [Runtime Usage](runtime-usage.md)
- [Safety Contract](../concepts/safety-model.md)

Use prompt files only for the active workflow:

- [Mix Review Prompt](prompts/mix-review.md)
- [Routing Review Prompt](prompts/routing-review.md)
- [Project Organizer Prompt](prompts/project-organizer.md)

### Develop Or Maintain The Repository

For code, tests, docs, controller files, scripts, workflows, packaging, or
Knowledgebase changes, read:

- [Development Guide](development.md)
- [Safety Contract](../concepts/safety-model.md)
- [Knowledgebase Protocol](knowledgebase-protocol.md)
- `docs/ENGINEERING_STANDARDS.md`
- `ROADMAP.md`

### GitHub Operations

For issues, PRs, roadmap planning, releases, CI, security, hotfixes, reverts,
API probes, backports, or review-only work, read:

- [GitHub Playbook](github-playbook.md)
- `docs/GITHUB_PLANNING.md`
- `ROADMAP.md`

Then use the focused prompt file for the exact operation.

## Context Rule

Agents should start narrow and only expand context when blocked. Runtime agents
should not read development or GitHub-operation documents unless the user task
requires repository maintenance.
