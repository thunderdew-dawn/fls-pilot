# VST Probe Findings

- **Date:** 2026-05-25
- **Agent/Author:** System Migration
- **Topic:** 3rd-party VST Parameter Exposure
- **Affected File/API:** FL Studio Plugin/Mixer API (`plugins.getParamName`, `plugins.getParamValueString`)
- **Confidence Level:** `implementation_verified`
- **Source/Method:** Probed FabFilter Pro-C 3 (`scripts/probe_vst.py`) on track 8, slot 4. FL Studio Producer Edition v25.2.5 [build 5319], Windows.

## Context
Question was whether FL's VST wrapper exposes real parameter names and readable value-strings for a 3rd-party plugin. If yes, the `calibrate -> intent` pattern works for VSTs exactly like native plugins.

## Observation & Result
**Verdict: YES ✅ (best case)**

- **`getParamName` returns REAL names:** e.g., `Threshold`, `Ratio`, `Knee`, `Range`, `Attack`, `Release`, `Lookahead`, `Hold`, `Mix`, `Output Level`, `Style`, `Auto Gain`. 100/100 named, zero "Param N".
- **`getParamValueString` returns READABLE UNITS:** e.g., `-16.00 dB`, `3.50:1`, `0.725 ms`, `100.0 ms`, `+7.35 dB`, `100.0%`. 100/100 non-empty.

**Details:**
- `getParamCount` = 4240 (the generic FL VST-wrapper signature), but the real params sit at LOW indices (0-99 for comp core).
- The existing paginated `plugin_get_params` (skips empty names, 150/page) works without controller stall.
- Pro-C 3 ratio is a clean `X:1` (e.g. `3.50:1`) — no bidirectional trap unlike Fruity Limiter.

## Tested Values
- FabFilter Pro-C 3 parameter sweep verified the strings.

## Known Pitfalls / Open Questions
- **Name Truncation & Collision:** The controller truncates names to 30 chars. Long sidechain-EQ names can collide.
- **Index Shifting:** A VST update could shift indices.
- **Addressing Recommendation:** Cache indices and re-validate `getParamName(index)` on connect instead of hardcoding indexes permanently.

## Next Recommended Action
Calibrate specific VSTs like Pro-C 3 COMP params and build VST compression intents on top of the generic plugin tools.
