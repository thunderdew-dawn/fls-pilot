# Batch Tool

- **Date**: 2026-06-05
- **Agent/Author**: Codex
- **Topic**: `fl_batch` MCP wrapper for read-only batches and persistent write batches
- **Affected File/API**: `src/fls_pilot/tools/batch.py`, `src/fls_pilot/server.py`, `src/fls_pilot/operations.py`, `safety.safe_write_group`, operation-registry protocol commands
- **Context**: v1.2 slices 11 and 12 expose one public `fl_batch` surface for strict operation-registry batches.
- **Observation**: `fl_batch(operations, continue_on_error=False)` validates every operation through the internal operation registry before any bridge calls. It accepts only registry IDs shaped as `{domain, action, params?}` from read-only or persistent-write whitelists. Read-only batches execute registry-built read commands directly. Persistent write batches must be homogeneous, reject `continue_on_error`, and execute through `safety.safe_write_group` as one named rollback unit.
- **Tested Values**: Successful read-only batch with `transport.get_tempo`, `mixer.get`, and `channel.get_selected`; 51-operation max rejection; raw `command` and `script_text` rejection; mixed read/write rejection; runtime read failure with and without `continue_on_error`; successful persistent write batch with two `mixer.set_mute` operations; invalid write validation with no bridge calls; write `continue_on_error` rejection; rollback of a successful write batch; persistent write dry-run plan; partial write failure with immediate group rollback.
- **Result**: Invalid structure, raw/script fields, non-whitelisted actions, mixed categories, transient controls, and excluded actions fail before mutation. Read-only runtime failures stop the batch unless `continue_on_error` is true. Persistent write batches snapshot all scopes, build restore actions, execute with readback through `safe_write_group`, log one rollback unit, and roll back executed writes on partial failure.
- **Confidence Level**: implementation_verified
- **Source/Method**: Focused FastMCP unit tests with a fake bridge, static safety audit, safety-doc audit, and registration baseline check.
- **Valid Ranges**: Maximum `50` operations per batch. Each operation object supports only `domain`, `action`, and optional object-valued `params`.
- **Example**: Read: `fl_batch(operations=[{"domain": "transport", "action": "get_tempo"}, {"domain": "mixer", "action": "get", "params": {"track": 1}}])`. Write: `fl_batch(operations=[{"domain": "mixer", "action": "set_mute", "params": {"track": 1, "state": true}}, {"domain": "mixer", "action": "set_mute", "params": {"track": 2, "state": true}}])`.
- **Known Pitfalls**: Batches cannot mix reads and writes. Persistent write batches reject `continue_on_error`. Raw protocol commands and script/code text are rejected. Transient runtime controls, external writes, and Piano Roll generated-script actions are excluded from `fl_batch`. List operations use their registry command payloads; richer workflow batching remains future scope.
- **Reproduction Steps**: Run `.venv/bin/python -m pytest tests/test_batch_read_only.py tests/test_batch_persistent_writes.py`.
- **Open Questions**: Live FL Studio smoke tests were not run for persistent write batching. Some underlying registry write specs remain build/API dependent and rely on their existing readback behavior.
- **Next Recommended Action**: Run slice 12 review before product workflow refactors.
