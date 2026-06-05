# Serum 2 Probe Findings

- **Date:** 2026-05-25
- **Agent/Author:** System Migration
- **Topic:** Serum 2 Parameter & Preset Exposure
- **Affected File/API:** FL Studio Plugin/Channel API (`plugins.getParamName`, `plugins.getPresetCount`, `plugins.getName`)
- **Confidence Level:** `implementation_verified`
- **Source/Method:** Probed Serum 2 (`scripts/probe_serum.py` and `scripts/probe_serum_presets.py`) loaded as a generator on channel 10 (slot = -1). FL Studio Producer Edition v25.2.5 [build 5319], Windows.

## Context
Investigating if Serum 2 exposes parameter reads via the generator path, and if its internal preset browser (`.fxp` library) can be navigated or read via the FL API.

## Observation & Result
### 1. Parameter Read (Generator Path) — VIABLE ✅
- Generator addressing works through the existing handler (`plugins.getParamName(i, channel, -1)`). No new controller handler needed. (FLEX and Serum read fine, plain Sampler channels error gracefully).
- `getParamCount` = 4240 (VST-wrapper signature), but Serum exposes a large REAL set: 541 named params in idx 0–1024.
- **Names are REAL:** 541/541, zero "Param N".
- **Value-strings are READABLE:** 541/541 (e.g., `Main Vol "50% [-9.0 dB]"`, `A Level "75% [-5.0 dB]"`).
- **Names are well-structured:** by prefix (`A `/`B ` osc, `Filter`, `Env N`, `LFO N`, macros, `Main`).

### 2. Preset Recall — WALLED OFF ❌ (DEAD END)
- `plugins.getPresetCount` = 128 (the generic VST-wrapper program count), NOT Serum's internal `.fxp` library.
- `plugins.getName` flag 6 = "Prog 1" (generic), flag 3 = empty. No real preset names ("LD Supersaw" etc.).
- `plugins.nextPreset` ×5 → name stayed "Prog 1" every step. It does NOT drive Serum's internal preset browser.

**Conclusion:** FL cannot navigate or read Serum's preset library. Preset-recall by name is NOT possible for Serum via the FL API. DO NOT RETRY this path.

## Tested Values
- Serum 2 generator parameter read sweep and preset recall attempts.

## Known Pitfalls / Open Questions
- Exposing all 541 parameters blindly is too noisy. A curated subset is required.

## Next Recommended Action
- **Direction: build-from-params:** Serum work must be building/tweaking patches from parameters (curated param map + calibrate→intent), not preset recall.
- Scope a curated Serum param subset (osc A/B level+tune, filter cutoff/reso/type, amp env ADSR, master vol, a few macros).
- Requires a channel-generator MCP tool (`channel` + `slot=-1`).
