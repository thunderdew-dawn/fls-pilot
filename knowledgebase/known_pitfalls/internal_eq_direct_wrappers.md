# Internal EQ Direct Wrapper Registration

- **Date**: 2026-06-05
- **Agent/Author**: Codex
- **Topic**: Internal EQ wrappers were not rollback-backed public tools
- **Affected File/API**: `src/fls_pilot/tools/internal_eq.py`, native mixer EQ commands
- **Context**: During v1.2 legacy low-level removal, the public registration surface was reviewed for redundant and unsafe low-level wrappers.
- **Observation**: `internal_eq.py` registered functions through direct `mcp.tool()(fn)` calls and those setter functions called the bridge directly instead of `safety.safe_write`.
- **Tested Values**: Registration review showed these tools as unannotated public tools before removal: `read_internal_mixer_eq`, `set_internal_mixer_eq_gain_normalized`, `set_internal_mixer_eq_gain_db`, `set_internal_mixer_eq_frequency_normalized`, `set_internal_mixer_eq_frequency_hz`, `set_internal_mixer_eq_bandwidth_normalized`, `reset_internal_mixer_eq`, and `apply_internal_eq_cleanup_preset`.
- **Result**: The Internal EQ wrapper module is no longer registered publicly. Use `fl_effect(action="get_eq"|"set_eq_band", params=...)` for rollback-backed native EQ operations.
- **Confidence Level**: implementation_verified
- **Source/Method**: Static source inspection and public registration baseline check.
- **Valid Ranges**: Use the `fl_effect`/operation-registry validation for native EQ: track integer, band `0..2`, normalized gain/frequency/bandwidth `0..1`, and non-negative integer `type` where readback verifies behavior.
- **Example**: `fl_effect(action="set_eq_band", params={"track": 1, "band": 1, "gain": 0.6})`
- **Known Pitfalls**: A function name or docstring saying "safe" is not sufficient; public write tools must be annotated and route through the safety layer or an established undo-backed path.
- **Reproduction Steps**: Inspect `src/fls_pilot/tools/internal_eq.py` and run `.venv/bin/python scripts/check_tool_registration_baseline.py`.
- **Open Questions**: Whether calibrated dB/Hz Internal EQ helpers should be rebuilt as rollback-backed `fl_effect` actions is future scope.
- **Next Recommended Action**: Keep Internal EQ dB/Hz mappings out of public writes until implemented through the operation registry and safety layer.
