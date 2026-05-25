#!/usr/bin/env python3
"""Offline test: plugin_library.list_installed (de-dupe + categorize) +
effects_by_role, against a SYNTHETIC temp 'Installed' tree (no FL).

    python scripts/test_plugin_library.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp.music import plugin_library as pl  # noqa: E402

_P = _F = 0


def check(label, cond, detail=""):
    global _P, _F
    _P += 1 if cond else 0
    _F += 0 if cond else 1
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", label, ("  -- " + detail) if detail else ""))


def touch(base, rel):
    p = Path(base) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("", encoding="utf-8")


def main() -> int:
    d = Path(tempfile.mkdtemp(prefix="flmcp_lib_"))
    base = d / "Installed"
    # effects: Pro-C 3 appears in BOTH VST3 and New (dup -> must de-dupe to one)
    touch(base, "Effects/Fruity/Fruity Compressor.fst")
    touch(base, "Effects/VST3/FabFilter Pro-C 3.fst")
    touch(base, "Effects/New/FabFilter Pro-C 3.fst")
    touch(base, "Effects/VST3/Ozone 12 Equalizer.fst")
    touch(base, "Effects/VST3/Frequency Splitter.fst")    # must NOT bucket as eq
    touch(base, "Generators/Fruity/Sytrus.fst")
    touch(base, "Generators/VST3/Serum 2.fst")

    lib = pl.list_installed(str(base))
    check("found the Installed tree", lib.get("found") is True, str(lib.get("error")))
    check("effects de-duped (Pro-C 3 once)",
          lib["effects"].count("FabFilter Pro-C 3") == 1, str(lib["effects"]))
    check("effects count = 4 unique", lib["counts"]["effects"] == 4, str(lib["counts"]))
    check("generators = Serum 2 + Sytrus", set(lib["generators"]) == {"Serum 2", "Sytrus"},
          str(lib["generators"]))

    roles = pl.effects_by_role(lib["effects"])
    check("comp bucket has both compressors",
          set(roles.get("compressor", [])) == {"FabFilter Pro-C 3", "Fruity Compressor"},
          str(roles.get("compressor")))
    check("eq bucket has Ozone Equalizer", "Ozone 12 Equalizer" in roles.get("eq", []),
          str(roles.get("eq")))
    check("'Frequency Splitter' NOT mis-bucketed as eq",
          "Frequency Splitter" not in roles.get("eq", []), str(roles.get("eq")))

    # missing tree -> graceful
    miss = pl.list_installed(str(d / "nope"))
    check("missing folder -> found False + error", miss.get("found") is False and "error" in miss)

    print("\n%d passed, %d failed" % (_P, _F))
    return 0 if _F == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
