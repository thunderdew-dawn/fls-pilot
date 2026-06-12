#!/usr/bin/env bash
# ============================================================================
# FLStudioPilot -- macOS installer (v0.2 -- MIDI transport)
# ============================================================================
set -euo pipefail

FL_HARDWARE="$HOME/Documents/Image-Line/FL Studio/Settings/Hardware"
TARGET="$FL_HARDWARE/FLStudioPilot"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo
echo "[1/4] Installing FL Studio controller script..."
if [[ ! -d "$FL_HARDWARE" ]]; then
  echo "  FL Studio Hardware folder not found at:"
  echo "    $FL_HARDWARE"
  echo "  Open FL Studio at least once, then re-run this script."
  exit 1
fi
if [[ ! -f "$REPO_ROOT/fl_controller/FLStudioPilot/device_FLStudioPilot.py" ]]; then
  echo "  Error: Source controller script not found. Are you running this from the cloned repo?"
  exit 1
fi
mkdir -p "$TARGET"
cp "$REPO_ROOT/fl_controller/FLStudioPilot/device_FLStudioPilot.py" "$TARGET/"
echo "  Installed to $TARGET"

USE_PIPX=0
INSTALL_PIPX=0

for arg in "$@"; do
  case $arg in
    --pipx)
      USE_PIPX=1
      shift
      ;;
    --install-pipx)
      INSTALL_PIPX=1
      shift
      ;;
    *)
      # Ignore unknown options
      shift
      ;;
  esac
done

echo
echo "[2/4] Installing the MCP server..."
if ! command -v python3 >/dev/null 2>&1; then
  echo "  python3 not found. Install Python 3.10+ and re-run."
  exit 1
fi
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
  echo "  Python 3.10+ is required. Please upgrade your Python installation."
  exit 1
fi
cd "$REPO_ROOT"

PIPX_CMD="pipx"
if [[ "$USE_PIPX" -eq 1 ]]; then
  if ! command -v pipx >/dev/null 2>&1; then
    if [[ "$INSTALL_PIPX" -eq 1 ]]; then
      echo "  pipx not found. Attempting to install via pip..."
      python3 -m pip install --user pipx
      python3 -m pipx ensurepath
      echo "  WARNING: PATH changes may require restarting your terminal!"
      export PATH="$HOME/.local/bin:$PATH"
      PIPX_CMD="python3 -m pipx"
    else
      echo "  pipx not found. Install pipx manually or run this script with --install-pipx."
      exit 1
    fi
  fi
  echo "  Installing via pipx (editable)..."
  $PIPX_CMD install --force --editable .
else
  if [[ -z "${VIRTUAL_ENV:-}" ]]; then
    if [[ ! -d ".venv" ]]; then
      echo "  Creating virtual environment (.venv)..."
      python3 -m venv .venv
    fi
    echo "  Activating virtual environment (.venv)..."
    source .venv/bin/activate
  fi
  python3 -m pip install --upgrade pip >/dev/null
  python3 -m pip install -e .
fi

echo
echo "[3/4] Seeding the note-bridge pyscript (MCP_Apply)..."
if [[ "$USE_PIPX" -eq 1 ]]; then
  PYTHONPATH=src python3 -c "import os, fls_pilot.pyscript_gen as g; os.makedirs(g.PIANO_ROLL_SCRIPTS_DIR, exist_ok=True); print('  Seeded ' + g.write_apply_script([], mode='append'))" || echo "  Note: Could not pre-seed MCP_Apply. Non-fatal -- daemon will write it on first note-write."
else
  python3 -c "import os, fls_pilot.pyscript_gen as g; os.makedirs(g.PIANO_ROLL_SCRIPTS_DIR, exist_ok=True); print('  Seeded ' + g.write_apply_script([], mode='append'))" || echo "  Note: Could not pre-seed MCP_Apply. Non-fatal -- daemon will write it on first note-write."
fi

echo
echo "[4/4] Checking for IAC Driver ports..."
if python3 -c 'import mido' 2>/dev/null; then
  python3 - <<'PYEOF'
import mido
names = set(mido.get_output_names()) | set(mido.get_input_names())
rx, tx = "FLStudioPilot RX", "FLStudioPilot TX"
missing = [n for n in (rx, tx) if not any(n.lower() in x.lower() for x in names)]
if not missing:
    print("  All required ports present.")
else:
    print(f"  Missing ports: {missing}")
PYEOF
else
  echo "  (Automated port check skipped: 'mido' module not in global environment.)"
  echo "  If using pipx, please manually ensure you have created the required IAC ports."
fi

if [[ "$USE_PIPX" -eq 1 ]]; then
  CMD_DAEMON="fls-pilot-daemon"
  CMD_SERVER="fls-pilot"
else
  CMD_DAEMON="$REPO_ROOT/.venv/bin/fls-pilot-daemon"
  CMD_SERVER="$REPO_ROOT/.venv/bin/fls-pilot"
fi

cat <<EOF

Done.

Next steps:
  1. If the port check above said any port is MISSING:
     - Open 'Audio MIDI Setup'.
     - Window > Show MIDI Studio.
     - Double-click IAC Driver. Tick 'Device is online'.
     - Under 'Ports', add two ports named exactly:
         FLStudioPilot RX
         FLStudioPilot TX
     - Apply, then re-run this installer.
  2. Open FL Studio.
  3. Options > MIDI Settings:
       Input list  > click 'FLStudioPilot RX', tick Enable, Controller type=FLStudioPilot, Port=42.
       Output list > click 'FLStudioPilot TX', tick Enable, Port=42 (SAME number).
  4. View > Script output should show '[FLStudioPilot] Ready. ...'.
  5. Run: python3 scripts/test_bridge.py

To use with Claude Desktop, Cursor, or other stdio clients:
  1. Start the daemon (holds the MIDI ports):
     $CMD_DAEMON
  2. Add this to your client's config (e.g. for Claude Desktop: ~/Library/Application Support/Claude/claude_desktop_config.json):
  {
    "mcpServers": {
      "fl-studio": {
        "command": "$CMD_SERVER",
        "env": {
          "FLS_PILOT_TRANSPORT": "tcp"
        }
      }
    }
  }

To use with ChatGPT Desktop (SSE):
  1. Start the daemon (holds the MIDI ports):
     $CMD_DAEMON
  2. In another terminal, run the MCP server with SSE transport:
     export FLS_PILOT_TRANSPORT=tcp
     $CMD_SERVER --sse --port 8080
  3. Open ChatGPT Desktop, go to Settings > Developer > MCP, click "Add New Server":
     - Name: FL Studio
     - URL: http://localhost:8080/sse

IMPORTANT (macOS Accessibility):
  Because the note-writing tool simulates keyboard shortcuts (Cmd+Opt+Y) to trigger
  the script in FL Studio, you must grant Accessibility permissions to the application
  running the MCP server.
  Go to System Settings > Privacy & Security > Accessibility and ensure your terminal
  (e.g., Terminal, iTerm, Warp) or your MCP Client app (Claude/ChatGPT/Cursor) is checked/enabled.
EOF
