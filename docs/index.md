# Development Guide

Use this path when changing code, tests, docs, scripts, controller files, Knowledgebase files, workflows, packaging, or project behavior.

## Mandatory First Reads

Before changing code, tests, docs, scripts, controller files, skill files, evals, or roadmap state, read these files and follow them as binding project instructions:

* `docs/engineering/standards.md`
* `docs/project/ROADMAP.github.md`
* `docs/concepts/safety-model.md`
* `docs/agents/knowledgebase-protocol.md`

If any file conflicts with an ad-hoc prompt, stop and surface the conflict before implementing. The safety model, engineering standards, Knowledgebase protocol, and roadmap scope are not optional.

For GitHub planning, issue/PR work, roadmap execution, releases, dependency updates, security alerts, bug triage, reviews, hotfixes, reverts, documentation-only changes, API probes, or backports, additionally read:

* `docs/agents/github-playbook.md`

## Working Mode

* Act as a senior, pragmatic software engineer.
* Inspect the repo before changing it. Read surrounding code, existing tool patterns, tests, safety layer, protocol constants, controller handlers, and registration style.
* For implementation work, explicitly inspect the relevant parts of `ROADMAP.md`, `docs/project/ROADMAP.github.md`, `docs/concepts/api-capability-audit.md`, `src/fls_pilot/safety.py`, `src/fls_pilot/protocol.py`, the FL controller script, existing tool modules, and focused tests/scripts before editing.
* For non-trivial implementation slices, produce a short implementation plan before editing and confirm the slice is dependency-correct and rollback-safe.
* Before building anything new, check whether the functionality already exists under a different name or can be composed from existing safe primitives.
* Prefer existing project patterns over new abstractions.
* Use established patterns: protocol constants, controller handlers, `safety.safe_write`, `safety.safe_write_group`, Piano Roll safety helpers, focused tests/scripts, and FastMCP registration style.
* Keep edits small, coherent, and backport-friendly.
* Preserve all user and uncommitted changes. Never revert unrelated work.
* Use English for commits, code comments, docstrings, and repo documentation.

## Knowledgebase And Token-Efficient Development

* Check `knowledgebase/` before changing or adding behavior that depends on FL Studio API behavior, mixer/plugin parameters, MIDI, automation, REC events, normalized values, dB/Hz mappings, ranges, known pitfalls, or reusable production rules.
* Do not guess FL Studio API ranges, normalized values, dB/Hz mappings, REC event IDs, track indices, plugin parameter indices, or valid value ranges.
* If new verified knowledge is discovered, update the Knowledgebase as part of the same slice:

  * Use Markdown for human-readable findings.
  * Use JSON or YAML when the knowledge is machine-actionable.
  * Put disproven assumptions and recurring mistakes in `knowledgebase/known_pitfalls/`.
* Prefer token-efficient implementation and review patterns:

  * Prefer high-signal domain/workflow tools over many narrow one-off tools.
  * Avoid unnecessary MCP roundtrips.
  * Prefer safe grouped reads/writes or server-side orchestration when this reduces token use and tool-selection noise.
  * Document token/tool-surface impact when adding or expanding MCP tools.

## Implementation Checklist

For every new FL-mutating tool, add or update:

* Protocol command constants, if needed.
* FL controller handler.
* Snapshot scope.
* Restore operation.
* Readback verification.
* Safety-layer integration via the established safety helpers.
* Tool annotations and docstring explaining safety behavior.
* Static audit compatibility.
* Focused script/unit test or rollback-safe live smoke script.
* Roadmap/API audit/docs note when behavior or scope changes.
* Knowledgebase entry or update when the tool depends on verified FL Studio behavior, mappings, ranges, parameters, or known limitations.

## Verification Expectations

Run the smallest meaningful checks for the changed area, then broaden when the blast radius justifies it:

* Compile checks for touched Python code.
* `scripts/audit_tool_safety.py --fail-on-gaps`.
* `scripts/audit_tool_safety.py --fail-on-missing-safety-docs --format json` when tool annotations or docstrings change.
* Focused script tests for changed areas.
* FastMCP registration/tool-count checks when tool registration changes.
* Rollback-safe live smoke tests when FL Studio is available and the change touches live behavior.

If repo-wide `pytest` or `ruff` failures are pre-existing, report them separately and do not churn unrelated code.

At handoff, summarize changed files, verification run, remaining risks or API limits, Knowledgebase changes, and the next recommended roadmap slice.

## Local Environment

* Python target: 3.12 for current development on this machine. Package metadata still supports Python 3.10+ unless changed deliberately.

* On macOS, commands importing pip, XML, or audio dependencies may need:

  export DYLD_LIBRARY_PATH="/usr/local/opt/expat/lib:${DYLD_LIBRARY_PATH:-}"

* Prefer `rg` and `rg --files` for search.

* Use `apply_patch` for manual file edits.

* Do not use destructive Git commands unless explicitly requested.

## Live FL Studio Procedure

* Start the TCP daemon yourself when live tests require it.
* Confirm heartbeat and `fl_transport(action="ping")` before live work.
* Confirm the controller build marker expected by the current code.
* Read current state before writing.
* For live write tests, write a temporary value, verify readback, rollback immediately, and verify restoration.
* If MIDI routing, script reload, or restart state is uncertain, diagnose the connection before changing code.
* Stop daemons you started and leave playback stopped/recording disarmed after tests.

## Workspace And File Artifact Protocol

To keep the workspace clean and maintain context for generated artifacts, agents must use these output directories. Never write files directly to the root of `scratch/` or the project root.

* Temporary scripts: `scratch/scripts/`
* Generated MIDI: `scratch/midi/`
* Analysis data and state dumps: `scratch/analysis/`
* Audio files: `scratch/audio/`
* Logs: `scratch/logs/`

Use session- or task-specific subdirectories where appropriate, for example `scratch/analysis/YYYY-MM-DD_session_name/`.
