#!/usr/bin/env python3
"""LIVE: Run a focused capability sweep against the current FL project.

This script answers: "What can the MCP server reliably do on THIS FL build,
right now?" by executing the existing live smoke scripts plus plugin and
documented-API false-positive probes.

Pre-req:
- FL Studio open with the fixture project copy loaded.
- fl-studio-mcp daemon running (TCP).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("FLSTUDIO_MCP_TRANSPORT", "tcp")

ROOT = Path(__file__).resolve().parents[1]


def _run(label: str, args: list[str]) -> int:
    print(f"\n=== {label} ===")
    proc = subprocess.run(args, cwd=str(ROOT))
    return int(proc.returncode)


def main() -> int:
    venv_py = ROOT / ".venv" / "bin" / "python"
    py = str(venv_py) if venv_py.exists() else (sys.executable or "python3")

    rc = 0
    rc |= _run("Priority 1/2 live smoke", [py, "scripts/test_priority12_live.py"])
    rc |= _run("Patterns & playlist live", [py, "scripts/test_pattern_playlist_live.py"])
    rc |= _run("Mixer live", [py, "scripts/test_mixer_live.py"])
    rc |= _run("Step sequencer live", [py, "scripts/test_step_sequencer_live.py"])
    rc |= _run("Plugin param live probe (track 49/50)", [py, "scripts/test_plugin_param_live.py"])
    rc |= _run(
        "Documented API false-positive probes",
        [py, "scripts/probe_documented_api_live.py"],
    )
    rc |= _run(
        "Targeted effect plugin probes (track 49/50)",
        [py, "scripts/test_effect_targets_live.py"],
    )

    print("\n=== Summary ===")
    if rc == 0:
        print("[OK] All sweep steps returned success.")
    else:
        print("[WARN] One or more sweep steps returned a non-zero exit code.")
        print("       Check the section output above for [FAIL]/[BLOCKED].")
    return 0 if rc == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
