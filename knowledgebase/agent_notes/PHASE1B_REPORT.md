# fls-pilot — Phase 1B Report (plugin parameter control)

**Version:** 0.3.0 · **Env:** FL Studio Producer Edition v25.2.5 [build 5319], MIDI scripting v40, Windows, Python 3.12, loopMIDI · **Date:** 2026-05-24

Phase 1B adds read/write control of **plugin parameters** on mixer-track effect
slots, with name-or-index addressing and full snapshot/rollback. Tested against
the project's real **mixer track 2 (VOX)** — Fruity Parametric EQ 2 (slot 0) +
Fruity Reeverb 2 (slot 1). No new plugins were loaded (FL API can't).

---

## 1. The decision this phase answered

**Question:** do native FL plugins expose REAL parameter names, or the generic
4240-slot VST-wrapper behaviour? — that decides whether **name-based** addressing
(`"Decay time"`) is viable, or whether we're stuck with bare indices.

**Answer: native FL plugins expose real names AND small real counts AND readable
value strings.** Name-based addressing is reliable for them.

| Plugin | `getParamCount` | Names | Value strings |
|---|---|---|---|
| Fruity parametric EQ 2 | **36** (not 4240) | "Band 1 level", "Band 1 freq", "Band 1 type"… | `0.0dB`, `63Hz`, `Low shelf`, `61%` |
| Fruity Reeverb 2 | **15** | "Decay time", "Room size", "Wet level"… | `1.5sec`, `50`, `4.0kHz` |

(VST/AU wrappers still report ~4240 mostly-empty slots — for those, prefer int
indices. The handler skips empty-name params and reports the raw `total` so the
two cases are always distinguishable.)

### Full param dumps (evidence)

**Fruity parametric EQ 2 — track 2 slot 0 — total 36, all named:**
```
[ 0- 6] Band 1..7 level   0.5            0.0dB
[ 7-13] Band 1..7 freq    0.167..0.833   63Hz,136Hz,294Hz,632Hz,1363Hz,2936Hz,6324Hz
[14-20] Band 1..7 width   0.39/0.61      39% / 61%
[21-27] Band 1..7 type    —              Low shelf, Peaking×5, High shelf
[28-34] Band 1..7 order   0.5            2
[35]    Main level        0.5            0.0dB
```

**Fruity Reeverb 2 — track 2 slot 1 — total 15, all named:**
```
[ 0] Low cut 75Hz   [ 1] High cut 4.0kHz  [ 2] Predelay 0ms   [ 3] Room size 50
[ 4] Diffusion 100  [ 5] Decay time 1.5s  [ 6] High damping 4.0kHz
[ 7] Bass multiplier 100%  [ 8] Crossover 500Hz  [ 9] Stereo separation Original
[10] Dry level 100%  [11] Early reflection 50%  [12] Wet level 50%
[13] Mod Speed 33%   [14] Mod Depth 0%
```

---

## 2. Wire commands (controller) + FL API arg order

Added to `device_FLStudioPilot.py` (the `plugins` module is mixer-track scoped:
`index` = mixer track, `slot` = effect slot 0-9):

- `plugin_list(track)` → filled slots: `isValid(track,slot)` + `getPluginName(track,slot)`.
- `plugin_get_params(track, slot, start)` → **budget-paginated** dump
  (`getParamCount`, `getParamName(i,track,slot)`, `getParamValue`,
  `getParamValueString`). Scan-capped at 150/page, skips empty names, page JSON
  held under ~480 B, reports `total` + `next_start`.
- `plugin_get_param(track, slot, param)` → **single param** read (precise
  snapshot primitive; works even for unnamed VST params). *New this phase.*
- `plugin_set_param(track, slot, param, value)` → `setParamValue(value, param,
  track, slot)`, reads back `{v, s}`.

> **Slot indexing is 0-based.** EQ = slot **0**, Reeverb = slot **1** (the GUI's
> "slot 1/2" is 1-based). The tools discover slots via `plugin_list`, so callers
> never have to guess.

---

## 3. MCP tools (`src/fls_pilot/tools/plugin.py`)

- `fl_plugin_list(track)` — filled slots + plugin names.
- `fl_plugin_get_params(track, slot)` — every named param (auto-loops all pages
  via `fetch_all_pages`): `{total, params:[{i, name, v(0..1), s}]}`.
- `fl_plugin_set_param(track, slot, param, value)` — `param` is **int index OR
  str name**; `value` normalised **0..1**.

### Name resolution (`resolve_param_index`, module-level → unit-testable)
1. int / integer-like string → used directly (name looked up for the response).
2. str → normalise (lowercase, strip non-alphanumerics), then **exact match**;
3. else **unique substring match**;
4. ambiguous or missing → `ParamNotFound` listing the candidates, so the model
   corrects the spelling instead of poking the wrong knob.

### Values are normalised 0..1 only
`setParamValue` takes 0..1; there is no generic unit→normalised inverse
(`0.6` EQ band level = `3.6dB`, `0.65` = `5.4dB`). The display string from
`fl_plugin_get_params` tells you what a value maps to. Unit-typed setting
(e.g. "500 Hz") is intentionally **not** implemented — it would need per-param,
per-plugin curves we don't have.

---

## 4. Safety integration

`fl_plugin_set_param` routes through the existing `safety.safe_write`:
**snapshot → log → execute → read back**, honoring dry-run and producing a
rollback entry. New snapshot scope **`plugin_param:TRACK:SLOT:PARAM`** in
`take_snapshot()` reads the one param via `plugin_get_param`, and `build_restore`
replays the original value. So every param write is undo-able via
`fl_rollback_last_change` and recorded in `~/.fls-pilot/changelog.jsonl`.

---

## 5. Test results — all green

**`scripts/test_phase1b.py`** (bridge level, real Track 2):
- `plugin_list(2)` → slot 0 EQ, slot 1 Reeverb ✅
- full param dumps for both (36 / 15, all named, with value strings) ✅
- set→readback→rollback: EQ Band 1 level 0.5 (0.0dB) → 0.6 (3.6dB) → 0.5 (0.0dB) ✅

**`scripts/test_phase1b_tools.py`** (tool logic — `resolve_param_index` +
`safe_write` + `rollback`): **7/7 PASS**
| Check | Result |
|---|---|
| Reeverb `"Decay time"` → idx 5 | ✅ |
| EQ `"band 3 freq"` (case/space-insensitive) → idx 9 | ✅ |
| EQ int `35` → "Main level" | ✅ |
| bogus name → `ParamNotFound` (+candidates) | ✅ |
| name-based set Band 1 level 0.0dB→5.4dB landed | ✅ |
| changelog recorded the write | ✅ |
| rollback → 0.0dB (original) | ✅ |

**`scripts/test_phase1b_mcp.py`** (end-to-end through the **real registered MCP
tools**, in-process — also proves the Pydantic `Union[int,str]` coercion):
**PASS** — `fl_plugin_set_param(param="Dry level")` → resolved idx 10, 0.8→0.7;
`fl_rollback_last_change` → 0.8.

---

## 6. Using it from an MCP Client

- The FL **controller is already reloaded** (has `plugin_get_param`).
- The **daemon does NOT need restarting** — it forwards arbitrary commands.
- **Restart your MCP client once** so the spawned MCP server re-registers and the
  3 new tools (`fl_plugin_list`, `fl_plugin_get_params`, `fl_plugin_set_param`)
  appear. Total tools now **29**.

---

## 7. Limits / notes
- **Cannot load new plugins** (FL API) — only controls plugins already present.
- **VST/AU wrappers** report ~4240 generic slots → use int indices, not names.
- Values are **normalised 0..1**; no unit-typed setting (see §3).
- `plugin_get_params` **skips empty-name params**; raw `total` still reported so
  named-count vs total is visible.

## 8. Tests in repo (Phase 1B)
- `scripts/test_phase1b.py` — bridge-level: list + full dumps + set/rollback.
- `scripts/test_phase1b_tools.py` — tool logic: name resolve + safe_write + rollback.
- `scripts/test_phase1b_mcp.py` — end-to-end via real MCP tools (in-process).
