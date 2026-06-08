#!/usr/bin/env python3
"""Live test: mixer/channel set tools report the TRUE post-write value.

Proves the safe_write fresh-read fix -- after each write, `after` matches what
was written (not the stale same-tick echo). Every write is restored to its
original value, so the project is left unchanged. Also sanity-checks rollback.

    python scripts/test_readback_fix.py [mixer_track] [channel]
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import contextlib

from fls_pilot import protocol, safety  # noqa: E402
from fls_pilot.connection import get_bridge, reset_bridge  # noqa: E402

_P = _F = 0


def check(label, cond, detail=""):
    global _P, _F
    _P += 1 if cond else 0
    _F += 0 if cond else 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}{'  -- ' + detail if detail else ''}")


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


def vol(bridge, mt, value, unit):
    return safety.safe_write(
        bridge,
        tool="mixer_set_volume",
        scope="mixer_track:%d" % mt,
        command=protocol.CMD_MIXER_SET_VOLUME,
        params={"track": mt, "value": value, "unit": unit},
        build_restore=lambda b: {
            "command": protocol.CMD_MIXER_SET_VOLUME,
            "params": {"track": mt, "value": b["vol_norm"], "unit": "normalized"},
        },
    )


def main() -> int:
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    mt = int(sys.argv[1]) if len(sys.argv) > 1 else 9
    ch = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    b, tr = connect()
    if b is None:
        print("FL bridge not reachable.")
        return 1
    print("connected via %s. testing mixer track %d, channel %d\n" % (tr, mt, ch))

    orig = b.call(protocol.CMD_MIXER_GET_TRACK, {"index": mt})
    o_norm, o_pan, o_name, o_db = orig["vol_norm"], orig["pan"], orig["name"], orig["vol_db"]

    # 1) VOLUME: set -6 dB, expect a FRESH after (~ -6), not the stale original.
    r = vol(b, mt, -6.0, "db")
    a = r.get("after") or {}
    check(
        f"volume after is FRESH (~ -6 dB; stale would read {o_db:.1f})",
        a.get("vol_db") is not None and abs(a["vol_db"] - (-6.0)) <= 0.6,
        f"after vol_db={a.get('vol_db')}",
    )
    vol(b, mt, o_norm, "normalized")  # restore

    # 2) PAN: set 0.5, expect FRESH after (~0.5).
    r = safety.safe_write(
        b,
        tool="mixer_set_pan",
        scope="mixer_track:%d" % mt,
        command=protocol.CMD_MIXER_SET_PAN,
        params={"track": mt, "value": 0.5},
        build_restore=lambda b: {
            "command": protocol.CMD_MIXER_SET_PAN,
            "params": {"track": mt, "value": b["pan"]},
        },
    )
    a = r.get("after") or {}
    check(
        f"pan after is FRESH (~0.5; stale would read {o_pan:.2f})",
        a.get("pan") is not None and abs(a["pan"] - 0.5) <= 0.05,
        f"after pan={a.get('pan')}",
    )
    safety.safe_write(
        b,
        tool="mixer_set_pan",
        scope="mixer_track:%d" % mt,
        command=protocol.CMD_MIXER_SET_PAN,
        params={"track": mt, "value": o_pan},
        build_restore=lambda b: {
            "command": protocol.CMD_MIXER_SET_PAN,
            "params": {"track": mt, "value": b["pan"]},
        },
    )  # restore

    # 3) NAME: set a test name, expect FRESH after == test name.
    test_name = ((o_name or "Track")[:18]) + "_RB"
    r = safety.safe_write(
        b,
        tool="mixer_set_name",
        scope="mixer_track:%d" % mt,
        command=protocol.CMD_MIXER_SET_NAME,
        params={"track": mt, "name": test_name},
        build_restore=lambda b: {
            "command": protocol.CMD_MIXER_SET_NAME,
            "params": {"track": mt, "name": b["name"]},
        },
    )
    a = r.get("after") or {}
    check(
        f"name after is FRESH (== {test_name!r}; stale would read {o_name!r})",
        a.get("name") == test_name,
        f"after name={a.get('name')!r}",
    )
    safety.safe_write(
        b,
        tool="mixer_set_name",
        scope="mixer_track:%d" % mt,
        command=protocol.CMD_MIXER_SET_NAME,
        params={"track": mt, "name": o_name},
        build_restore=lambda b: {
            "command": protocol.CMD_MIXER_SET_NAME,
            "params": {"track": mt, "name": b["name"]},
        },
    )  # restore

    # 4) CHANNEL volume (same code path -> auto-fixed). Guarded.
    try:
        corig = b.call(protocol.CMD_CHANNEL_GET, {"index": ch})
        c_norm, c_db = corig["vol_norm"], corig["vol_db"]
        r = safety.safe_write(
            b,
            tool="channel_set_volume",
            scope="channel:%d" % ch,
            command=protocol.CMD_CHANNEL_SET_VOLUME,
            params={"channel": ch, "value": -6.0, "unit": "db"},
            build_restore=lambda b: {
                "command": protocol.CMD_CHANNEL_SET_VOLUME,
                "params": {"channel": ch, "value": b["vol_norm"], "unit": "normalized"},
            },
        )
        a = r.get("after") or {}
        check(
            f"channel volume after is FRESH (~ -6 dB; stale would read {c_db:.1f})",
            a.get("vol_db") is not None and abs(a["vol_db"] - (-6.0)) <= 0.6,
            f"after vol_db={a.get('vol_db')}",
        )
        safety.safe_write(
            b,
            tool="channel_set_volume",
            scope="channel:%d" % ch,
            command=protocol.CMD_CHANNEL_SET_VOLUME,
            params={"channel": ch, "value": c_norm, "unit": "normalized"},
            build_restore=lambda b: {
                "command": protocol.CMD_CHANNEL_SET_VOLUME,
                "params": {"channel": ch, "value": b["vol_norm"], "unit": "normalized"},
            },
        )
    except Exception as e:
        print(f"  [SKIP] channel volume test -- {type(e).__name__}: {e}")

    # 5) ROLLBACK sanity: write -10 dB, rollback, confirm reverted (fresh read).
    vol(b, mt, -10.0, "db")
    rb = safety.rollback_last_change(b)
    fresh = b.call(protocol.CMD_MIXER_GET_TRACK, {"index": mt})
    check(
        "rollback still works (track back to original norm)",
        rb.get("ok") and abs(fresh["vol_norm"] - o_norm) <= 0.001,
        f"now vol_norm={fresh['vol_norm']} (orig {o_norm})",
    )

    # final: everything restored?
    fin = b.call(protocol.CMD_MIXER_GET_TRACK, {"index": mt})
    check(
        "project left UNCHANGED (vol/pan/name restored)",
        abs(fin["vol_norm"] - o_norm) <= 0.001
        and abs(fin["pan"] - o_pan) <= 0.001
        and fin["name"] == o_name,
        f"vol_norm={fin['vol_norm']} pan={fin['pan']} name={fin['name']!r}",
    )

    print("\n%d passed, %d failed" % (_P, _F))
    return 0 if _F == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
