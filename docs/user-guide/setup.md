# Setup & Troubleshooting

## 1. Configure MIDI Ports

- **Windows**: Create two virtual MIDI ports in loopMIDI, named exactly `FLStudioPilot RX` and `FLStudioPilot TX`.
- **macOS**:
    1. Open the **Audio MIDI Setup** app.
    2. Choose **Window > Show MIDI Studio** (or press `Cmd+8`).
    3. Double-click the **IAC Driver** icon.
    4. Tick the **Device is online** checkbox.
    5. Under **Ports** (or **Buses**), add/rename two ports to exactly:
        - `FLStudioPilot RX`
        - `FLStudioPilot TX`
    6. Click **Apply**.

## 2. Install the Controller Script & Server

### Default Installation (.venv)
Recommended for development and AI agents.

**Windows**:

```batchfile
git clone https://github.com/thunderdew-dawn/fls-pilot
cd fls-pilot
scripts\install_windows.bat
```

**macOS**:

```shell
git clone https://github.com/thunderdew-dawn/fls-pilot
cd fls-pilot
chmod +x scripts/install_macos.sh
./scripts/install_macos.sh
```

These scripts will copy the controller script, install the server into an isolated `.venv` virtual environment, verify that the MIDI ports are online, and pre-seed the note-bridge script (`MCP_Apply.pyscript`) inside your FL Studio user data directory.

### Global CLI Installation (pipx)
If you prefer to install the server globally as a CLI application (e.g., to run `fls-pilot-daemon` without path prefixes), you can opt-in to `pipx`:

- Windows: `scripts\install_windows.bat --pipx`
- macOS: `./scripts/install_macos.sh --pipx`

If `pipx` is not installed on your system, the script will abort. You can ask the installer to attempt to install `pipx` for you by adding `--install-pipx`:
- `scripts\install_windows.bat --pipx --install-pipx`

> [!IMPORTANT]
> **macOS Accessibility Permissions**: Since the note-writing tool simulates keyboard shortcuts (`Cmd+Opt+Y`) via `pyautogui` to trigger script runs in FL Studio, the application executing the MCP server (e.g., your terminal, iTerm, Warp, or your MCP client app like Claude Desktop/ChatGPT) must be granted Accessibility permissions. Go to **System Settings > Privacy & Security > Accessibility** and ensure the app you are running is enabled.

For optional audio/melody analysis extras:
- Windows (.venv): `.venv\Scripts\pip install -e ".[audio,audio-accurate]"`
- macOS (.venv): `.venv/bin/pip install -e ".[audio,audio-accurate]"`
- Global (pipx): `pipx inject fls-pilot ".[audio,audio-accurate]"`

## 3. Configure FL Studio (All Platforms)

1. Open FL Studio.
2. Go to **Options > MIDI Settings**:
    - **Input list**: Click `FLStudioPilot RX`, tick **Enable**, set **Controller type** to `FLStudioPilot`, and set **Port** to `42`.
    - **Output list**: Click `FLStudioPilot TX`, tick **Enable**, and set **Port** to `42` (MUST match the input port).
3. Go to **View > Script output**. It should show `[FLStudioPilot] Ready`.

## 4. Run Setup Doctor

Recommended first-run path: open the local Control Center and follow its guided
setup:

- **Windows (.venv)**: `.venv\Scripts\fls-pilot-control-center --open`
- **macOS (.venv)**: `.venv/bin/fls-pilot-control-center --open`
*(If you installed via pipx, simply run `fls-pilot-control-center --open`)*

The Control Center stays read-only against the FL Studio project. It asks you to
perform manual FL Studio actions, then reruns the relevant checks. It can also
start/stop the local daemon and ChatGPT SSE server that it manages. When Python
and the core dependencies are available, Control Center attempts to start the
local daemon automatically. If the default daemon port is busy, it starts on the
recommended fallback port and updates the snippets and setup report. When it
starts the SSE server, it immediately runs an MCP connection test through the
displayed SSE URL and shows the result in Guided Setup under MCP SSE.

CLI fallback: before starting write-capable workflows, run the read-only Setup Doctor:

- **Windows (.venv)**: `.venv\Scripts\fls-pilot-doctor`
- **macOS (.venv)**: `.venv/bin/fls-pilot-doctor`
*(If you installed via pipx, simply run `fls-pilot-doctor`)*

Review `--- BLOCKERS ---` first. The Doctor reports MCP stdio/SSE transport,
TCP daemon/bridge health, MIDI ports, FL controller heartbeat, read-only ping,
and the Piano Roll `MCP_Apply` script as separate findings so one healthy layer
is not mistaken for full project readiness.

For machine-readable output:

- **Windows (.venv)**: `.venv\Scripts\fls-pilot-doctor --format json`
- **macOS (.venv)**: `.venv/bin/fls-pilot-doctor --format json`
*(If you installed via pipx, simply run `fls-pilot-doctor --format json`)*

For release validation across both MCP transports:

- **Windows (.venv)**: `.venv\Scripts\fls-pilot-doctor --all-transports`
- **macOS (.venv)**: `.venv/bin/fls-pilot-doctor --all-transports`
*(If you installed via pipx, simply run `fls-pilot-doctor --all-transports`)*

## 5. Print the Local Status Summary

Print the read-only local status data:

- **Windows (.venv)**: `.venv\Scripts\fls-pilot-status`
- **macOS (.venv)**: `.venv/bin/fls-pilot-status`
*(If you installed via pipx, simply run `fls-pilot-status`)*

The status CLI tool prints bridge/project/resource state only, clearly marks unavailable or API-limited data, and does not modify FL Studio.

Default local ports:

| Component | Default | Fallback behavior |
|---|---:|---|
| Control Center | `8766` | Uses the next available port and opens/prints the actual URL. |
| ChatGPT SSE server | `8080` | Control Center-managed SSE uses the next available port and updates snippets. |
| TCP daemon | `9787` | Control Center detects a healthy external daemon, auto-starts its own daemon when possible, or uses a fallback port. |

## 6. Connect to your MCP Client

### Option A: Claude Desktop, Cursor, or other stdio clients

1. Recommended: open Control Center first. It attempts to start the MIDI bridge
   daemon automatically after the environment checks pass.
2. Terminal fallback: start the MIDI bridge daemon manually if Control Center
   cannot manage it:
    - Windows (.venv): Run `.venv\Scripts\fls-pilot-daemon`
    - macOS (.venv): Run `.venv/bin/fls-pilot-daemon`
    *(If using pipx, run `fls-pilot-daemon`)*
3. Configure your client (e.g., Claude Desktop). Add this to your configuration file (Windows: `%APPDATA%\Claude\claude_desktop_config.json`, macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`):
    
    ```json
    {
      "mcpServers": {
        "fls-pilot": {
          "command": "/path/to/fls-pilot/.venv/bin/fls-pilot",
          "env": {
            "FLS_PILOT_TRANSPORT": "tcp"
          }
        }
      }
    }
    ```
    
    *(Note: On Windows, use `.venv\\Scripts\\fls-pilot` if using the default installation, or just `fls-pilot` if installed via pipx.)*

### Option B: ChatGPT Desktop (SSE)

ChatGPT Desktop does not support local stdio subprocesses and requires a remote/SSE connection:

Recommended: start the SSE server from the Control Center and copy the displayed
ChatGPT URL. It will reflect any fallback port selected because `8080` was busy.
Guided Setup shows the SSE MCP connection test result after the server starts.

1. Recommended: start the MIDI bridge daemon from Control Center. It will use
   the configured port or a detected fallback port.
2. Terminal fallback:
    - Windows (.venv): `.venv\Scripts\fls-pilot-daemon`
    - macOS (.venv): `.venv/bin/fls-pilot-daemon`
    *(If using pipx, run `fls-pilot-daemon`)*
3. Start the MCP server with the SSE transport in another terminal:
    - Windows (.venv): `set FLS_PILOT_TRANSPORT=tcp && .venv\Scripts\fls-pilot --sse --port 8080`
    - macOS (.venv): `export FLS_PILOT_TRANSPORT=tcp && .venv/bin/fls-pilot --sse --port 8080`
    *(If using pipx, run `fls-pilot --sse --port 8080`)*
4. Enable Developer Mode in ChatGPT Desktop (Settings > Developer).
5. Go to **Settings > Developer > MCP**, click **Add New Server**:
    - **Name**: `FL Studio`
    - **Type**: `sse`
    - **URL**: `http://localhost:8080/sse`
    - Click **Save**.

## 7. Arm the Note Bridge (Per Session)

Open the FL Studio Piano Roll, click the arrow menu (top-left), and run **MCP_Apply** once from the **File > Script** menu. This arms the note bridge for composition tools only. It is not required for read-only Mix Review, Routing Review, Project Health, or other scan/report workflows.

Verify the connection by asking your AI assistant to run `fl_transport(action="ping")`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| loopMIDI ports not found / not detected | The two ports must be named **exactly** `FLStudioPilot RX` and `FLStudioPilot TX`. Recreate them in loopMIDI and re-run the installer. |
| No `[FLStudioPilot] Ready` in FL's Script output | The controller isn't registered: set the `FLStudioPilot RX` input's **Controller type** to **FLStudioPilot** in MIDI Settings, confirm `device_FLStudioPilot.py` is in `Settings\Hardware\FLStudioPilot\`, then fully restart FL Studio. |
| The LLM assistant can't reach FL / transport ping fails | Make sure the daemon is running (`fls-pilot-daemon`); check the transport matches (`FLS_PILOT_TRANSPORT=tcp` uses the daemon, unset uses direct MIDI); restart your MCP client after editing its config. |
| Note-writing does nothing | Run `MCP_Apply` once from the piano roll's scripting menu this session - it arms the note bridge. |
| Audio tools error or are unavailable | Install the optional extras: `pip install -e ".[audio]"` (or `".[audio,audio-accurate]"`). |
