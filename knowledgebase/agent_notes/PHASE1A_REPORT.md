# flstudio-mcp — Phase 1A Report (read + write + safety)

**Version:** 0.3.0 · **Env:** FL Studio Producer Edition v25.2.5 [build 5319], MIDI scripting v40, Windows, Python 3.12, loopMIDI · **Date:** 2026-05-24

This report covers the transport/architecture state and the Phase 1A build
(project/mixer/channel read surface, mixer/channel write commands, and a
safety snapshot/rollback layer). Intended for an external review pass.

---

## 1. Architecture (v0.3) — dual transport

```
MCP client → (stdio) → MCP server → ┬─ direct: in-process FLBridge ─┐
                                     └─ tcp: TCP→ daemon ─────────────┤→ loopMIDI → FL controller → FL API
```

- **Why two transports.** The MCP server can run MIDI in-process (`FLBridge`,
  default `FLSTUDIO_MCP_TRANSPORT=direct`). But the **Microsoft Store / MSIX
  build of the MCP client launches its child MCP-server process in a context
  where the Windows MIDI subsystem delivers no input data** — the loopMIDI
  ports enumerate and open without error, but zero MIDI arrives. Proven by
  A/B: a normally-launched Python process receives every heartbeat; the
  Client-spawned one (same code, same session, same port, both
  non-AppContainer) receives nothing.
- **Fix = `TCPBridge` + a daemon.** With `FLSTUDIO_MCP_TRANSPORT=tcp`, the MCP
  server does **no MIDI** — it talks to a standalone **`fl-studio-mcp-daemon`**
  (a normal process the user runs) over `127.0.0.1:9787`; the daemon owns all
  loopMIDI I/O. TCP is unaffected by the MSIX launch context (same reason
  socket-based MCPs like AbletonMCP "just work"). This makes the bridge work
  under **every** MCP client.
- Verified end-to-end via the daemon path: **10/10 Phase-0 transport tools**
  (ping, tempo set/restore, play/stop, toggle, record arm/disarm, song
  position get/set).

### SysEx payload limit (important constraint)
Empirically probed: **~1000 B round-trips fine; ≥2000 B is dropped entirely**
(not truncated). So every response must stay well under ~1.5 KB on the wire.
All list reads therefore **paginate by payload budget** (see §3).

---

## 2. Validated against the v1.0 engineering plan
The plan's "keep verbatim" items were independently confirmed correct during
this work:
- FL 25.x routes incoming SysEx to **`OnSysEx`** (not `OnMidiMsg`) — handled.
- `fl_set_tempo` = `processRECEvent(REC_Tempo, bpm*1000, REC_UpdateValue|REC_UpdateControl)` (no `REC_FromMIDI`) — matches.
- loopMIDI RX/TX with matching FL Port numbers — correct.

---

## 3. Phase 1A — READ surface (DONE, verified)

Commands (controller) + server helper:
- `get_project_state` — tempo, transport, pattern/channel/mixer counts.
- `mixer_list_tracks` / `channel_list` — **budget-paginated**: accumulate
  entries until the page JSON would exceed ~600 B, return `next_start` (or
  null). Names truncated to 24 chars in lists (`trunc: true`); full names via
  single-gets. Server-side `fetch_all_pages()` loops `start → next_start →
  null` and concatenates.
- `mixer_get_track` / `channel_get` — single item, full untruncated name.
  Channel dict includes `solo` (so channel rollback is exact).

**Test (`scripts/test_phase1a.py`) — all pass:** project state ✅; all **18**
mixer tracks retrieved across pages ✅; all **8** channels ✅; single-gets full
names ✅. (Initial 8-per-page fixed-count version timed out on this project's
40–55-char sample names — that's what motivated the budget pagination.)

---

## 4. Phase 1A — WRITE surface + safety (BUILT; 1 item pending reload)

### Write commands (controller) + MCP tools
- mixer: `mixer_set_volume(track, value, unit)`, `_set_pan`, `_set_mute`,
  `_set_solo`, `_set_name`
- channel: `channel_set_volume(channel, value, unit)`, `_set_pan`,
  `_set_mute`, `_set_solo`
- Every write **reads back** the value FL actually accepted (FL clamps) and
  returns it — same pattern as `set_tempo`.

### Volume conversion (the silent-bug trap — handled)
FL normalized volume **0.8 = unity (0 dB), NOT 1.0** (Master reads 0.8 live).
```
db → norm:  norm = 0.8 * 10**(db/20),  clamp [0,1]
norm → db:  db   = 20 * log10(norm / 0.8)   (guard norm>0)
```
**Explicitly asserted in the test:** set track 1 to −6 dB →
expected `0.8*10**(-6/20) = 0.4009`, **actual = 0.4009** (within 0.001). ✅
A 1.0-unity bug would have given 0.5012 — it did not.

### Safety layer (`src/fl_studio_mcp/safety.py`, server-side)
- `safe_write()` = **snapshot → log → execute → read back**, returns
  `{before, after}`. Honors dry-run.
- `take_snapshot(scope)` — `mixer_track:N` / `channel:N` / `mixer_all` /
  `channels_all`.
- `rollback_last_change()` — pops the last changelog entry and replays its
  pre-change `restore` action.
- `set_dry_run(enabled)` — writes return `{planned}` only, no FL change.
- Changelog = rolling `deque(50)`, persisted to
  `~/.flstudio-mcp/changelog.jsonl`.
- MCP tools wired: read (`fl_get_project_state`, `fl_get_mixer_state`,
  `fl_get_channel_state`), write (`fl_set_mixer_*`, `fl_set_channel_*`), safety
  (`fl_take_snapshot`, `fl_rollback_last_change`, `fl_set_dry_run`).

### Test results (`scripts/test_phase1a_write.py`)
| Check | Result |
|---|---|
| dB conversion (−6 dB → 0.4009, 0.8-unity) | ✅ |
| volume rollback → baseline 0.6205 | ✅ |
| pan +0.5 set + rollback → 0.0 | ✅ |
| dry-run returns planned-only, FL unchanged | ✅ |
| **mute / solo (both directions)** | ✅ (clean False→True→False proof) |

**The mute saga (RESOLVED).** Three findings, in order:
1. Bare `mixer.muteTrack(index)` **toggles correctly — one op per script-tick**.
2. The explicit-value form `mixer.muteTrack(index, 1)` does **NOT** mute on this
   build (only `,0` reliably unmutes). An early "fix" using it silently failed,
   and a test passed only because the track happened to already be muted.
3. FL **coalesces multiple mute ops within one script execution** — a one-line
   interpreter test with four toggles registered only the first.

**Final fix:** read-then-**bare-toggle** in the handler. Each MCP command is a
separate SysEx = a separate FL script-tick = exactly one toggle, so it lands.
Verified clean `False→True→False→True→False` on a fresh track via the command
path (mixer + channel mute & solo).

---

## 5. Open items / notes
- **Field naming — DONE:** every volume-bearing response (reads + writes,
  mixer + channel) now returns `vol_norm` (0..1) and `vol_db` (dB, 0.8=unity).
  The old inconsistent `vol`/`norm`/`db` keys are gone.
- **Channel-solo in snapshot:** added `solo` to the channel read dict so
  channel-solo rollback is exact (parity with mixer).
- **Recurring MIDI gotcha:** an FL restart **or a MIDI device hot-plug/unplug**
  re-enables `FLStudioMCP RX` as an *output* at Port 42, recreating a duplicate
  output on the controller's port. `device.midiOutSysex` then routes heartbeats
  to RX instead of TX and the bridge sees nothing (`alive:false`). Workaround:
  keep `FLStudioMCP RX` output disabled. **Permanent fix (recommended):** give
  the RX output a *different* Port number (e.g. 43) so it can never collide.
- **Daemon lifecycle:** for distribution, the daemon must auto-start (Windows
  Startup / tray) so non-technical users don't run it manually. Not yet built.
- **Out of scope (per plan):** plugin-param control (Phase 1B; needs a
  per-machine discovery scan), piano-roll note authorship (Phase 2; pyscript +
  job-file bridge), music-intelligence engine (Phase 3).

## 6. Tests in repo
- `scripts/test_bridge.py` — Phase 0, all 10 transport tools.
- `scripts/test_phase1a.py` — read surface (project/mixer/channel, pagination).
- `scripts/test_phase1a_write.py` — write + safety (dB assertion, rollback,
  dry-run).

## 7. Review questions (suggested)
1. Is the budget-pagination + name-truncation approach acceptable, or should we
   move to a chunked-SysEx protocol for large reads now rather than later?
2. `vol` vs `norm` naming — unify now or after Phase 1B?
3. Safety/rollback model — is per-change `restore`-action replay sufficient, or
   do we want full project snapshots before bulk operations?
4. Daemon auto-start strategy for end-user distribution.
