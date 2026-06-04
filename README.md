# flstudio-mcp

**Control FL Studio with any MCP-compatible LLM: AI mixing, composition, and mix diagnosis through natural language.**

![version](https://img.shields.io/badge/version-1.1.0-blue)
![status](https://img.shields.io/badge/status-stable-green)
![license](https://img.shields.io/badge/license-MIT-green)
![python](https://img.shields.io/badge/python-3.10+-blue)
![Windows](https://img.shields.io/badge/Windows-0078D6?style=flat&logo=windows&logoColor=white)
![macOS](https://img.shields.io/badge/macOS-000000?style=flat&logo=apple&logoColor=white)
![FL Studio](https://img.shields.io/badge/FL%20Studio-2025%2B-orange)

![The LLM assistant diagnosing and fixing a mix in FL Studio](docs/demo.gif)

*The LLM assistant diagnosing and fixing a mix in FL Studio through natural language.*

## Overview

flstudio-mcp is a Model Context Protocol (MCP) server that lets any MCP client (like Claude Desktop, ChatGPT, or Cursor) drive FL Studio 2025 directly — the mixer, plugins, piano roll, routing, and project — from plain-language requests. Ask for a mix diagnosis, a vocal chain, a chord progression in a particular scale, or a full arrangement, and the LLM assistant carries it out through FL's scripting API and a set of calibrated, safety-checked tools.

It is genre- and producer-agnostic: nothing about it assumes a particular style of music.

## Maintained fork

This repository is a materially extended fork of
[`rosasynthesiz/flstudio-mcp`](https://github.com/rosasynthesiz/flstudio-mcp),
now maintained at
[`thunderdew-dawn/flstudio-mcp`](https://github.com/thunderdew-dawn/flstudio-mcp).
The project keeps the `fl-studio-mcp` package and command names for
compatibility, while the fork's engineering direction is now explicit:
rollback-first FL Studio production tooling, documented API-evidence handling,
live-probe discipline for build-dependent behavior, macOS support, CI safety
audits, prompt evals, and a committed agent workflow guide.

See [`NOTICE.md`](NOTICE.md) for provenance and attribution.

## Quickstart

```bat
scripts\install_windows.bat        :: Windows: controller + server + note bridge
fl-studio-mcp-daemon               :: start the bridge, keep it running
```

```bash
./scripts/install_macos.sh         # macOS: controller + server + note bridge
.venv/bin/fl-studio-mcp-daemon     # start the bridge, keep it running
```

Wire the two loopMIDI ports in FL (Options > MIDI Settings), arm `MCP_Apply` once in the piano roll, then ask the LLM assistant in plain language:

> "Scan my mix and tell me what's wrong." — "Set up a vocal chain from my plugins." — "Export this arrangement to MIDI."

Full setup is below.

## Capabilities

### Mixing & diagnosis
- **Mix Doctor** — scans the whole mix and reports concrete problems (clipping, low headroom, level imbalance, missing high-pass, ungrouped related tracks, overlapping EQ boosts), each with the exact evidence and a proposed fix. Fixes are applied one at a time, only on approval, through a snapshot → write → readback → rollback safety layer. Master clipping is resolved by trimming the contributing source tracks rather than pulling the master.
- **Knowledgebase & Safe Wrappers** — machine-readable calibration logic prevents destructive API calls. Normalized values, DB/Hz limits, and specific EQ mappings are verified against a live-updated JSON knowledgebase, eliminating hallucinated parameter values from the LLM assistant.
- **Full-song peak watch** — holds a running peak per track across playback, so level decisions are based on the loudest moment of the actual song, not a single instant.
- **Calibrated processing intents** — musical EQ, compression, reverb, and delay moves mapped to real plugin parameters (native and third-party), each applied as one reversible change.
- **Level-aware compression** — sets thresholds relative to a track's measured level during playback.
- **Gain staging** — proposes per-track trims toward a healthy level with proper master headroom.
- **Reference match** — compares your mix's level and tonal balance against a reference track.
- **Bulk track control** — solo or mute a whole group (drums, vocals, …) in one step, with a one-call reset.
- **Track & channel coloring** — color a track, a channel, or a whole group (drums, vocals, …) by color name or hex, reversible like every other change.

### Plugin & preset control
- Read and set plugin parameters by name, on native and third-party plugins (the parameter list is resolved live).
- **Chain suggestions** and **preset recommendations** drawn from your actual installed library — read directly from FL's plugin database and preset folders on disk, so recommendations are limited to what you own.

### Composition
- **Multi-track MIDI export** — generate a complete arrangement as a standard MIDI file to import.
- **Multi-pattern arrangement** — create, name, clone, and mark sections.
- **Note and chord writing** into the piano roll, with quantize to a grid (for new notes and existing ones).
- **Composition in any scale or mode** — Western modes, pentatonic, ragas, maqam, and beyond — through the scale composer, where the LLM assistant supplies the notes for the requested scale.

### Audio analysis
- Tempo and key estimation from an audio file.
- Melody-to-MIDI transcription (CREPE pitch tracking, with a lighter fallback).

The server exposes 138 tools across the production, mixing, composition, safety,
and project-organization surface, plus 6 live resources (project, mixer,
transport, channels, patterns, status) that the LLM assistant can read directly.
For a user-facing value overview, workflow examples, and the full tool catalog,
see [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md).

## What sets it apart

flstudio-mcp is built as a mixing and production assistant, not only a note sender. It diagnoses and repairs a whole mix, makes decisions from real measured levels rather than guesswork, and is aware of your actual plugin and preset library when it makes suggestions. Every change that touches the project is shown before it is applied, logged, and reversible.

## Limitations

These are properties of FL Studio's scripting API, stated plainly:

- **Plugins, audio files, and rendering are UI-only.** FL's API cannot load a plugin, load an audio file, or render audio. The plugin and preset tools therefore *suggest* — you load the chosen plugin or preset, and the LLM assistant then configures it. Audio export is done manually (File > Export); the LLM assistant can analyze the rendered file afterward.
- **Note writing is armed once per session.** A generated pyscript writes notes into the piano roll; FL exposes no API to run a pyscript, so you run "MCP_Apply" once from the piano roll's scripting menu at the start of a session.
- **Micro-tonal and gamaka-heavy music is approximated.** Scales with intervals smaller than a semitone (e.g. Arabic maqam) are rounded to the nearest semitone, and traditions built on gamaka/ornamentation (e.g. Carnatic) get the *scale framework* — the correct swaras and intervals — not gamaka or micro-tonal rendering. That's a limit of 12-tone MIDI, not of the tools.

## Requirements

- **Windows 10/11** (tested on Windows 11) or **macOS 12+** (Intel & Apple Silicon)
- **Known-working FL Studio build:** Producer Edition v25.2.5, build 5055,
  with controller build marker `channels-v38`.
  FL Studio 20.7+ has the required MIDI scripting foundation, but individual
  API behavior can be build-dependent; use `fl_ping` and the live smoke/probe
  scripts before relying on a new FL build for writes.
- **Claude Desktop** or **ChatGPT Desktop** (or any MCP client)
- **Python 3.10+**
- Virtual MIDI ports:
  - **loopMIDI** on Windows ([download](https://www.tobias-erichsen.de/software/loopmidi.html))
  - **IAC Driver** (built into macOS)
- Optional: **ffmpeg** on PATH (for MP3 analysis)

## Setup

### 1. Configure MIDI Ports

* **Windows**: Create two virtual MIDI ports in loopMIDI, named exactly `FLStudioMCP RX` and `FLStudioMCP TX`.
* **macOS**:
  1. Open the **Audio MIDI Setup** app.
  2. Choose **Window > Show MIDI Studio** (or press `Cmd+8`).
  3. Double-click the **IAC Driver** icon.
  4. Tick the **Device is online** checkbox.
  5. Under **Ports** (or **Buses**), add/rename two ports to exactly:
     * `FLStudioMCP RX`
     * `FLStudioMCP TX`
  6. Click **Apply**.

### 2. Install the Controller Script & Server

#### Windows:
```bat
git clone https://github.com/thunderdew-dawn/flstudio-mcp
cd flstudio-mcp
scripts\install_windows.bat
```

#### macOS:
```bash
git clone https://github.com/thunderdew-dawn/flstudio-mcp
cd flstudio-mcp
chmod +x scripts/install_macos.sh
./scripts/install_macos.sh
```
This script will copy the controller script, create a virtual environment (`.venv`), install the server inside it, and verify that the IAC Driver ports are online. It also pre-seeds the note-bridge script (`MCP_Apply.pyscript`) inside your FL Studio user data directory.

> [!IMPORTANT]
> **macOS Accessibility Permissions**: Since the note-writing tool simulates keyboard shortcuts (`Cmd+Opt+Y`) via `pyautogui` to trigger script runs in FL Studio, the application executing the MCP server (e.g., your terminal, iTerm, Warp, or your MCP client app like Claude Desktop/ChatGPT) must be granted Accessibility permissions. Go to **System Settings > Privacy & Security > Accessibility** and ensure the app you are running is enabled.

For optional audio/melody analysis extras:
* Windows: `pip install -e ".[audio,audio-accurate]"`
* macOS: `.venv/bin/pip install -e ".[audio,audio-accurate]"`

### 3. Configure FL Studio (All Platforms)

1. Open FL Studio.
2. Go to **Options > MIDI Settings**:
   * **Input list**: Click `FLStudioMCP RX`, tick **Enable**, set **Controller type** to `FLStudioMCP`, and set **Port** to `42`.
   * **Output list**: Click `FLStudioMCP TX`, tick **Enable**, and set **Port** to `42` (MUST match the input port).
3. Go to **View > Script output**. It should show `[FLStudioMCP] Ready`.

### 4. Connect to your MCP Client

#### Option A: Claude Desktop, Cursor, or other stdio clients
1. Start the MIDI bridge daemon (recommended so MIDI ports are held by a stable background process):
   * Windows: Run `fl-studio-mcp-daemon`
   * macOS: Run `.venv/bin/fl-studio-mcp-daemon`
2. Configure your client (e.g., Claude Desktop). Add this to your configuration file (Windows: `%APPDATA%\Claude\claude_desktop_config.json`, macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`):
   ```json
   {
     "mcpServers": {
       "fl-studio": {
         "command": "/path/to/flstudio-mcp/.venv/bin/fl-studio-mcp",
         "env": {
           "FLSTUDIO_MCP_TRANSPORT": "tcp"
         }
       }
     }
   }
   ```
   *(Note: On Windows, use `fl-studio-mcp` for the command instead of the `.venv` path if installed globally.)*

#### Option B: ChatGPT Desktop (SSE)
ChatGPT Desktop does not support local stdio subprocesses and requires a remote/SSE connection:
1. Start the MIDI bridge daemon in a terminal:
   * Windows: `fl-studio-mcp-daemon`
   * macOS: `.venv/bin/fl-studio-mcp-daemon`
2. Start the MCP server with the SSE transport in another terminal:
   * Windows: `set FLSTUDIO_MCP_TRANSPORT=tcp && fl-studio-mcp --sse --port 8080`
   * macOS: `export FLSTUDIO_MCP_TRANSPORT=tcp && .venv/bin/fl-studio-mcp --sse --port 8080`
3. Enable Developer Mode in ChatGPT Desktop (Settings > Developer).
4. Go to **Settings > Developer > MCP**, click **Add New Server**:
   * **Name**: `FL Studio`
   * **Type**: `sse`
   * **URL**: `http://localhost:8080/sse`
   * Click **Save**.

### 5. Arm the Note Bridge (Per Session)

Open the FL Studio Piano Roll, click the arrow menu (top-left), and run **MCP_Apply** once from the **File > Script** menu. This arms the note bridge for composition tools.

Verify the connection by asking your AI assistant to run `fl_ping`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| loopMIDI ports not found / not detected | The two ports must be named **exactly** `FLStudioMCP RX` and `FLStudioMCP TX`. Recreate them in loopMIDI and re-run the installer. |
| No `[FLStudioMCP] Ready` in FL's Script output | The controller isn't registered: set the `FLStudioMCP RX` input's **Controller type** to **FLStudioMCP** in MIDI Settings, confirm `device_FLStudioMCP.py` is in `Settings\Hardware\FLStudioMCP\`, then fully restart FL Studio. |
| The LLM assistant can't reach FL / `fl_ping` fails | Make sure the daemon is running (`fl-studio-mcp-daemon`); check the transport matches (`FLSTUDIO_MCP_TRANSPORT=tcp` uses the daemon, unset uses direct MIDI); restart your MCP client after editing its config. |
| Note-writing does nothing | Run `MCP_Apply` once from the piano roll's scripting menu this session — it arms the note bridge. |
| Audio tools error or are unavailable | Install the optional extras: `pip install -e ".[audio]"` (or `".[audio,audio-accurate]"`). |

## Usage examples

Plain-language prompts:

- "Scan my mix and tell me what's wrong."
- "Set up a vocal chain on the lead vocal using my plugins."
- "Suggest a vintage bass preset from my Serum library."
- "Compose an 8-bar melody in D Dorian and write it to the selected channel."
- "Export this arrangement to a MIDI file."
- "What tempo and key is this track?" (on an audio file)

For examples by module, assistant, and diagnostic check, see the
[`User Guide`](docs/USER_GUIDE.md).

## Architecture

A thin controller script runs inside FL Studio and returns only cheap, raw data; all judgement — diagnosis, calibration, planning — happens server-side. A standalone daemon owns the MIDI port so the server works regardless of how the MCP client is launched. Note authoring uses a generated pyscript bridge: the daemon re-triggers the armed `MCP_Apply` script with a keystroke (via pyautogui) after a brief window force-focus. Every project-modifying tool routes through a snapshot → write → readback → rollback safety layer backed by a persisted change log.

Design notes and findings are in [`docs/`](docs/).

## License

MIT — see [LICENSE](LICENSE).

## Status & contributing

Beta — the public 1.1 release. Fully compatible with Windows and macOS.
Issues and pull requests:
[github.com/thunderdew-dawn/flstudio-mcp](https://github.com/thunderdew-dawn/flstudio-mcp).

<!-- mcp-name: io.github.thunderdew-dawn/flstudio-mcp -->
