@echo off
REM ============================================================================
REM FLStudioMCP -- Windows installer (v0.2 -- MIDI transport)
REM ============================================================================
setlocal enabledelayedexpansion

set "FL_HARDWARE=%USERPROFILE%\Documents\Image-Line\FL Studio\Settings\Hardware"
set "TARGET=%FL_HARDWARE%\FLStudioMCP"
set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."

echo.
echo [1/3] Installing FL Studio controller script...
if not exist "%FL_HARDWARE%" (
  echo   FL Studio Hardware folder not found at:
  echo     %FL_HARDWARE%
  echo   Open FL Studio at least once, then re-run this script.
  exit /b 1
)
if not exist "%TARGET%" mkdir "%TARGET%"
copy /Y "%REPO_ROOT%\fl_controller\FLStudioMCP\device_FLStudioMCP.py" "%TARGET%\" >nul
if errorlevel 1 (
  echo   Copy failed. Aborting.
  exit /b 1
)
echo   Installed to %TARGET%

echo.
echo [2/3] Installing the MCP server (editable)...
where python >nul 2>nul
if errorlevel 1 (
  echo   Python not found on PATH. Install Python 3.10+ and re-run.
  exit /b 1
)
pushd "%REPO_ROOT%"
python -m pip install --upgrade pip >nul
python -m pip install -e .
if errorlevel 1 (
  echo   pip install failed. See output above.
  popd
  exit /b 1
)
popd

echo.
echo [3/3] Checking for loopMIDI ports...
python -c "import mido; names=set(mido.get_output_names())|set(mido.get_input_names()); rx='FLStudioMCP RX'; tx='FLStudioMCP TX'; missing=[n for n in (rx, tx) if not any(n.lower() in x.lower() for x in names)]; print('  All required ports present.') if not missing else print('  Missing ports: %s' % missing)"

echo.
echo Done.
echo.
echo Next steps:
echo   1. If the port check above said any port is MISSING:
echo      - Install loopMIDI: https://www.tobias-erichsen.de/software/loopmidi.html
echo      - Open loopMIDI, create exactly: "FLStudioMCP RX" and "FLStudioMCP TX".
echo      - Re-run this installer to re-check.
echo   2. Open FL Studio.
echo   3. Options ^> MIDI Settings:
echo        Input list  ^> click "FLStudioMCP RX", tick Enable, Controller type=FLStudioMCP, Port=42.
echo        Output list ^> click "FLStudioMCP TX", tick Enable, Port=42 (SAME number).
echo   4. View ^> Script output should show "[FLStudioMCP] Ready. ...".
echo   5. Run: python scripts\test_bridge.py
echo.
endlocal
