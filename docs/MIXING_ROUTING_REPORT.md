# flstudio-mcp — Mixing Intents + Routing Report

**Version:** 0.3.0 · **Env:** FL Studio Producer Edition v25.2.5 [build 5319], MIDI scripting v40, Windows, Python 3.12 · **Date:** 2026-05-25

Covers everything since the Phase 1B restore point: high-level **EQ / reverb /
delay mixing intents** (built on empirically-calibrated plugin curves) and the
**routing/grouping** surface (read + write). One architectural principle drove
all of it.

---

## 0. Architecture principle (the big lesson)

**Controller stays THIN; the server does the THINKING.**

The FL controller-script sandbox stalls on heavy work in a single `OnSysEx`
tick (hundreds of API calls, or `getGridBit` on audio channels). So:
- The controller only returns **cheap RAW data** (names, params, routes, plugin
  slots) and does **simple** writes (`setParamValue`, `setRouteTo`).
- All **judgement / orchestration** (empty/unused detection, grouping) lives on
  the **server** (plain Python, no sandbox limits), aggregating several cheap
  controller calls.

Bonus: server-side logic changes need **no controller reload** — which matters
because FL's toggle / "Update MIDI scripts" reload proved **unreliable** (a full
FL restart is the only sure reload). Keeping logic server-side sidesteps that.

---

## 1. Plugin parameter calibration (empirical)

Swept each param 0..1 and parsed FL's display strings (`scripts/calibrate_eq.py`,
`scripts/calibrate_reverb_delay.py`). Every plugin is calibrated **individually**
— curves are plugin-specific.

**Fruity Parametric EQ 2** (`music/eq_curves.py`)
- freq: **logarithmic** `Hz = 20·10^(3·norm)` (20 Hz–20 kHz)
- level: **linear** `dB = 36·norm − 18` (±18 dB)
- width: **linear** `% = 100·norm`
- type: **8 discrete** filter types snapped to k/7

**Fruity Reeverb 2 + Fruity Delay 3** (`music/reverb_delay_curves.py`)
- reverb decay **linear** 0.1–20 s; wet **linear** 0–125 %; room **linear**;
  high-cut / low-cut **linear Hz** with **"Off" endpoints**
- delay wet/dry/spread **linear %**; feedback **linear** 0–125 % (clamped ≤100 %
  unless explicitly pushed); feedback-cutoff **piecewise** (table interp); Time =
  tempo-synced **musical divisions** (1/16…1/1)

Native FL plugins expose **real param names + small counts** (EQ2=36, Reeverb=15,
Delay3=26) — not the ~4240 generic slots a VST wrapper reports — so name-based
addressing is reliable for them.

---

## 2. Mixing intents (`tools/mixing.py`)

High-level, musically-named moves; each picks/edits the right params, applies
them as ONE rollback unit, and returns FL's readback strings.

- **`fl_apply_eq_intent(track, slot, intent, intensity=0.5)`** — finds a FREE EQ
  band, sets type+freq+gain+width together. Intents: `remove_mud` (Peaking 250 Hz),
  `add_air` (High shelf 12 kHz), `remove_harshness` (3 kHz), `add_presence`
  (5 kHz), `high_pass`. Gain scales `max_dB·intensity`.
- **`fl_apply_reverb_intent`** — `more_space`, `tighten_reverb`, `darker_reverb`,
  `brighter_reverb`, `more_reverb`, `less_reverb`.
- **`fl_apply_delay_intent`** — `longer/shorter_delay` (step musical division),
  `more/less_feedback` (clamped ≤100 % unless intensity>0.9, warns on
  self-oscillation), `more/less_delay` (output wet), `darker/brighter_delay`
  (feedback cutoff).

**Tests:** `test_mixing_intents.py` **21/21**; `test_reverb_delay_intents.py`
**33/33** (e.g. `remove_mud(0.5)`→Band 1 Peaking/250 Hz/−3.0 dB; `add_air(0.7)`
→High shelf/12 kHz/+4.2 dB; reverb/delay moves land + roll back exactly).

---

## 3. Routing read — Slice 1 (`tools/routing.py`)

Thin controller reads + **server-side** cleanup judgement.
- `fl_get_routing(track)` / `fl_get_routing_all()` — send matrix (default →
  Master confirmed visible). Budget-paginated.
- `fl_get_channel_routing()` — channel → mixer links (`getTargetFxTrack`;
  `target_fx_track` also added to the single-channel read).
- `fl_detect_cleanup_candidates()` — **judgement on the server**: derives
  channel-targets + incoming-routes from cheap reads, then `plugin_list` only for
  surviving candidates. Flags **unused mixer tracks** (reliable: no channel + no
  plugin + default name + nothing routed in) and **empty channels** (name
  heuristic only — the API can't cheaply see clip/piano-roll content).

**Test:** `test_routing_read.py` — matrix + channel links accurate; cleanup
flagged only the genuinely-empty `Insert` tracks; **no in-use track** (VOX,
Future Trumpet, named/plugin tracks) was ever flagged.

> A first attempt put the detection loop *in the controller* — it stalled FL
> (timed out even at 20 s). Moving the judgement to the server fixed it and
> removed the reload dependency. That's principle #0 in action.

---

## 4. Routing write + grouping — Slice 2

- Controller: one thin handler **`mixer_set_route`** (`setRouteTo` +
  `afterRoutingChanged` + readback).
- Safety: new **`route:src:dst`** snapshot scope.
- **`fl_set_route(src, dst, enabled)`** — single routing edit; snapshot → write →
  readback → rollback-able. **Test 7/7** (adds 9→1, default 9→Master untouched,
  rollback restores).
- **`fl_group_tracks(sources, bus, name?)`** — **exclusive** bus grouping
  (each source → bus ON, source → Master OFF; bus → Master ON; optional bus
  rename), applied as ONE `safe_write_group` so a single rollback undoes the
  whole group. Pure server orchestration of live commands → **no reload**.
  **Test 7/7**; confirmed live (RHYTHM bus on track 10, Percussion + Drums
  grouped into it).
- Rename reuses Phase 1A `fl_set_mixer_name`.

---

## 5. Safety model (unchanged, extended)

Every write routes through `safety.safe_write` (single) or
`safety.safe_write_group` (multi = one rollback unit): **snapshot → log →
execute → read back**. Honors dry-run. Snapshot scopes now cover mixer/channel,
`plugin_param`, and `route`. `fl_rollback_last_change` replays the last entry
(single or grouped). Changelog persists to `~/.flstudio-mcp/changelog.jsonl`.
No delete operations are implemented.

---

## 6. Known constraints discovered

- **SysEx payload ≈1.5 KB** → responses paginate or stay compact (a verbose
  un-paginated `detect` response was silently dropped).
- **Controller reload is flaky** (toggle / Update MIDI scripts often doesn't
  re-read); a build marker in `ping` confirms what's actually live; full FL
  restart is the reliable reload.
- **Heavy controller loops stall FL** → keep judgement server-side.

## 7. Tools (38 total) + tests in repo
- Mixing: `fl_apply_eq_intent`, `fl_apply_reverb_intent`, `fl_apply_delay_intent`.
- Routing: `fl_get_routing`, `fl_get_routing_all`, `fl_get_channel_routing`,
  `fl_detect_cleanup_candidates`, `fl_set_route`, `fl_group_tracks`.
- Calibration: `scripts/calibrate_eq.py`, `scripts/calibrate_reverb_delay.py`,
  `scripts/probe_timings.py`.
- Tests: `test_mixing_intents.py`, `test_reverb_delay_intents.py`,
  `test_routing_read.py`, `test_route_write.py`, `test_group_tracks.py`.

## 8. Open housekeeping
- The old heavy `_h_detect_cleanup` is now **dead code** in the controller
  (replaced by server-side judgement); remove on the next controller change.
- New write tools require a **Claude Desktop restart** to register live.
