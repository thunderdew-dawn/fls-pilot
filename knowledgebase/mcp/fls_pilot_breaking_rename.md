# FL Studio Pilot Breaking Rename

- **Date:** 2026-06-08
- **Agent/Author:** Codex
- **Topic:** FL Studio Pilot package, command, controller, and environment rename.
- **Affected File/API:** `pyproject.toml`, `server.json`, `src/fls_pilot`, `fl_controller/FLStudioPilot/device_FLStudioPilot.py`, FastMCP server metadata, console scripts, and runtime environment variables.
- **Context:** Release 3.0 intentionally renames the maintained project to `fls-pilot`, meaning FL Studio Pilot. The rename is breaking and does not retain compatibility aliases.
- **Observation:** The supported distribution, import package, CLI commands, controller script identity, default MIDI port names, and environment-variable prefix now use the FL Studio Pilot naming scheme.
- **Tested Values:** `fls-pilot`, `fls-pilot-daemon`, `fls_pilot`, `FLStudioPilot`, `FLStudioPilot RX`, `FLStudioPilot TX`, `FLS_PILOT_TRANSPORT`, `FLS_PILOT_PORT_TO_FL`, and `FLS_PILOT_PORT_FROM_FL`.
- **Result:** A fresh editable install exposes only the new console scripts, imports `fls_pilot` at version `3.0.0a1`, does not resolve `fl_studio_mcp`, and builds a wheel containing `fls_pilot` without `fl_studio_mcp`.
- **Confidence Level:** `implementation_verified`
- **Source/Method:** Static rename scan, fresh scratch virtualenv install, console script existence check, importlib import-path check, wheel contents check, `twine check`, and `pytest`.
- **Valid Ranges:** Not applicable; this entry documents project identity and runtime names rather than FL Studio parameter ranges.
- **Example:** Use `FLS_PILOT_TRANSPORT=tcp fls-pilot` with the `FLStudioPilot` controller and `FLStudioPilot RX/TX` MIDI ports.
- **Known Pitfalls:** Local MIDI ports created before the rename may still be named `FLStudioMCP RX/TX` and must be renamed manually. Historical verification evidence may retain old names because it describes the implementation that existed at the time. The GitHub repository slug still requires an external owner/admin rename from `thunderdew-dawn/flstudio-mcp` to `thunderdew-dawn/fls-pilot`.
- **Reproduction Steps:** Create a fresh virtual environment, install the project with `pip install -e .`, verify `import fls_pilot` and version `3.0.0a1`, verify `importlib.util.find_spec("fl_studio_mcp") is None`, verify `fls-pilot` and `fls-pilot-daemon` exist and old console scripts do not, then build the wheel and confirm it contains `fls_pilot` but not `fl_studio_mcp`.
- **Open Questions:** The external GitHub repository rename must be completed by an owner/admin at the release gate.
- **Next Recommended Action:** After merging the rename PR, perform the GitHub repository rename and ask users to rename local MIDI ports and MCP client configs before running live FL Studio checks.
