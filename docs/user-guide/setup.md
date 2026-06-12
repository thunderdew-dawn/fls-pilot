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

### Windows

```batchfile
git clone https://github.com/thunderdew-dawn/fls-pilot
cd fls-pilot
scripts\install_windows.bat
```

### macOS

```shell
git clone https://github.com/thunderdew-dawn/fls-pilot
cd fls-pilot
chmod +x scripts/install_macos.sh
./scripts/install_macos.sh
```

This script will copy the controller script, create a virtual environment (`.venv`), install the server inside it, and verify that the IAC Driver ports are online. It also pre-seeds the note-bridge script (`MCP_Apply.pyscript`) inside your FL Studio user data directory.

> [!IMPORTANT]
> **macOS Accessibility Permissions**: Since the note-writing tool simulates keyboard shortcuts (`Cmd+Opt+Y`) via `pyautogui` to trigger script runs in FL Studio, the application executing the MCP server (e.g., your terminal, iTerm, Warp, or your MCP client app like Claude Desktop/ChatGPT) must be granted Accessibility permissions. Go to **System Settings > Privacy & Security > Accessibility** and ensure the app you are running is enabled.

For optional audio/melody analysis extras:
- Windows: `pip install -e ".[audio,audio-accurate]"`
- macOS: `.venv/bin/pip install -e ".[audio,audio-accurate]"`

## 3. Configure FL Studio (All Platforms)

1. Open FL Studio.
2. Go to **Options > MIDI Settings**:
    - **Input list**: Click `FLStudioPilot RX`, tick **Enable**, set **Controller type** to `FLStudioPilot`, and set **Port** to `42`.
    - **Output list**: Click `FLStudioPilot TX`, tick **Enable**, and set **Port** to `42` (MUST match the input port).
3. Go to **View > Script output**. It should show `[FLStudioPilot] Ready`.

## 4. Run Setup Doctor

Before starting write-capable workflows, run the read-only Setup Doctor:

```shell
fls-pilot-doctor
```

Review `--- BLOCKERS ---` first. The Doctor reports MCP stdio/SSE transport,
TCP daemon/bridge health, MIDI ports, FL controller heartbeat, read-only ping,
and the Piano Roll `MCP_Apply` script as separate findings so one healthy layer
is not mistaken for full project readiness.

For machine-readable output:

```shell
fls-pilot-doctor --format json
```

For release validation across both MCP transports:

```shell
fls-pilot-doctor --all-transports
```

## 5. Open the Local Dashboard

Export the read-only local dashboard:

```shell
fls-pilot-dashboard
```

The dashboard uses existing read-only bridge and resource reads. It separates
live bridge data from unavailable or API-limited signals and never applies FL
Studio project changes. To serve it locally and open a browser:

```shell
fls-pilot-dashboard --serve --open
```

## 6. Connect to your MCP Client

### Option A: Claude Desktop, Cursor, or other stdio clients

1. Start the MIDI bridge daemon (recommended so MIDI ports are held by a stable background process):
    - Windows: Run `fls-pilot-daemon`
    - macOS: Run `.venv/bin/fls-pilot-daemon`
2. Configure your client (e.g., Claude Desktop). Add this to your configuration file (Windows: `%APPDATA%\Claude\claude_desktop_config.json`, macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`):
    
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
    
    *(Note: On Windows, use `fls-pilot` for the command instead of the `.venv` path if installed globally.)*

### Option B: ChatGPT Desktop (SSE)

ChatGPT Desktop does not support local stdio subprocesses and requires a remote/SSE connection:

1. Start the MIDI bridge daemon in a terminal:
    - Windows: `fls-pilot-daemon`
    - macOS: `.venv/bin/fls-pilot-daemon`
2. Start the MCP server with the SSE transport in another terminal:
    - Windows: `set FLS_PILOT_TRANSPORT=tcp && fls-pilot --sse --port 8080`
    - macOS: `export FLS_PILOT_TRANSPORT=tcp && .venv/bin/fls-pilot --sse --port 8080`
3. Enable Developer Mode in ChatGPT Desktop (Settings > Developer).
4. Go to **Settings > Developer > MCP**, click **Add New Server**:
    - **Name**: `FL Studio`
    - **Type**: `sse`
    - **URL**: `http://localhost:8080/sse`
    - Click **Save**.

## 7. Arm the Note Bridge (Per Session)

Open the FL Studio Piano Roll, click the arrow menu (top-left), and run **MCP_Apply** once from the **File > Script** menu. This arms the note bridge for composition tools.

Verify the connection by asking your AI assistant to run `fl_transport(action="ping")`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| loopMIDI ports not found / not detected | The two ports must be named **exactly** `FLStudioPilot RX` and `FLStudioPilot TX`. Recreate them in loopMIDI and re-run the installer. |
| No `[FLStudioPilot] Ready` in FL's Script output | The controller isn't registered: set the `FLStudioPilot RX` input's **Controller type** to **FLStudioPilot** in MIDI Settings, confirm `device_FLStudioPilot.py` is in `Settings\Hardware\FLStudioPilot\`, then fully restart FL Studio. |
| The LLM assistant can't reach FL / transport ping fails | Make sure the daemon is running (`fls-pilot-daemon`); check the transport matches (`FLS_PILOT_TRANSPORT=tcp` uses the daemon, unset uses direct MIDI); restart your MCP client after editing its config. |
| Note-writing does nothing | Run `MCP_Apply` once from the piano roll's scripting menu this session - it arms the note bridge. |
| Audio tools error or are unavailable | Install the optional extras: `pip install -e ".[audio]"` (or `".[audio,audio-accurate]"`). |
