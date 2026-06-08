# GitHub Planning

GitHub Issues and Milestones are the planning source of truth for open roadmap
work after the 2026-06-08 migration. Markdown roadmap and changelog files remain
readable snapshots backed by the configured GitHub-to-Markdown workflow.

## Current Structure

- Canonical project: [FL Studio MCP Core Roadmap](https://github.com/users/thunderdew-dawn/projects/7).
- Fingerprint: [`issue_project_fingerprint.md`](issue_project_fingerprint.md)
  records the expected project IDs, fields, required release-train items, and
  semantic invariant checks.
- Label `github-source-of-truth` marks durable planning issues.
- Priority labels: `priority:p0`, `priority:p1`, `priority:p2`, `priority:p3`.
- Area labels: `area:safety`, `area:workflow`, `area:docs`, `area:github`,
  `area:kb`, `area:ux`, `area:api`, plus fine-grained labels such as
  `area:rename`, `area:security`, `area:ci`, and `area:installer` when the
  issue needs more precise routing.
- Type labels: `type:roadmap`, `type:workflow`, `type:doctor`, `type:report`,
  `type:github-sync`, `type:rename`, `type:security`, `type:feature`,
  `type:fix`, and `type:maintenance`.
- Safety labels: `read-only`, `write-safe-required`, `api-dependent`,
  `api-limited`, `dry-run-only`, and `transient`.
- Release labels: `release-blocker`, `breaking-change`, `release:skip`.
- Legacy labels such as `P0`, `P1`, `bug`, `enhancement`, `documentation`,
  `safety`, `ux`, `workflow`, and `rollback` are not canonical for new work.
  Normalize issues to structured labels when they are touched.

## Project Fields

Project #7 has these roadmap fields populated for GitHub source-of-truth issues
and the 3.0 release-train issues:

- `Roadmap Lane`: `Now`, `Next`, `Later`, `Blocked`, `Done`.
- `Priority`: `P0`, `P1`, `P2`, `P3`.
- `Area`: `Safety`, `Workflow`, `Docs`, `GitHub`, `KB`, `UX`, `API`.
- `Type`: `Roadmap`, `Workflow`, `Doctor`, `Report`, `GitHub Sync`.
- `Safety`: `Read-only`, `Write-safe required`, `API-dependent`,
  `Mixed/manual`.

Fine-grained labels intentionally map into these coarser Project field values.
For example, `area:rename` maps to `GitHub`, `area:security` maps to `Safety`,
and `type:rename` maps to `Roadmap`.

## Milestones

Maintenance/backlog milestones:

- `GitHub Roadmap Migration`
- `Setup Reliability & Reporting`
- `API-backed Quick Wins`
- `Product Workflows`
- `Experimental/API-dependent`
- `Rejected / Not Planned`

3.0 release-train milestones:

- `M0 Naming & Governance Freeze`
- `M1 Security Baseline & Repo Hardening`
- `M2 Stability Core: Rollback, Evidence, API Boundaries`
- `M3 Setup Reliability & First-Run Experience`
- `M4 User Value Pack 1: Mix Review / Preflight / Organizer`
- `M5 Release Readiness / 3.0`
- `M6 Jam-to-Project Alpha / 3.1`

The old `v2.1 Jam-to-Project` milestone is superseded by the 3.1 alpha plan.
Jam-to-Project should not ship before the breaking `fls-pilot` rename, safety
core, setup doctor, and first user-value beta are complete.

## Migration Notes

- Open items from `ROADMAP.md` were migrated to GitHub issues #3 through #34.
- Extension review follow-up issues were added as #35 through #48. Issues #42
  through #48 are closed as `not planned` and document explicit product/safety
  boundaries.
- The 2026-06-08 release-train cleanup added M0-M5 issues for the breaking
  `fls-pilot` rename, security baseline, write-safety contract, setup doctor,
  user-value beta, and 3.0 release readiness.
- Project #7 is configured with all migrated issues, release-train issues, and
  the project fields listed above. The fingerprint check is semantic: it
  verifies source-of-truth issue inclusion, required release-train items,
  populated project fields, release-blocker milestone/P0 state, and Done/Done
  state for closed issues.
- GitHub-to-Markdown snapshot generation is implemented by `Sync GitHub
  Markdown Snapshots`. It always renders `docs/generated/` and can refresh
  `ROADMAP.md` and `docs/CHANGELOG.md` through the manual `write_canonical`
  input.
- GitHub user Projects require an auth token with project scopes. Project
  Automation intentionally no-ops when `PROJECTS_TOKEN` is absent because
  `GITHUB_TOKEN` cannot edit the maintainer's user Project #7.
- Release sequencing is tracked in GitHub Project #7 and release planning issue
  #66.

## Operations Workflows

- `Project Automation`: adds issues to Project #7 and mirrors labels into
  project fields. It requires `PROJECTS_TOKEN`; without it the workflow exits
  successfully as a no-op to avoid noisy false failures.
- `Project Fingerprint`: verifies Project #7 source-of-truth and release-train
  invariants against [`issue_project_fingerprint.md`](issue_project_fingerprint.md).
- `Sync GitHub Markdown Snapshots`: renders GitHub-backed roadmap/changelog
  snapshots into `docs/generated/`; a manual input can also refresh
  `ROADMAP.md` and `docs/CHANGELOG.md`.
- `CodeQL`: runs weekly and on pushes/PRs for Python security analysis.
- `Release Dry Run`: builds and validates distributions without publishing a
  release.
- `Release`: validates release tag/version alignment, builds distributions, and
  marks `alpha`, `beta`, and `rc` tags as GitHub prereleases.

## Agent Operating Playbook

Use [`AGENT_OPERATING_PLAYBOOK.md`](AGENT_OPERATING_PLAYBOOK.md) for concrete
human/agent workflows: local IDE implementation, roadmap slice planning,
bug-fix execution, security alert handling, and accepted feature planning.
