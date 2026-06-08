# Agent Operating Playbook

This playbook describes how humans, local coding agents, and review agents
should use the configured GitHub setup for day-to-day project work. GitHub
Issues, Milestones, and Project #7 are the planning source of truth; local
agent chats are execution surfaces, not durable planning storage.

## Shared Rules

- Start from the canonical project:
  <https://github.com/users/thunderdew-dawn/projects/7>
- Do not create duplicate roadmap projects. Project #6 is a legacy view; Project
  #7 is canonical.
- Every non-trivial change starts with a GitHub issue or updates an existing
  one.
- Keep `ROADMAP.md` and `docs/CHANGELOG.md` as snapshots. Use generated files in
  `docs/generated/` and the snapshot workflow for GitHub-backed views.
- Use small PRs. Each PR should close or materially advance one issue.
- Persistent FL Studio writes still require snapshot, readback, changelog, and
  rollback. If evidence is unclear, ship read-only, dry-run, probe-only, or
  manual guidance.

## Roles

- Human owner: decides product intent, accepts or rejects features, and resolves
  priority conflicts.
- High-reasoning planning agent: reads the issue, repo standards, and relevant
  code; produces implementation plans, dependency order, safety analysis, and
  agent slices.
- Low-reasoning implementation agent: executes one narrow, pre-approved slice
  at a time with minimal exploration.
- Review agent: checks diffs, tests, safety posture, and issue/PR alignment.

## Token-Saving Defaults

- Put durable context in GitHub issues, not in repeated chat prompts.
- Give agents one issue number and one slice at a time.
- Tell agents which files to inspect first.
- Ask planning agents for concise output: assumptions, dependencies, slices,
  commands, and stop conditions.
- Ask implementation agents to avoid broad repo scans after the planning agent
  has identified the relevant files.
- Use GitHub labels and Project fields to route work instead of restating
  priorities in every chat.

## Use Case 1: Human Wants A Local IDE Agent To Implement An Idea

### Human Actions

1. Open a Feature Request or Workflow Request issue.
2. Add the intended outcome, safety class, relevant FL API evidence, and known
   unsupported boundaries.
3. Assign labels and Project fields:
   - `priority:p0` through `priority:p3`
   - `area:*`
   - `type:*`
   - `read-only`, `write-safe-required`, `api-dependent`, or `dry-run-only`
4. Move the issue into the intended Project #7 lane.
5. Start the local IDE agent with the prompt below.

### Local Agent Prompt

```text
Work on GitHub issue #<number> in thunderdew-dawn/flstudio-mcp.

Rules:
- Read AGENTS.md, docs/ENGINEERING_STANDARDS.md, ROADMAP.md, and the issue.
- Treat GitHub issue/project state as the planning source of truth.
- Do not perform FL Studio writes.
- If the task needs live FL evidence, prepare a read-only or rollback-safe probe
  plan instead of guessing.
- Implement the smallest coherent slice that satisfies this issue.
- Update docs/API audit/verification history/Knowledgebase only when the change
  requires it.
- Run focused checks, then summarize changed files, verification, remaining
  risk, and next slice.
```

### Completion Criteria

- PR references the issue.
- Required local checks pass.
- GitHub CI and CodeQL pass.
- Project issue fields remain accurate after merge.

## Use Case 2: Agent Prepares The Next Roadmap Item For Multi-Agent Execution

The high-reasoning agent prepares work. Lower-reasoning agents execute only the
prepared slices in order.

### Human Actions

1. Pick the next item from Project #7, usually `Roadmap Lane = Now`, then
   `Priority = P0/P1`.
2. Assign or confirm the milestone and labels.
3. Ask a high-reasoning planning agent for a token-efficient implementation
   plan and slice queue.

### High-Reasoning Planning Prompt

```text
Prepare GitHub issue #<number> for multi-agent implementation.

Output must be token-efficient and execution-oriented:
1. Scope: one paragraph.
2. Required first reads: exact files only.
3. Dependency order: numbered.
4. Safety/API evidence requirements.
5. Slice queue:
   - slice id
   - agent class: low-reasoning or high-reasoning
   - objective
   - files to inspect
   - files likely to edit
   - commands/checks
   - stop conditions
6. PR strategy: one PR or multiple PRs.
7. GitHub field updates needed.

Do not implement. Do not broaden scope beyond the issue.
```

### Slice Issue Comment Template

Post this as a GitHub issue comment so agents can self-serve:

```text
Slice queue for issue #<number>

Rules for agents:
- Take the first unclaimed slice.
- Comment "Claiming slice <id>" before work.
- Work only on that slice.
- Stop if safety, API evidence, rollback, readback, or target selection is
  unclear.
- Open a PR titled "<slice id>: <short objective>".
- Link the PR back to this issue.

<paste slice queue>
```

### Low-Reasoning Agent Prompt

```text
Claim and execute the first unclaimed low-reasoning slice in issue #<number>.

Constraints:
- Use only the slice instructions and listed files unless blocked.
- Do not redesign the feature.
- Do not change FL Studio state.
- Keep the diff narrow.
- Run the slice checks.
- Open or prepare one PR and report exact verification.
```

### High-Reasoning Agent Prompt For Complex Slices

```text
Claim and execute the first unclaimed high-reasoning slice in issue #<number>.

Focus:
- Resolve architecture, safety, API-evidence, or cross-module questions.
- Preserve rollback-first behavior.
- Produce a narrow implementation or a documented block with evidence.
- Update the issue with the next executable slice if the plan changes.
```

### Completion Criteria

- All slices are closed, merged, or explicitly blocked in the issue.
- Project #7 lane/status reflects reality.
- Snapshot docs are updated through the GitHub snapshot workflow when needed.

## Use Case 3: User Reports A Bug And An Agent Fixes It

### Human/User Actions

1. Open a Bug Report issue.
2. Include FL Studio build, controller marker, OS, Python version, bridge type,
   ping/status evidence, repro steps, and logs.
3. Set labels such as `bug`, `area:*`, `read-only`, `write-safe-required`, or
   `api-dependent`.

### Triage Prompt

```text
Triage GitHub bug issue #<number>.

Tasks:
- Classify as reproducible, needs-info, duplicate, expected API limitation, or
  real defect.
- Identify the smallest affected surface.
- List exact files/tests to inspect.
- State whether live FL verification is required.
- If live verification is required, propose read-only first, then rollback-safe
  probe steps.
- Do not implement yet unless the fix is obvious and isolated.
```

### Fix Agent Prompt

```text
Fix GitHub bug issue #<number>.

Rules:
- Read AGENTS.md, docs/ENGINEERING_STANDARDS.md, ROADMAP.md, and the issue.
- Reproduce or explain why reproduction is impossible.
- Keep the fix minimal and scoped to the bug.
- Do not weaken safety or rollback behavior.
- Add or update focused tests if the behavior is testable offline.
- Update Knowledgebase/API audit/known pitfalls if the bug exposes missing
  reusable knowledge.
- Run focused checks and report verification.
```

### Completion Criteria

- Bug cause is documented in the PR.
- Fix is covered by focused tests or a justified verification path.
- Issue is closed only after the PR is merged or the report is rejected with
  evidence.

## Use Case 4: GitHub Security Features Report A Problem

Security reports may come from CodeQL, Dependabot, secret scanning, or private
vulnerability reporting.

### Human Actions

1. Do not paste secrets or private vulnerability details into public issues.
2. For Dependabot or CodeQL alerts, use the generated alert/PR as source data.
3. For private vulnerability reports, keep discussion inside GitHub Security
   Advisories or private maintainer channels.
4. Decide whether the fix is urgent enough for an immediate branch or can wait
   for the normal milestone.

### Security Agent Prompt

```text
Review the GitHub security alert/PR for thunderdew-dawn/flstudio-mcp.

Rules:
- Do not expose secrets, private paths, or vulnerability details in public text.
- Identify alert source: CodeQL, Dependabot, secret scanning, or private report.
- Confirm affected files and package versions.
- Propose the smallest safe remediation.
- Check whether the fix changes FL Studio write behavior, file IO, generated
  artifacts, or GitHub Actions permissions.
- If implementation is approved, make one narrow PR and run focused checks.
```

### Completion Criteria

- Alert is closed, dismissed with documented reason, or linked to a merged fix.
- CI/CodeQL are green.
- Any dependency update has a Release Dry Run if packaging could be affected.

## Use Case 5: User Requests A Feature, Human Approves, Agents Plan And Execute

### Human Decision Flow

1. User opens Feature Request or Workflow Request.
2. Human owner decides:
   - accepted
   - needs more evidence
   - duplicate
   - rejected/not planned
3. If accepted, set labels, milestone, Project lane, priority, and safety class.
4. If rejected, close as not planned with a clear safety/product reason.
5. If evidence is missing, create or link an API Probe issue.

### Approval Comment Template

```text
Decision: accepted

Scope:
- <what is included>

Out of scope:
- <what must not be implemented>

Safety class:
- <read-only | transient | write-safe required | api-dependent | dry-run-only>

Planning fields:
- Priority: <P0/P1/P2/P3>
- Milestone: <milestone>
- Roadmap Lane: <Now/Next/Later>
- Target iteration/quarter, if relevant: <value or none>

Next step:
- High-reasoning planning agent should produce an implementation plan and slice
  queue. No implementation before plan approval.
```

### Planning Agent Prompt

```text
Plan implementation for accepted feature issue #<number>.

Output:
- User value and acceptance criteria.
- API evidence and safety class.
- Milestone/iteration/quarter recommendation.
- Dependencies and rollout order.
- Slice queue split into low-reasoning and high-reasoning work.
- Testing and verification plan.
- Docs/Knowledgebase/API audit updates.
- PR and release strategy.

Keep output concise. Do not implement.
```

### Execution Agent Prompt

```text
Execute approved slice <id> for feature issue #<number>.

Rules:
- Follow the approved slice plan.
- Keep the diff narrow.
- Do not expand scope.
- Preserve FL safety contract.
- Update issue/PR with exact verification and remaining risk.
```

### Completion Criteria

- Feature matches the approved scope.
- Project fields and milestone are current.
- Docs and Knowledgebase are updated when behavior or reusable evidence changed.
- CI, CodeQL, safety audits, and focused tests pass.

## Recommended GitHub Commands

```bash
gh issue view <number> --repo thunderdew-dawn/flstudio-mcp
gh project item-list 7 --owner thunderdew-dawn --limit 100 --format json
python3 scripts/check_github_project_fingerprint.py
gh run list --repo thunderdew-dawn/flstudio-mcp --limit 10
gh workflow run project_fingerprint.yml --repo thunderdew-dawn/flstudio-mcp --ref main
gh workflow run roadmap_changelog_sync.yml --repo thunderdew-dawn/flstudio-mcp --ref main -f write_canonical=false
gh workflow run release_dry_run.yml --repo thunderdew-dawn/flstudio-mcp --ref main
```

## Stop Conditions

Agents must stop and ask for human decision when:

- the requested behavior conflicts with `AGENTS.md` or
  `docs/ENGINEERING_STANDARDS.md`;
- FL Studio API support, target selection, rollback, readback, or value ranges
  are unclear;
- implementation would require prohibited automation;
- a low-reasoning slice discovers architectural ambiguity;
- a security alert involves private vulnerability details or secrets;
- Project #7 fingerprint fails and the issue/project state cannot be explained.
