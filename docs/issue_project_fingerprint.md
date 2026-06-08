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
- Expected item count: `46`
- Expected issue range: `#3` through `#48`
- Expected field count at verification time: `23`

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

## Expected Distribution

### Roadmap Lane

- `Now`: `3`
- `Next`: `3`
- `Later`: `33`
- `Blocked`: `0`
- `Done`: `7`

Initial lane assignment after the extension-review triage:

- `Now`: `#3`, `#9`, `#10`
- `Next`: `#4`, `#5`, `#6`
- `Later`: open backlog issues except the `Now` and `Next` items
- `Done`: rejected/not-planned issues `#42` through `#48`

### Status

- `Todo`: `36`
- `Next`: `2`
- `In progress`: `1`
- `Done`: `7`

### Priority

- `P0`: `3`
- `P1`: `6`
- `P2`: `25`
- `P3`: `12`

## Milestones

- `GitHub Roadmap Migration`
- `Setup Reliability & Reporting`
- `API-backed Quick Wins`
- `v2.1 Jam-to-Project`
- `Product Workflows`
- `Experimental/API-dependent`
- `Rejected / Not Planned`

## Source-of-Truth Rules

- GitHub Issues and Milestones are the durable planning source of truth.
- Project #7 is the canonical planning view.
- Project #6 is retained only as a secondary/legacy view.
- `ROADMAP.md` and `docs/CHANGELOG.md` remain readable snapshots until issue
  #10 implements GitHub-to-Markdown generation.
- Safety evidence still belongs in `docs/API_CAPABILITY_AUDIT.md`,
  `docs/VERIFICATION_HISTORY.md`, and `knowledgebase/`; GitHub planning does
  not replace verified API evidence.

## Verification Commands

```bash
gh project view 7 --owner thunderdew-dawn --format json
gh project field-list 7 --owner thunderdew-dawn --format json
gh project item-list 7 --owner thunderdew-dawn --limit 100 --format json
```

Useful count checks:

```bash
gh project item-list 7 --owner thunderdew-dawn --limit 100 --format json \
  | jq '[.items[]."roadmap Lane"] | group_by(.) | map({lane: .[0], count: length})'

gh project item-list 7 --owner thunderdew-dawn --limit 100 --format json \
  | jq '[.items[].priority] | group_by(.) | map({priority: .[0], count: length})'
```
