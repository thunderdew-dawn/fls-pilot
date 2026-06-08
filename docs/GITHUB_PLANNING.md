# GitHub Planning

GitHub Issues and Milestones are the planning source of truth for open roadmap
work after the 2026-06-08 migration. Markdown roadmap and changelog files remain
readable snapshots until automated GitHub-to-Markdown generation is implemented.

## Current Structure

- Label `github-source-of-truth` marks migrated planning issues.
- Priority labels: `priority:p0`, `priority:p1`, `priority:p2`, `priority:p3`.
- Area labels: `area:safety`, `area:workflow`, `area:docs`, `area:github`,
  `area:kb`, `area:ux`, `area:api`.
- Type labels: `type:roadmap`, `type:workflow`, `type:doctor`, `type:report`,
  `type:github-sync`.
- Safety labels: `read-only`, `write-safe-required`, `api-dependent`.

## Milestones

- `GitHub Roadmap Migration`
- `Setup Reliability & Reporting`
- `v2.1 Jam-to-Project`
- `Product Workflows`
- `Experimental/API-dependent`

## Migration Notes

- Open items from `ROADMAP.md` were migrated to GitHub issues #3 through #34.
- GitHub-to-Markdown generation for `ROADMAP.md` and `docs/CHANGELOG.md` is
  tracked in issue #10.
- GitHub Projects require an auth token with project scopes. If Projects are
  enabled later, keep Issues and Milestones as the durable source data and treat
  the Project as a planning view.
