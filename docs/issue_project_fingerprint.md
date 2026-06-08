# Issue Project Fingerprint

Last verified: 2026-06-08.

This file records the canonical GitHub issue/project setup for roadmap
planning. It is intentionally compact so agents can verify the GitHub state
without recreating duplicate projects or re-inferring the migration layout.

## Canonical Project

- Owner: `thunderdew-dawn`
- Repository: `thunderdew-dawn/flstudio-mcp`
- Project: `FL Studio MCP Core Roadmap`
- Project number: `7`
- Project ID: `PVT_kwHOC9dBM84BZ7oT`
- URL: <https://github.com/users/thunderdew-dawn/projects/7>
- Visibility: private

## Secondary Project

- Project: `FL Studio MCP Roadmap`
- Project number: `6`
- Project ID: `PVT_kwHOC9dBM84BZ7nZ`
- URL: <https://github.com/users/thunderdew-dawn/projects/6>
- Status: secondary/legacy roadmap view
- Rule: do not create a third duplicate roadmap project

## Canonical Fields

| Field | ID | Expected options |
|---|---|---|
| `Status` | `PVTSSF_lAHOC9dBM84BZ7oTzhU2zz8` | `Todo`, `Next`, `In progress`, `Done` |
| `Roadmap Lane` | `PVTSSF_lAHOC9dBM84BZ7oTzhU6yKQ` | `Now`, `Next`, `Later`, `Blocked`, `Done` |
| `Priority` | `PVTSSF_lAHOC9dBM84BZ7oTzhU6yKU` | `P0`, `P1`, `P2`, `P3` |
| `Area` | `PVTSSF_lAHOC9dBM84BZ7oTzhU6yKY` | `Safety`, `Workflow`, `Docs`, `GitHub`, `KB`, `UX`, `API` |
| `Type` | `PVTSSF_lAHOC9dBM84BZ7oTzhU6yME` | `Roadmap`, `Workflow`, `Doctor`, `Report`, `GitHub Sync` |
| `Safety` | `PVTSSF_lAHOC9dBM84BZ7oTzhU6yM8` | `Read-only`, `Write-safe required`, `API-dependent`, `Mixed/manual` |

Fine-grained labels map into these coarse fields. Examples:

- `area:rename` -> `Area = GitHub`
- `area:security` -> `Area = Safety`
- `area:ci` -> `Area = GitHub`
- `area:installer` -> `Area = UX` unless `area:safety` is also present
- `type:rename`, `type:security`, and `type:maintenance` -> `Type = Roadmap`
- both `read-only` and `write-safe-required` -> `Safety = Mixed/manual`

## Required Release-Train Items

The Project must include these release-train issues:

- `#59` `M0 Naming & Governance Freeze`
- `#60` `M0 Naming & Governance Freeze`
- `#61` `M0 Naming & Governance Freeze`
- `#62` `M1 Security Baseline & Repo Hardening`
- `#63` `M2 Stability Core: Rollback, Evidence, API Boundaries`
- `#64` `M3 Setup Reliability & First-Run Experience`
- `#65` `M4 User Value Pack 1: Mix Review / Preflight / Organizer`
- `#66` `M5 Release Readiness / 3.0`

`M6 Jam-to-Project Alpha / 3.1` is the next planned release milestone after the
3.0 gates. The older `v2.1 Jam-to-Project` milestone is superseded.

## Semantic Fingerprint Rules

`scripts/check_github_project_fingerprint.py` verifies:

- Every issue labeled `github-source-of-truth` is present in Project #7.
- Every required 3.0 release-train issue is present in Project #7.
- Project items for source-of-truth issues have non-empty `Status`,
  `Roadmap Lane`, `Priority`, `Area`, `Type`, and `Safety` fields.
- Closed source-of-truth issues are `Status = Done` and
  `Roadmap Lane = Done`.
- Open issues labeled `release-blocker` have a milestone and
  `Priority = P0` in Project #7.

The check intentionally no longer hard-codes total item counts or exact lane
distributions. New source-of-truth issues should not break the fingerprint
merely because the roadmap grew.

## Milestones

Maintenance/backlog milestones:

- `GitHub Roadmap Migration`
- `Setup Reliability & Reporting`
- `API-backed Quick Wins`
- `Product Workflows`
- `Experimental/API-dependent`
- `Rejected / Not Planned`

Release-train milestones:

- `M0 Naming & Governance Freeze`
- `M1 Security Baseline & Repo Hardening`
- `M2 Stability Core: Rollback, Evidence, API Boundaries`
- `M3 Setup Reliability & First-Run Experience`
- `M4 User Value Pack 1: Mix Review / Preflight / Organizer`
- `M5 Release Readiness / 3.0`
- `M6 Jam-to-Project Alpha / 3.1`

## Source-of-Truth Rules

- GitHub Issues and Milestones are the durable planning source of truth.
- Project #7 is the canonical maintainer planning view.
- `ROADMAP.md`, `docs/CHANGELOG.md`, and `docs/generated/` are readable
  snapshots backed by the GitHub-to-Markdown snapshot workflow.
- Safety evidence still belongs in `docs/API_CAPABILITY_AUDIT.md`,
  `docs/VERIFICATION_HISTORY.md`, and `knowledgebase/`; GitHub planning does
  not replace verified API evidence.

## Verification Commands

```bash
gh project view 7 --owner thunderdew-dawn --format json
gh project field-list 7 --owner thunderdew-dawn --format json
gh project item-list 7 --owner thunderdew-dawn --limit 200 --format json
python scripts/check_github_project_fingerprint.py
```
