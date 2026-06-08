#!/usr/bin/env python3
"""Routing/cleanup Slice 1 test -- READ ONLY.

Drives the bridge directly (no writes): dumps the routing matrix, channel->
mixer links, and cleanup candidates, so we can eyeball whether the reads are
accurate and the cleanup flags are sane (not flagging in-use tracks).

    set FLS_PILOT_TRANSPORT=tcp
    python scripts/test_routing_read.py [track]   # default track 2 for single read
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fls_pilot import protocol  # noqa: E402
from fls_pilot.connection import fetch_all_pages, get_bridge  # noqa: E402
from fls_pilot.tools.routing import detect_cleanup  # noqa: E402

TRACK = int(sys.argv[1]) if len(sys.argv) > 1 else 2


def show(title, obj):
    print(f"\n=== {title} ===")
    print(json.dumps(obj, indent=2))


def main() -> int:
    bridge = get_bridge()
    bridge.open()
    if not bridge.is_alive():
        print("Bridge not alive -- FL open? controller reloaded? daemon up (tcp)?")
        return 1
    print("Heartbeat age:", bridge.heartbeat_age())

    # 1. full routing matrix
    routing = fetch_all_pages(bridge, protocol.CMD_MIXER_GET_ROUTING_ALL, "routing")
    print("\n=== mixer_get_routing_all (%d tracks) ===" % routing.get("total"))
    any_to_master = False
    for tr in routing.get("routing", []):
        dests = tr.get("routes_to", [])
        ds = (
            ", ".join(
                "%d:%s%s"
                % (d["dst"], d["dst_name"], (f" @{d['level']:.3f}") if "level" in d else "")
                for d in dests
            )
            or "(none)"
        )
        print("  track %2d %-16s -> %s" % (tr["i"], repr(tr["name"]), ds))
        if any(d["dst"] == 0 for d in dests):
            any_to_master = True
    print("  default->Master visible:", any_to_master)

    # 2. single-track routing (spot check)
    show(
        "mixer_get_routing(track=%d)" % TRACK,
        bridge.call(protocol.CMD_MIXER_GET_ROUTING, {"track": TRACK}),
    )

    # 3. channel -> mixer links
    chan = fetch_all_pages(bridge, protocol.CMD_CHANNEL_ROUTING_SUMMARY, "channels")
    print("\n=== channel_routing_summary (%d channels) ===" % chan.get("total"))
    for c in chan.get("channels", []):
        print(
            "  ch %2d %-16s -> mixer %s (%s)"
            % (c["channel"], repr(c["name"]), c["target_mixer_track"], c["target_name"])
        )

    # 4. cleanup candidates -- judgement computed SERVER-SIDE from cheap reads
    # (channel summary + routing matrix + per-candidate plugin_list). The
    # controller never does a heavy single-tick scan.
    show("detect_cleanup_candidates (server-side judgement)", detect_cleanup(bridge))

    print("\nDone -- READ ONLY, nothing changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
