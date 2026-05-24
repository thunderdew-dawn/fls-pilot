# Roadmap

> **Transport note (v0.2):** the FL <-> server channel is MIDI SysEx, not a
> file queue. See [`docs/architecture.md`](docs/architecture.md) and
> [`docs/CHANGELOG.md`](docs/CHANGELOG.md). The tool surface is unchanged;
> phase work continues on top of the new transport.

Tracking the full Production scope — eight phases shipping the MCP server,
the Tamil cinema preset packs, the SKILL.md, evals, and the Claude Code
plugin marketplace bundle.

Each phase is shippable on its own. Each ends with `python scripts/test_bridge.py`
still passing.

## Phase 0 — Foundation (shipping)

Goal: prove the file-queue bridge works end-to-end and ship the absolute
minimum tool surface.

- [x] File-queue protocol (commands, responses, heartbeat, atomic writes).
- [x] FL controller script with `OnIdle` polling and dispatch table.
- [x] FastMCP server skeleton with stdio transport.
- [x] Transport tools: ping, tempo get/set, play, stop, toggle, record,
      play-state, song-position get/set. **10 tools total.**
- [x] `scripts/test_bridge.py` standalone harness.
- [x] Install scripts for Windows and macOS.

## Phase 1 — Channel rack (~12 tools)

The channel rack is where most users place samples and instruments.

- `fl_channel_list` — Names, types, colors, current pattern.
- `fl_channel_get` — Volume, pan, mute, solo, target mixer track.
- `fl_channel_set_volume`, `_pan`, `_mute`, `_solo`.
- `fl_channel_select` — Make a channel active.
- `fl_channel_get_grid` — Read the step-sequencer grid for the current pattern.
- `fl_channel_set_grid_bit` — Write a single step. (This is how we draw drum
  patterns without needing the Piano Roll pyscript.)
- `fl_channel_clear_grid` — Wipe steps for a channel in the current pattern.
- `fl_channel_get_color`, `_set_color` — Visual organization.

Risk: FL's channel API uses `channels.channelNumber()` and `channels.selectedChannel()`
for the active channel. Some functions need the explicit index; some use the
selection. The script normalizes to explicit indices.

## Phase 2 — Mixer (~10 tools)

- `fl_mixer_list_tracks` — Up to 125 tracks plus Master at index 0.
- `fl_mixer_get_track` — Name, volume, pan, mute, solo, dock side, color.
- `fl_mixer_set_volume`, `_set_pan`, `_set_mute`, `_set_solo`.
- `fl_mixer_select_track` — Drive UI focus.
- `fl_mixer_get_route` — Where this track's audio is sent.
- `fl_mixer_set_route` — Add/remove a route to another track.
- `fl_mixer_get_levels` — Peak meter sample (read via `OnUpdateMeters`).

Risk: `setTrackVolume` takes a normalized float 0.0–1.0 where 0.8 is unity
gain, not 1.0. The tools accept dB and convert.

## Phase 3 — Patterns + playlist (~6 tools)

- `fl_pattern_list` — Names, lengths, colors.
- `fl_pattern_select`, `_rename`.
- `fl_pattern_get_length` (in steps and beats).
- `fl_playlist_get_tracks` — Playlist track names and visibility.
- `fl_playlist_get_markers` — Time-line markers (used by Carnatic preset pack
  to insert raga section markers).

API limits worth surfacing in tool docs:
- New patterns cannot be created from scratch. Cloning happens via the Piano
  Roll pyscript by selecting all and stamping into a new pattern slot.

## Phase 4 — Piano Roll pyscript (~6 tools)

This is the most invasive phase — adds the second script type.

- `fl_piano_write_notes` — Note batch into the active pattern's Piano Roll.
- `fl_piano_write_chord` — Helper that builds a chord by name (`Cmaj7`,
  `Bbm9`) and writes it.
- `fl_piano_clear` — Wipe the active pattern.
- `fl_piano_quantize` — Snap selected notes.
- `fl_piano_transpose` — Shift in semitones.
- `fl_piano_get_notes` — Read back what is in the active pattern.

Mechanics:
1. MCP server writes the job to `bridge/piano_roll/pending.json`.
2. MCP server triggers a hotkey (`Ctrl+Alt+Y` on Windows, `Cmd+Alt+Y` on
   macOS) via `pyautogui`. This is the only place we touch the keyboard.
3. The `.pyscript` reads the JSON, writes the notes, writes `done.json`.
4. MCP server polls `done.json`.

The keyboard trigger is the only fragile bit. We require FL Studio to be the
focused window for piano-roll writes. The server detects focus loss and
returns a clear error rather than guessing.

## Phase 5 — Plugin params (~5 tools)

- `fl_plugin_list_params` — Parameter index, name, current value, value range.
- `fl_plugin_get_param`, `_set_param`.
- `fl_plugin_get_preset_name`, `_select_preset_index`.

This is intentionally scoped tight. Per-VST parameter naming is a mess across
plugins; we expose the raw FL view and let the LLM map names.

## Phase 6 — Carnatic + kuthu presets (~8 tools)

Where the Tamil cinema differentiator lives.

- `fl_preset_list_ragas` — All 72 melakarta ragas plus the common janyas
  (Bhairavi, Mohanam, Kalyani, etc) with ascending/descending notes.
- `fl_preset_get_raga_scale` — Returns the swara → MIDI mapping at a given
  base note.
- `fl_preset_write_raga_melody` — Generate a melody fragment in a chosen
  raga with mood (`devotional`, `cinematic`, `kuthu-energetic`,
  `melancholic`). Calls `fl_piano_write_notes` under the hood.
- `fl_preset_list_kuthu_patterns` — Kuthu / gaana / chenda templates with
  per-instrument rolls (tavil, parai, kanjira, dholak).
- `fl_preset_write_kuthu_pattern` — Stamp a kuthu pattern across a chosen set
  of channels in the active channel rack.
- `fl_preset_chord_progression` — Common Tamil-film progressions in any key.
- `fl_preset_get_tempo_for_mood` — Suggests BPM bands for moods used in
  Tamil film scoring.

The data files live in `src/fl_studio_mcp/presets/` as plain Python modules
so they ship inside the wheel.

## Phase 7 — Polish & ship

- [ ] `skills/flstudio-production/SKILL.md` orchestration layer with deep
      content in `references/`. Under 500 lines.
- [ ] `evals/evals.json` — 10 questions exercising the full tool surface.
- [ ] `.claude-plugin/marketplace.json` so this can live in
      `paper-kasu-skills` as an installable plugin.
- [ ] `AGENTS.md` describing the agentic workflow for future Claude sessions
      working on this codebase.
- [ ] Demo video and screenshots in `docs/`.
- [ ] GitHub Actions for linting and the standalone bridge tests (mock FL).
- [ ] Pin a known-working FL Studio version range in README.

## Out of scope (intentionally)

- Loading new VST instances — FL API does not allow this.
- Creating new patterns ex nihilo — same limitation.
- Audio recording control beyond the record-arm toggle.
- Multiple FL Studio instances on one machine. The bridge supports it via
  `FLSTUDIO_MCP_BRIDGE` but we don't ship that wiring.
