# Transport Domain Tool

- **Date**: 2026-06-04
- **Agent/Author**: Codex
- **Topic**: Consolidated `fl_transport` MCP wrapper
- **Affected File/API**: `src/fls_pilot/tools/transport.py`, `src/fls_pilot/operations.py`, transport protocol commands
- **Context**: v1.2 slice 05 added an additive domain tool beside legacy transport tools for parity testing and lower tool-selection overhead. Slice 14 retired the legacy transport aliases from public registration.
- **Observation**: `fl_transport(action, params)` validates transport actions through the internal operation registry where applicable, dispatches read-only and transient commands directly to the bridge, dispatches persistent writes through `safety.safe_write`, and handles `ping` as the consolidated bridge-health action.
- **Tested Values**: Unit-tested `ping`, `get_tempo`, `set_tempo` with `bpm=128`, `play`, unknown action, and out-of-range `bpm=1000` against a fake bridge.
- **Result**: Read and transient actions use registry-built protocol payloads. Tempo writes use the rollback-backed safe-write path with tempo snapshot and readback. `ping` reports heartbeat/port/controller data through `fl_transport` after `fl_ping` was removed from public registration.
- **Confidence Level**: implementation_verified
- **Source/Method**: Focused pytest coverage and static safety/registration audits in the local repo.
- **Valid Ranges**: Registry validation currently allows tempo `10..999` BPM, time-signature denominators `4` or `8`, and non-negative song position values in exactly one of `beats`, `ms`, or `ticks`.
- **Example**: `fl_transport(action="ping")`; `fl_transport(action="set_tempo", params={"bpm": 128})`
- **Known Pitfalls**: The tool's annotation is `write-safe-required` because the same public function can perform persistent writes; read-only and transient action safety is action-specific in the implementation and docstring.
- **Reproduction Steps**: Run `.venv/bin/python -m pytest tests/test_transport_domain.py`.
- **Open Questions**: Live FL Studio smoke was not run for this slice; behavior mirrors existing legacy transport wrappers and registry specs.
- **Next Recommended Action**: Run slice 15 final release docs and audit.
