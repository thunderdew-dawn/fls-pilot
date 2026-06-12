@echo off
REM ============================================================================
REM  fls-pilot -- Windows installer
REM    [1] controller script  -> FL Settings\Hardware\FLStudioPilot\
REM    [2] MCP server          -> pip install -e .
REM    [3] note-bridge script  -> seeds MCP_Apply.pyscript in Piano roll scripts\
REM    [4] loopMIDI port check
REM
REM  Assumes the standard FL 2025 user-data location:
REM    %USERPROFILE%\Documents\Image-Line\FL Studio\Settings
REM  If your FL data folder is elsewhere, edit FL_SETTINGS below.
REM ============================================================================
setlocal enabledelayedexpansion

set "FL_SETTINGS=%USERPROFILE%\Documents\Image-Line\FL Studio\Settings"
set "HW_TARGET=%FL_SETTINGS%\Hardware\FLStudioPilot"
set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."

set "USE_PIPX=0"
set "INSTALL_PIPX=0"

:parse_args
if "%~1"=="" goto end_args
if "%~1"=="--pipx" set "USE_PIPX=1"
if "%~1"=="--install-pipx" set "INSTALL_PIPX=1"
shift
goto parse_args
:end_args

echo.
echo [1/4] Installing FL Studio controller script...
if not exist "%FL_SETTINGS%\Hardware" (
  echo   FL Studio Settings\Hardware folder not found at:
  echo     %FL_SETTINGS%\Hardware
  echo   Open FL Studio at least once, then re-run this script.
  exit /b 1
)
if not exist "%HW_TARGET%" mkdir "%HW_TARGET%"
copy /Y "%REPO_ROOT%\fl_controller\FLStudioPilot\device_FLStudioPilot.py" "%HW_TARGET%\" >nul
if errorlevel 1 ( echo   Copy failed. Aborting. & exit /b 1 )
echo   Installed to %HW_TARGET%

echo.
echo [2/4] Installing the MCP server...
where python >nul 2>nul
if errorlevel 1 ( echo   Python not found on PATH. Install Python 3.12+ and re-run. & exit /b 1 )
pushd "%REPO_ROOT%"

if "!USE_PIPX!"=="1" (
  where pipx >nul 2>nul
  if errorlevel 1 (
    if "!INSTALL_PIPX!"=="1" (
      echo   pipx not found. Attempting to install via pip...
      python -m pip install --user pipx
      python -m pipx ensurepath
      echo   WARNING: PATH changes may require restarting the terminal!
    ) else (
      echo   pipx not found. Install pipx manually or run this script with --install-pipx.
      popd
      exit /b 1
    )
  )
  echo   Installing via pipx (editable)...
  pipx install --force --editable .
) else (
  if not exist ".venv" (
    echo   Creating virtual environment ^(.venv^)...
    python -m venv .venv
  )
  echo   Installing via .venv...
  .venv\Scripts\python.exe -m pip install --upgrade pip >nul
  .venv\Scripts\python.exe -m pip install -e .
  if errorlevel 1 ( echo   pip install failed. See output above. & popd & exit /b 1 )
)
popd

echo.
echo [3/4] Seeding the note-bridge pyscript (MCP_Apply)...
if "!USE_PIPX!"=="1" (
  set "PYTHONPATH=src"
  python -c "import os, fls_pilot.pyscript_gen as g; os.makedirs(g.PIANO_ROLL_SCRIPTS_DIR, exist_ok=True); print('   seeded ' + g.write_apply_script([], mode='append'))"
) else (
  .venv\Scripts\python.exe -c "import os, fls_pilot.pyscript_gen as g; os.makedirs(g.PIANO_ROLL_SCRIPTS_DIR, exist_ok=True); print('   seeded ' + g.write_apply_script([], mode='append'))"
)
if errorlevel 1 echo   Note: could not pre-seed MCP_Apply (FL Piano roll scripts folder missing?). Non-fatal -- the daemon writes it on the first note-write.

echo.
echo [4/4] Checking loopMIDI ports...
python -c "import mido; names=set(mido.get_output_names())|set(mido.get_input_names()); req=('FLStudioPilot RX','FLStudioPilot TX'); missing=[n for n in req if not any(n.lower() in x.lower() for x in names)]; print('   All required ports present.') if not missing else print('   MISSING ports: %s -- create them in loopMIDI.' % missing)"

echo.
echo ============================================================================
echo  Done. Next steps (see README for detail):
echo ============================================================================
echo   1. loopMIDI: if a port was MISSING above, create EXACTLY these two and re-run:
echo        "FLStudioPilot RX"   and   "FLStudioPilot TX"
echo        ( https://www.tobias-erichsen.de/software/loopmidi.html )
echo   2. FL Studio ^> Options ^> MIDI Settings:
echo        Input  ^> "FLStudioPilot RX": Enable, Controller type = FLStudioPilot, Port = 42
echo        Output ^> "FLStudioPilot TX": Enable, Port = 42  (the SAME number)
echo        View ^> Script output should show  [FLStudioPilot] Ready
if "!USE_PIPX!"=="1" (
  set "CMD_DAEMON=fls-pilot-daemon"
  set "CMD_SERVER=fls-pilot"
  set "CMD_OPT=pipx inject fls-pilot"
) else (
  set "CMD_DAEMON=.venv\Scripts\fls-pilot-daemon.exe"
  set "CMD_SERVER=.venv\Scripts\fls-pilot.exe"
  set "CMD_OPT=.venv\Scripts\python.exe -m pip install -e"
)

echo   3. Start the bridge daemon and keep it running:
echo        !CMD_DAEMON!
echo   4. Register with an MCP Client like Claude Desktop  (%%APPDATA%%\Claude\claude_desktop_config.json):
echo        "fl-studio": { "command": "!CMD_SERVER!", "env": { "FLS_PILOT_TRANSPORT": "tcp" } }
echo   5. Each session: open the Piano roll, and from its Scripting menu run "MCP_Apply"
echo        once (this arms note-writing). Then ask your AI assistant to call fl_ping.
echo.
echo  Optional audio features:   !CMD_OPT! ".[audio]"      (tempo/key + melody)
echo                             !CMD_OPT! ".[audio,audio-accurate]"  (+ CREPE)
echo.
endlocal
