#!/usr/bin/env python3
"""Mix Doctor (Stage 1): gather a whole-mix snapshot + print a ranked diagnosis.

READ-ONLY. Gathers via cheap bridge reads, runs the pure rule engine, prints a
plain-language problem report with proposed fixes. Does NOT apply anything.

    python scripts/run_mix_doctor.py [--no-params] [--max-tracks N]
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp.connection import get_bridge, reset_bridge  # noqa: E402
from fl_studio_mcp.music import mix_doctor as md  # noqa: E402

SEV_TAG = {"high": "[HIGH]", "medium": "[MED ]", "low": "[LOW ]"}


def connect():
    order = ([os.environ["FLSTUDIO_MCP_TRANSPORT"]]
             if os.environ.get("FLSTUDIO_MCP_TRANSPORT") else ["tcp", "direct"])
    for t in order:
        os.environ["FLSTUDIO_MCP_TRANSPORT"] = t
        reset_bridge()
        try:
            b = get_bridge()
            if b.is_alive():
                return b, t
        except Exception as e:
            print("  transport %-6s unavailable: %s: %s" % (t, type(e).__name__, e))
    return None, None


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    with_params = "--no-params" not in sys.argv
    max_tracks = 64
    if "--max-tracks" in sys.argv:
        max_tracks = int(sys.argv[sys.argv.index("--max-tracks") + 1])

    print("connecting to FL bridge...")
    bridge, transport = connect()
    if bridge is None:
        print("FL bridge NOT reachable. Open FL Studio + bring up the MCP bridge "
              "(daemon for tcp, or loopMIDI ports for direct).")
        return 1
    print("connected via %s.\n" % transport)

    t0 = time.time()
    snap = md.gather_snapshot(bridge, with_params=with_params, max_tracks=max_tracks)
    gather_s = time.time() - t0
    size_kb = len(json.dumps(snap, default=str).encode("utf-8")) / 1024.0
    res = md.diagnose(snap)

    print("=== Mix Doctor report ===")
    print("transport   :", transport)
    print("tracks       : %d   playing: %s" % (snap["track_count"], snap["playing"]))
    print("gathered in  : %.2fs   snapshot %.1f KB   params=%s" % (gather_s, size_kb, with_params))
    if snap.get("gather_errors"):
        print("gather errors: %d  (e.g. %s)" % (len(snap["gather_errors"]), snap["gather_errors"][0]))
    s = res["summary"]
    print("findings     : %d high, %d medium, %d low\n" % (s["high"], s["medium"], s["low"]))

    for note in res["notes"]:
        print("NOTE:", note)
    if res["notes"]:
        print()

    if not res["findings"]:
        print("No problems detected by the current rules. (Quiet mix, or play for level checks.)")
    for i, f in enumerate(res["findings"], 1):
        where = (" <%s>" % f["track"]) if f["track"] else ""
        print("%2d. %s %s%s" % (i, SEV_TAG.get(f["severity"], "[?]"), f["rule"], where))
        print("    %s" % f["message"])
        print("    evidence : %s" % f["evidence"])
        fix = f["proposed_fix"]
        print("    proposed : %s  (%s)" % (fix.get("intent"), fix.get("desc")))
    print("\n(Proposals only -- nothing applied. Stage 2 will let you approve + apply.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
