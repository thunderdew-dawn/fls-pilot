# GitHub Planning

GitHub Issues and Milestones are the planning source of truth for open roadmap
work after the 2026-06-08 migration. Markdown roadmap and changelog files remain
readable snapshots until automated GitHub-to-Markdown generation is implemented.

## Current Structure

- Canonical project: [FL Studio MCP Core Roadmap](https://github.com/users/thunderdew-dawn/projects/7).
- Existing similar project: [FL Studio MCP Roadmap](https://github.com/users/thunderdew-dawn/projects/6).
  It also contains the migrated issues, but Project #7 is the canonical roadmap
  view because it has the richer planning fields. Do not create a third
  duplicate project.
- Fingerprint: [`issue_project_fingerprint.md`](issue_project_fingerprint.md)
  records the expected project IDs, fields, item range, and count checks.
- Label `github-source-of-truth` marks migrated planning issues.
- Priority labels: `priority:p0`, `priority:p1`, `priority:p2`, `priority:p3`.
- Area labels: `area:safety`, `area:workflow`, `area:docs`, `area:github`,
  `area:kb`, `area:ux`, `area:api`.
- Type labels: `type:roadmap`, `type:workflow`, `type:doctor`, `type:report`,
  `type:github-sync`.
- Safety labels: `read-only`, `write-safe-required`, `api-dependent`.

## Project Fields

Project #7 has these roadmap fields populated for issues #3 through #34:

- `Roadmap Lane`: `Now`, `Next`, `Later`, `Blocked`, `Done`.
- `Priority`: `P0`, `P1`, `P2`, `P3`.
- `Area`: `Safety`, `Workflow`, `Docs`, `GitHub`, `KB`, `UX`, `API`.
- `Type`: `Roadmap`, `Workflow`, `Doctor`, `Report`, `GitHub Sync`.
- `Safety`: `Read-only`, `Write-safe required`, `API-dependent`,
  `Mixed/manual`.

## Milestones

- `GitHub Roadmap Migration`
- `Setup Reliability & Reporting`
- `v2.1 Jam-to-Project`
- `Product Workflows`
- `Experimental/API-dependent`

## Migration Notes

- Open items from `ROADMAP.md` were migrated to GitHub issues #3 through #34.
- Project #7 is configured with all migrated issues and the project fields
  listed above. Initial lanes are `Now` for #3, #9, and #10; `Next` for #4,
  #5, and #6; and `Later` for the remaining migrated items.
- GitHub-to-Markdown generation for `ROADMAP.md` and `docs/CHANGELOG.md` is
  tracked in issue #10.
- GitHub Projects require an auth token with project scopes. Keep Issues and
  Milestones as the durable source data and treat the Project as a planning
  view.
