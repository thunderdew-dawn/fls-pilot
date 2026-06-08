# Release Strategy

This document records the 2026-06-08 release-train decision for the maintained
fork. GitHub Issues, Milestones, and Project #7 remain the planning source of
truth; this file explains the release sequencing and gates so agents do not
re-infer it from local chat.

## Current Baseline

- Latest published GitHub release: `v2.0.0-stable`, published 2026-06-07.
- Current package metadata: `fl-studio-mcp` package version `2.0.0`.
- Planned identity break: `fls-pilot` means `FL Studio Pilot`.
- The rename is intentionally breaking: no old CLI, package, or import aliases
  are retained after the 3.0 cut.

## Label And Planning Rules

- Canonical labels are `priority:*`, `type:*`, `area:*`, status labels,
  safety labels, `release-blocker`, and `github-source-of-truth`.
- Legacy labels such as `P0`, `P1`, `bug`, `enhancement`, `documentation`,
  `safety`, `ux`, `workflow`, and `rollback` are not canonical for new work.
  They may remain on historical issues only until those issues are normalized.
- Every open 3.0 release blocker must have a milestone, Project #7 item, P0
  priority, acceptance criteria, and a clear owner/slice path before work
  starts.
- The private Project #7 is the maintainer planning view; generated Markdown
  snapshots in `docs/generated/` are the readable public view.

## Release Train

### v2.0.1-maintenance

Purpose: governance, GitHub automation, label cleanup, and release-process
hardening only.

Allowed:
- GitHub workflow fixes.
- Issue templates and release-note categories.
- Planning docs and generated snapshots.
- Branch/security documentation.

Not allowed:
- New FL Studio user-facing tool behavior.
- Package/import rename.
- New API capability claims.

### v3.0.0-alpha.1

Purpose: first installable alpha under the `fls-pilot` identity.

Scope:
- Repository/package/CLI/import rename to `fls-pilot` and `fls_pilot`.
- MCP/server metadata and docs updated to `FL Studio Pilot`.
- Migration notes for the breaking rename.
- No compatibility aliases for old names.

Exit:
- Fresh editable install works.
- New CLI starts.
- Tests and safety audits pass.
- README and quickstart use only new public names.

### v3.0.0-alpha.2

Purpose: release the safety core under the new name.

Scope:
- Confirm every persistent FL Studio write is classified and rollback-first.
- Keep operation registry and safety audit at zero write gaps.
- Ensure user-facing mutation reports include before/after, risk, and rollback
  availability where supported.

Exit:
- No persistent write bypasses the safety layer.
- CI catches unclassified or undocumented write tools.
- Release-blocking safety issues are closed or explicitly blocked with
  evidence.

### v3.0.0-beta.1

Purpose: safe first-run and setup trust.

Scope:
- Read-only setup doctor and first-run diagnostics.
- Python/dependency/MIDI/bridge/MCP-client checks.
- Clear remediation output.
- README quickstart starts with doctor/read-only diagnostics before writes.

Exit:
- Fresh setup can be diagnosed without project mutation.
- Setup failures produce actionable output suitable for GitHub issues.

### v3.0.0-beta.2

Purpose: first user-value beta after rename, safety, and setup gates.

Scope:
- Mix Review read-only baseline.
- Project Preflight report.
- Organizer proposal mode.
- Risk-rated proposals.
- Apply only after explicit approval, through rollback-safe paths.
- Markdown and JSON reports.

Exit:
- Users can receive useful project diagnostics without mutation.
- Proposals are clearly separated from applied changes.
- Every applied persistent change has a rollback unit.

### v3.0.0-rc.1

Purpose: release freeze and final verification.

Scope:
- No new features.
- Docs, migration guide, changelog, release notes, and smoke checks.
- P3 experimental topics frozen until after stable 3.0.

Exit:
- No open `release-blocker` issues for 3.0.
- CI, CodeQL, release dry run, safety audit, and focused smoke checks pass.
- Fresh install and one rollback-safe live write smoke are documented when FL
  Studio is available.

### v3.0.0

Purpose: stable breaking release under the `fls-pilot` name.

Positioning:
- New name: `fls-pilot` / `FL Studio Pilot`.
- Safety contract: rollback-first writes, classified operation surface, no raw
  unsafe shortcuts.
- First-run trust: setup doctor and read-only diagnostics before mutation.

### v3.1.0-alpha.1

Purpose: Jam-to-Project alpha after the 3.0 foundation is stable.

Scope:
- Read-only jam-session analysis.
- Structured cleanup plan generation.
- Markdown/JSON preview report.
- Risk ratings and planned rollback groups.
- Optional low-risk apply prototypes only when the 3.0 safety contract fully
  covers them.

Not allowed:
- Playlist clip movement or deletion.
- Pattern or clip deletion.
- Plugin loading.
- Stretch Pro or Normalize automation claims.
- Full-project restore claims.
- Broad UI automation.

## Tag And Version Policy

- Stable tags use `vX.Y.Z`.
- Historical stable suffix tags such as `v2.0.0-stable` map to package version
  `X.Y.Z`.
- Alpha tags use `vX.Y.Z-alpha.N` and map to Python version `X.Y.ZaN`.
- Beta tags use `vX.Y.Z-beta.N` and map to Python version `X.Y.ZbN`.
- RC tags use `vX.Y.Z-rc.N` and map to Python version `X.Y.ZrcN`.
- The release workflow validates that the tag and `pyproject.toml` version
  match before creating a GitHub release.
