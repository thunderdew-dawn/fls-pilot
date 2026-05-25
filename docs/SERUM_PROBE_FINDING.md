# flstudio-mcp — Serum 2 probe findings (generator path + presets)

**Version:** 0.3.0 · **Env:** FL Studio Producer Edition v25.2.5 [build 5319], Windows · **Date:** 2026-05-25 · Serum 2 = channel-rack **generator** on channel 10 (slot = -1).

Two READ-only probes decided the Serum direction.

## 1. Param read (generator path) — VIABLE ✅  (`scripts/probe_serum.py`)

- **Generator addressing works through the EXISTING handler**: `plugin_get_params`
  with `track=<channel>, slot=-1` hits `plugins.getParamName(i, channel, -1)` —
  the generator form. **No new controller handler needed.** (Plain Sampler
  channels return `isValid(c,-1)=False` and error gracefully; VST/native-synth
  generators like FLEX and Serum read fine.)
- `getPluginName(10,-1)` = **"Serum 2"**. `getParamCount` = **4240** (VST-wrapper
  signature), **but Serum exposes a large REAL set**: **541 named params in idx
  0–1024** (hit the 1024 scan cap → more exist beyond).
- **Names REAL** (541/541, zero "Param N"), **value-strings READABLE** (541/541):
  `Main Vol "50% [-9.0 dB]"`, `A Level "75% [-5.0 dB]"`, `A Octave "0 oct"`,
  `A Semi "0 semitones"`, `Porta Time "0.0 ms"`, etc.
- Names are **well-structured by prefix** (`A `/`B ` osc, `Filter`, `Env N`,
  `LFO N`, macros, `Main`) → a **curated subset** is the practical path (541 is
  too many to expose blindly).

## 2. Preset recall — WALLED OFF ❌ (DEAD END)  (`scripts/probe_serum_presets.py`)

Tested `plugins.getPresetCount / nextPreset / prevPreset / getName` on the
generator (via the new `plugin_preset` controller command):

- `getPresetCount` = **128** — the generic **VST-wrapper program count** (MIDI
  0–127 convention), **NOT** Serum's internal `.fxp` library (which would be
  thousands).
- Current preset name: `getName` flag 6 = **"Prog 1"** (generic), flag 3 =
  **empty**. No real preset names ("LD Supersaw" etc.).
- **`nextPreset` ×5 → name stayed "Prog 1" every step** — it does NOT drive
  Serum's internal preset browser, and no readable preset name is exposed.

**Conclusion: FL cannot navigate or read Serum's preset library. Preset-recall
by name ("vintage bass" → load a real pro preset) is NOT possible for Serum via
the FL API. DO NOT RETRY this path.**

## 3. Direction: build-from-params

Serum work = **build / tweak patches from parameters** (curated param map +
calibrate→intent), not preset recall. Next slice scopes:
- a **curated Serum param subset** (osc A/B level+tune, filter cutoff/reso/type,
  amp env ADSR, master vol, a few macros),
- calibration of those params (norm↔unit), and
- a **channel-generator MCP tool** (`channel` + `slot=-1`) — the current
  `fl_plugin_*` tools block `slot<0`, though the controller handler already
  supports generators.

## Tooling note
The `plugin_preset` controller command (build `slice-preset-v7`) works but is
**not useful for Serum** (confirmed walled off). Leaving it in place — it may
help with native FL plugins / other VSTs later; not wired to any MCP tool.
