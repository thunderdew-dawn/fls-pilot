# Workflow Report Contract

- **Date:** 2026-06-13
- **Agent/Author:** Codex
- **Topic:** Unified proposal/report contract for diagnostics and organizer changes.
- **Affected File/API:** `src/fls_pilot/workflow_report.py`, `src/fls_pilot/tools/mix_doctor.py`, `src/fls_pilot/tools/project_doctor.py`, `src/fls_pilot/tools/project_organizer.py`, `fl_review_mix`, `fl_gain_stage`, `fl_review_low_end_stereo`, `fl_project_health_report`, `fl_export_readiness_report`, `fl_project_dry_run_fix_plan`, `fl_project_health_overview`, `fl_check_project_preflight`, `fl_analyze_project_organization`, `fl_plan_project_cleanup`, `fl_apply_project_cleanup_step`, `fl_apply_naming_standard`, `fl_apply_color_standard`, `fl_apply_mix_adjustment`.
- **Context:** v3 is a breaking release, so workflow outputs can move from ad hoc `findings`/`proposals` shapes to one explicit proposal/report contract.
- **Observation:** User-facing diagnostics need useful read-only output, clear separation between proposed and applied changes, risk ratings, and Markdown/JSON renderings. Persistent organizer and Mix Review writes must not run unless the exact change was explicitly approved.
- **Tested Values:** Mix Review synthetic reports, Project Doctor preflight/readiness reports, Project Organizer invalid color rejection, Mix Review trim approval gate, compile checks for touched modules.
- **Result:** Reports use contract version `fls-pilot.workflow-report.v1` with `diagnostics`, `proposed_changes`, `applied_changes`, `skipped_changes`, `manual_checks`, `safety`, `kb_policy_refs`, `metadata`, `json_report`, and `markdown_report`. Organizer apply tools and `fl_apply_mix_adjustment` require `approved=True`; unapproved calls return `mode="approval_required"` with no FL write. Approved organizer cleanup can apply renames, colors, and channel-routing cleanup through `safety.safe_write_group`.
- **Confidence Level:** `implementation_verified`
- **Source/Method:** Static implementation review plus focused offline tests.
- **Valid Ranges:** Proposal `risk_level` is one of `read-only`, `low`, `medium`, `high`, or `unsupported`. Persistent applied changes inherit operation-registry validation and safety-layer readback/rollback metadata.
- **Example:** `fl_plan_project_cleanup` returns read-only `proposed_changes`; a channel-routing cleanup proposal targets `fl_apply_project_cleanup_step` with `routing=[{"channel": N, "mode": "free"}]` and `approved=True` in the proposed params. The apply tool still performs no mutation until called with `approved=True`.
- **Known Pitfalls:** Do not read old `findings`, `proposals`, `plan`, `ready`, `blockers`, or `manual_checklist` keys from these v3 workflow tools. Use the contract fields instead. Do not treat `proposed_changes[*].params.approved=True` as approval by itself; it is the exact follow-up call shape after explicit user approval.
- **Reproduction Steps:** Run `.venv/bin/python tests/test_mix_doctor.py`, `.venv/bin/python tests/test_project_doctor.py`, and `.venv/bin/python tests/test_product_workflow_registry_refactor.py`.
- **Open Questions:** Live FL Studio smoke tests were not run for the newly gated organizer routing cleanup path.
- **Next Recommended Action:** Update any remaining guided-cleanup orchestration copy to consume the v3 contract fields directly.
