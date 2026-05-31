#!/usr/bin/env python3
"""Offline test: preset_library against a SYNTHETIC temp tree (via env overrides)
+ score_presets matching. No FL.

    python scripts/test_preset_library.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp.music import preset_library as pre  # noqa: E402

_P = _F = 0


def check(label, cond, detail=""):
    global _P, _F
    _P += 1 if cond else 0
    _F += 0 if cond else 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}{'  -- ' + detail if detail else ''}")


def touch(p):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text("", encoding="utf-8")


def main() -> int:
    d = Path(tempfile.mkdtemp(prefix="flmcp_pre_"))
    fl = d / "Presets"
    serum = d / "Xfer" / "Serum 2 Presets"
    touch(fl / "Plugin presets" / "Fruity Parametric EQ 2" / "Bright Vocal.fst")
    touch(fl / "Plugin presets" / "Fruity Parametric EQ 2" / "Default.fst")
    touch(fl / "Plugin presets" / "Fruity Compressor" / "Glue Bus.fst")
    touch(fl / "Channel presets" / "My Kick.fst")
    touch(serum / "Bass" / "Vintage Bass.serumpreset")
    touch(serum / "Lead" / "BA Growl.serumpreset")
    touch(serum / "Lead" / "LD Saw.serumpreset")

    os.environ["FLSTUDIO_MCP_PRESETS"] = str(fl)
    os.environ["FLSTUDIO_MCP_SERUM_PRESETS"] = str(serum)

    # summary
    s = pre.list_presets()
    check(
        "summary lists plugins with presets",
        s["plugins_with_presets"].get("Fruity Parametric EQ 2") == 2,
        str(s.get("plugins_with_presets")),
    )
    check(
        "summary counts serum presets",
        s["serum_preset_count"] == 3,
        str(s.get("serum_preset_count")),
    )
    check("summary has channel presets", s.get("channel_presets", {}).get("count") == 1)

    # filtered: Serum
    f = pre.list_presets(plugin_filter="Serum")
    serum_names = f["presets"].get("Serum 2 (Xfer)", [])
    check(
        "Serum filter returns the .serumpreset names",
        set(serum_names) == {"Vintage Bass", "BA Growl", "LD Saw"},
        str(serum_names),
    )

    # filtered: a specific FL plugin
    f2 = pre.list_presets(plugin_filter="Parametric EQ")
    check(
        "plugin filter narrows to that plugin",
        "Bright Vocal" in f2["presets"].get("Fruity Parametric EQ 2", []),
        str(f2.get("presets")),
    )

    # score_presets
    m = pre.score_presets(serum_names, "vintage bass")
    check("'vintage bass' ranks 'Vintage Bass' first", m and m[0] == "Vintage Bass", str(m))
    check("'vintage bass' also matches 'BA Growl' (ba=bass)", "BA Growl" in m, str(m))
    check("'LD Saw' not matched for 'vintage bass'", "LD Saw" not in m, str(m))

    # real machine read (best-effort -- only if FL/Serum present; clear env first)
    del os.environ["FLSTUDIO_MCP_PRESETS"]
    del os.environ["FLSTUDIO_MCP_SERUM_PRESETS"]
    real = pre.list_presets()
    print(
        "\nREAL read: found=%s | plugins_with_presets=%d | serum=%s"
        % (
            real.get("found"),
            len(real.get("plugins_with_presets", {})),
            real.get("serum_preset_count"),
        )
    )

    print("\n%d passed, %d failed" % (_P, _F))
    return 0 if _F == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
