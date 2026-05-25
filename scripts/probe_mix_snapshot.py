#!/usr/bin/env python3
"""PROBE (Mix Doctor Stage 0): can we snapshot the WHOLE mix without stalling?

READ-ONLY. The server orchestrates many CHEAP calls -- two paginated list
reads (all-track vol/pan/mute/solo/name + the full routing matrix) plus one
peaks + one plugin_list per track -- so NO heavy all-track loop runs in a
single controller OnSysEx tick (that stalled FL before). Measures snapshot
size, round-trips, wall time, slowest call, and errors/stalls.

Does NOT diagnose and does NOT write anything (no play, no param sets). Run:

    python scripts/probe_mix_snapshot.py [--params] [--max-tracks N]

--params also samples a few parameter values per loaded plugin (extra calls).
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp import protocol  # noqa: E402
from fl_studio_mcp.connection import (  # noqa: E402
    fetch_all_pages,
    get_bridge,
    reset_bridge,
)


class CountingBridge:
    """Wraps a real bridge, counting + timing every .call (incl. pagination)."""

    def __init__(self, inner):
        self.inner = inner
        self.calls = 0
        self.total_time = 0.0
        self.slowest = (0.0, None)
        self.per_cmd = {}

    def call(self, cmd, params=None, timeout=None):
        self.calls += 1
        t0 = time.time()
        try:
            return self.inner.call(cmd, params, timeout=timeout)
        finally:
            dt = time.time() - t0
            self.total_time += dt
            slot = self.per_cmd.setdefault(cmd, [0, 0.0])
            slot[0] += 1
            slot[1] += dt
            if dt > self.slowest[0]:
                self.slowest = (dt, cmd)

    def is_alive(self):
        return self.inner.is_alive()


def connect():
    """Pick a transport: env override, else daemon(tcp) then direct MIDI."""
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


def safe(errors, fn, label):
    try:
        return fn()
    except Exception as e:
        errors.append("%s -> %s: %s" % (label, type(e).__name__, e))
        return None


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    want_params = "--params" in sys.argv
    max_tracks = 40
    if "--max-tracks" in sys.argv:
        max_tracks = int(sys.argv[sys.argv.index("--max-tracks") + 1])

    print("connecting to FL bridge...")
    raw, transport = connect()
    if raw is None:
        print("FL bridge NOT reachable. Ensure FL Studio is open and the MCP "
              "bridge is up (daemon for tcp, or loopMIDI ports for direct).")
        return 1
    cb = CountingBridge(raw)
    print("connected via %s transport.\n" % transport)

    errors = []
    t_start = time.time()

    # 1) project state -> tempo + playing (peaks only meaningful while playing)
    ps = safe(errors, lambda: cb.call(protocol.CMD_GET_PROJECT_STATE), "project_state") or {}
    playing = ps.get("playing")

    # 2) all-track vol/pan/mute/solo/name -- ONE paginated sequence
    tracks_pg = safe(errors, lambda: fetch_all_pages(cb, protocol.CMD_MIXER_LIST_TRACKS, "tracks"),
                     "mixer_list_tracks") or {"tracks": []}
    tracks = tracks_pg.get("tracks", [])

    # 3) routing matrix -- ONE paginated sequence
    routing_pg = safe(errors, lambda: fetch_all_pages(cb, protocol.CMD_MIXER_GET_ROUTING_ALL, "routing"),
                      "mixer_get_routing_all") or {"routing": []}
    routing = routing_pg.get("routing", [])
    route_by_idx = {}
    for r in routing:
        idx = r.get("track", r.get("index"))
        if idx is not None:
            route_by_idx[idx] = r

    n = len(tracks)
    capped = n > max_tracks
    loop_tracks = tracks[:max_tracks]

    # 4) per-track peaks + plugins (+ optional param sample): one CHEAP call per
    #    controller tick. Server-side loop -- the controller never loops itself.
    snapshot = []
    for t in loop_tracks:
        i = t.get("index", t.get("i"))
        rec = {"index": i, "name": t.get("name"),
               "volume": t.get("volume"), "pan": t.get("pan"),
               "mute": t.get("mute"), "solo": t.get("solo")}
        pk = safe(errors, lambda: cb.call(protocol.CMD_MIXER_GET_PEAKS, {"track": i}),
                  "peaks[%s]" % i)
        rec["peak_max"] = (pk or {}).get("peak_max")
        pl = safe(errors, lambda: cb.call(protocol.CMD_PLUGIN_LIST, {"track": i}),
                  "plugin_list[%s]" % i)
        rec["plugins"] = pl
        rec["routes_to"] = (route_by_idx.get(i) or {}).get("routes_to")
        if want_params and pl:
            slots = pl.get("plugins") or pl.get("slots") or []
            psample = {}
            for s in slots:
                slot_idx = s.get("slot", s.get("index"))
                if slot_idx is None:
                    continue
                page = safe(errors, lambda: cb.call(
                    protocol.CMD_PLUGIN_GET_PARAMS,
                    {"track": i, "slot": slot_idx, "start": 0}), "params[%s:%s]" % (i, slot_idx))
                if page:
                    psample[slot_idx] = {"total": page.get("total"),
                                         "first": (page.get("params") or [])[:4]}
            rec["params_sample"] = psample
        snapshot.append(rec)

    elapsed = time.time() - t_start
    blob = json.dumps(snapshot, default=str)
    size_kb = len(blob.encode("utf-8")) / 1024.0

    # ---- report ----
    print("=== Mix Doctor snapshot probe ===")
    print("transport      :", transport)
    print("playing        :", playing,
          "" if playing else "  <- peaks NOT meaningful (project stopped)")
    print("mixer tracks   :", n, ("(capped to %d for probe)" % max_tracks) if capped else "")
    print("round-trips    :", cb.calls)
    print("wall time      : %.2fs" % elapsed)
    print("bridge time    : %.2fs (sum of round-trips)" % cb.total_time)
    print("slowest call   : %.3fs (%s)" % (cb.slowest[0], cb.slowest[1]))
    print("snapshot size  : %.1f KB  (%d tracks, params=%s)" % (size_kb, len(snapshot), want_params))
    print("errors/stalls  :", len(errors))
    for e in errors[:12]:
        print("   !", e)
    print("\nper-command round-trips (by total time):")
    for cmd, (c, tt) in sorted(cb.per_cmd.items(), key=lambda kv: -kv[1][1]):
        print("   %-22s x%-3d  %.2fs" % (cmd, c, tt))

    print("\nraw mixer_list_tracks[0]:")
    print("  ", json.dumps(tracks[0], default=str)[:300] if tracks else "(none)")
    print("raw routing[0]:")
    print("  ", json.dumps(routing[0], default=str)[:300] if routing else "(none)")

    print("\nper-track record shape (keys):")
    if snapshot:
        print("  ", list(snapshot[0].keys()))
        withpl = next((r for r in snapshot
                       if isinstance(r.get("plugins"), dict)
                       and (r["plugins"].get("plugins") or r["plugins"].get("slots"))), None)
        sample = withpl or snapshot[0]
        print("\nsample track (index %s):" % sample.get("index"))
        print(json.dumps(sample, indent=2, default=str)[:1600])
    return 0


if __name__ == "__main__":
    sys.exit(main())
