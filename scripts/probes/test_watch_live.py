#!/usr/bin/env python3
"""Live demo: 1.2s snapshot peaks vs a multi-second WATCH (running max).

Shows watch mode catches peaks the snapshot's single ~1.2s window misses.
Play a quiet->loud section (or the drop) while the watch runs.

    python scripts/test_watch_live.py [watch_seconds]
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import contextlib

from fls_pilot.connection import get_bridge, reset_bridge  # noqa: E402
from fls_pilot.music import mix_doctor as md  # noqa: E402


def connect():
    order = (
        [os.environ["FLS_PILOT_TRANSPORT"]]
        if os.environ.get("FLS_PILOT_TRANSPORT")
        else ["tcp", "direct"]
    )
    for t in order:
        os.environ["FLS_PILOT_TRANSPORT"] = t
        reset_bridge()
        try:
            b = get_bridge()
            if b.is_alive():
                return b, t
        except Exception:
            pass
    return None, None


def main() -> int:
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    secs = float(sys.argv[1]) if len(sys.argv) > 1 else 12.0
    b, tr = connect()
    if b is None:
        print("FL bridge not reachable.")
        return 1
    print(f"connected via {tr}\n")

    # 1) snapshot peaks (sustained ~1.2s window)
    snap = md.gather_snapshot(b)
    snap_db = {t["index"]: t["peak_db"] for t in snap["tracks"]}
    names = {t["index"]: t["name"] for t in snap["tracks"]}

    # 2) watch (running max) for `secs`
    idxs = list(snap_db.keys())
    md.get_watcher().start(b, idxs, interval_ms=150)
    print(f"WATCHING {secs:.0f}s -- play a quiet->loud section / the drop now...\n")
    time.sleep(secs)
    mx, reads, el = md.get_watcher().stop()
    print("watch: %d polls over %.1fs\n" % (reads, el))

    print("%-22s %9s %9s %8s" % ("track", "snap_dB", "watch_dB", "delta"))
    caught = 0
    for i in idxs:
        sd = snap_db.get(i)
        wl = mx.get(i)
        wd = md.lin_to_db(wl) if wl else None
        delta = (wd - sd) if (sd is not None and wd is not None) else None
        flag = ""
        if delta is not None and delta > 1.0:
            flag = "  <-- watch caught more"
            caught += 1
        print(
            "%-22s %9s %9s %8s%s"
            % (
                (names.get(i) or "?")[:22],
                f"{sd:.1f}" if sd is not None else "-",
                f"{wd:.1f}" if wd is not None else "-",
                f"{delta:+.1f}" if delta is not None else "-",
                flag,
            )
        )
    print("\n%d track(s) where the watch caught a higher peak than the 1.2s snapshot." % caught)
    return 0


if __name__ == "__main__":
    sys.exit(main())
