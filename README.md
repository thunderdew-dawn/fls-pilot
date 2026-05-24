# FL Studio MCP

An MCP (Model Context Protocol) server that lets Claude, Cursor, and any
other MCP client control FL Studio through its built-in Python scripting API.

Transport: **MIDI SysEx** over a pair of virtual MIDI ports. Commands go
server -> FL on port A; responses + heartbeats come back FL -> server on
port B. We landed on MIDI after confirming that FL's controller-script
Python sandbox blocks every form of file write (open(), os.open,
os.makedirs all raise SystemError on FL 24+, MIDI scripting v40).

## Status

v0.2.0 -- Phase 0 (transport tools) shipping over the MIDI bridge. The full
roadmap is in [`ROADMAP.md`](ROADMAP.md). See
[`docs/CHANGELOG.md`](docs/CHANGELOG.md) for the v0.1 -> v0.2 history.

| Phase | Surface | Tools | Status |
|-------|---------|-------|--------|
| 0 | Transport + tempo + ping | 10 | shipping (v0.2.0) |
| 1 | Channel rack | ~12 | next |
| 2 | Mixer | ~10 | planned |
| 3 | Patterns + playlist | ~6 | planned |
| 4 | Piano Roll pyscript | ~6 | planned |
| 5 | Plugin params | ~5 | planned |
| 6 | Carnatic + kuthu presets | ~8 | planned |
| 7 | Polish, evals, skill, repo | -- | planned |

## Requirements

- FL Studio 20.7 or newer.
- Python 3.10+ for the MCP server side.
- Windows: **loopMIDI** (free, from
  https://www.tobias-erichsen.de/software/loopmidi.html).
  macOS: the built-in **IAC Driver** (Audio MIDI Setup).
  Linux: `snd-virmidi` kernel module.

## Install

### 1. Create the virtual MIDI ports

**Windows (loopMIDI):**

1. Install loopMIDI.
2. Open loopMIDI. In the "New port-name" field create exactly:
   - `FLStudioMCP RX` and click `+`
   - `FLStudioMCP TX` and click `+`
3. Leave loopMIDI running (it minimises to tray).

**macOS (IAC Driver):**

1. Open `Audio MIDI Setup` -> `Window` -> `Show MIDI Studio`.
2. Double-click `IAC Driver`. Tick `Device is online`.
3. Under `Ports`, add two ports named exactly `FLStudioMCP RX` and
   `FLStudioMCP TX`. Apply.

### 2. Install the controller script and the MCP server

```bat
:: Windows
.\scripts\install_windows.bat
```

```bash
# macOS
./scripts/install_macos.sh
```

The installer copies `device_FLStudioMCP.py` into
`Documents/Image-Line/FL Studio/Settings/Hardware/FLStudioMCP/`, then
`pip install -e .` for the server.

### 3. Wire the ports into FL Studio

1. Open FL Studio.
2. **Options -> MIDI Settings**.
3. In the **Input** list, click `FLStudioMCP RX`. Tick `Enable`. Set
   **Controller type** to `FLStudioMCP`. Set **Port** to any number,
   e.g. **42**.
4. In the **Output** list, click `FLStudioMCP TX`. Tick `Send master sync`
   off (we don't need it). Set **Port** to the **same number** (42).
5. The matching port number is how the controller script's
   `device.midiOutSysex(...)` calls find the right output. If they don't
   match, FL won't be able to respond and heartbeats will never reach the
   server.
6. Open **View -> Script output**. You should see
   `[FLStudioMCP] Ready. FL <version>, protocol v2.`

### 4. Verify the bridge works

```bash
python scripts/test_bridge.py
```

Expected:

```
Heartbeat age: 0.12

  ping ............................................ ok
        {'fl_version': '21.2.3', 'protocol_version': 2, 'ts': ...}
  get_tempo ....................................... ok
        {'bpm': 130.0, 'raw': 130000}
  set_tempo to 135.0 .............................. ok
  ...
  All checks passed.
```

If `ping` fails with "FL Studio did not respond", see
[Troubleshooting](#troubleshooting).

### 5. Wire it into Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` on
macOS, or `%APPDATA%\Claude\claude_desktop_config.json` on Windows:

```json
{
  "mcpServers": {
    "fl-studio": {
      "command": "fl-studio-mcp"
    }
  }
}
```

If `fl-studio-mcp` is not on your PATH, use the venv binary path
explicitly, or use `python -m fl_studio_mcp.server`.

Quit Claude Desktop fully (tray icon -> Quit) and reopen. Try:
*"Use fl_ping to check FL Studio. Then set the tempo to 128 and start playback."*

## Phase 0 tools

| Tool | Description |
|---|---|
| `fl_ping` | Confirms FL Studio is open and the controller is loaded. Call first when something seems off. |
| `fl_get_tempo` | Returns current project tempo in BPM. |
| `fl_set_tempo` | Sets project tempo (10-999 BPM). |
| `fl_play` | Start playback. Idempotent. |
| `fl_stop` | Stop playback. Idempotent. |
| `fl_toggle_play` | Spacebar behaviour. |
| `fl_record` | Toggle record-arm. |
| `fl_get_play_state` | Returns `{playing, recording}`. |
| `fl_get_song_position` | Returns position in ms, ticks, and beats. |
| `fl_set_song_position` | Move the playhead. Accepts `ms`, `beats`, or `ticks`. |

## Limits to know about

These are FL Studio API limits, not server bugs.

- **Cannot load new plugins.** You can change parameters on plugins already
  in the project; you cannot programmatically add a Massive X to channel 4.
- **Cannot create new patterns from scratch.** You can rename and select
  existing patterns, and (in a later phase) clone via the Piano Roll
  pyscript.
- **Cannot write files from the controller script.** FL's controller-script
  sandbox blocks file I/O. That's why this server uses MIDI SysEx instead
  of a JSON file queue.
- **Tempo writes can be rejected** if FL is showing a modal dialog. The
  server reads back the post-write value into the response.

## Troubleshooting

**`fl_ping` returns `alive: false, reason: No heartbeat received`.** One of:

1. FL Studio is closed. Open it.
2. `FLStudioMCP RX` is not enabled in MIDI Settings Input list, or
   Controller type is not set to FLStudioMCP. Re-pick it.
3. `FLStudioMCP TX` is not enabled in the Output list, or its Port number
   does not match the Input port number. Match them.
4. The loopMIDI port names on your machine differ from the defaults. Run
   `fl-studio-mcp --list-ports` to see what Python actually sees, then set
   `FLSTUDIO_MCP_PORT_TO_FL` and `FLSTUDIO_MCP_PORT_FROM_FL` env vars.

**`FLPortMissing: No OUTPUT MIDI port matching ...`.** loopMIDI isn't
running, the port doesn't exist, or the name doesn't match. Open loopMIDI;
the ports should be in the list. Run `fl-studio-mcp --list-ports` to see
what Python sees.

**Set-tempo "succeeds" but tempo did not change.** FL Studio may have been
showing a modal dialog. The server reads back the post-write value into the
response so the mismatch is visible.

**`[FLStudioMCP] WARNING: device.midiOutSysex not available` in FL Script
output.** Very old FL build. v0.2 needs FL 20.7+ for SysEx-out support.

## Layout

```
flstudio-mcp/
├── fl_controller/FLStudioMCP/      Runs INSIDE FL Studio.
│   └── device_FLStudioMCP.py
├── fl_pyscripts/                   Piano Roll trigger scripts (Phase 4).
├── src/fl_studio_mcp/              The MCP server itself.
│   ├── server.py                   FastMCP entry point + --list-ports.
│   ├── connection.py               mido SysEx bridge client.
│   ├── protocol.py                 Wire format + command names.
│   └── tools/
│       └── transport.py            Phase 0 transport tools.
├── scripts/
│   ├── install_windows.bat
│   ├── install_macos.sh
│   └── test_bridge.py              Standalone bridge tester.
├── skills/flstudio-production/     SKILL.md for Claude (Phase 7).
├── docs/
│   ├── architecture.md             Why MIDI, not files.
│   └── CHANGELOG.md
├── evals/                          Eval suite (Phase 7).
├── pyproject.toml
├── ROADMAP.md
└── README.md
```

## License

MIT -- see [LICENSE](LICENSE).
