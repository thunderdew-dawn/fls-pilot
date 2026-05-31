#!/usr/bin/env python3
"""Mix Doctor Stage 2: gated apply-fixes (propose -> approve -> apply -> rollback).

STRICTLY one fix at a time, each shown EXACTLY before applying. No batch, no
auto-apply. Apply + rollback go through safety.safe_write -> snapshot + readback
+ rollback-able. Reuses the existing mixer-volume command + the safety layer.

    python scripts/mix_doctor_fix.py                # propose (READ-ONLY) + save plans
    python scripts/mix_doctor_fix.py --apply 1      # apply approved fix #1 (the saved exact params)
    python scripts/mix_doctor_fix.py --rollback     # undo the last applied change
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import contextlib

from fl_studio_mcp import protocol, safety  # noqa: E402
from fl_studio_mcp.connection import get_bridge, reset_bridge  # noqa: E402
from fl_studio_mcp.music import mix_doctor as md  # noqa: E402

PLAN_FILE = Path.home() / ".flstudio-mcp" / "mix_doctor_plans.json"


def connect():
    order = (
        [os.environ["FLSTUDIO_MCP_TRANSPORT"]]
        if os.environ.get("FLSTUDIO_MCP_TRANSPORT")
        else ["tcp", "direct"]
    )
    for t in order:
        os.environ["FLSTUDIO_MCP_TRANSPORT"] = t
        reset_bridge()
        try:
            b = get_bridge()
            if b.is_alive():
                return b, t
        except Exception as e:
            print(f"  transport {t:6} unavailable: {type(e).__name__}: {e}")
    return None, None


def do_propose(bridge):
    t0 = time.time()
    snap = md.gather_snapshot(bridge)
    plan = md.plan_fixes(snap)
    PLAN_FILE.parent.mkdir(parents=True, exist_ok=True)
    PLAN_FILE.write_text(json.dumps(plan["plans"], indent=2), encoding="utf-8")

    print("=== Mix Doctor fix proposals (READ-ONLY) ===")
    print(
        "playing: {}   gathered in {:.2f}s   (peaks {})".format(
            snap["playing"], time.time() - t0, "sustained" if snap["playing"] else "skipped/stopped"
        )
    )
    for n in plan["notes"]:
        print("NOTE:", n)
    print()
    if not plan["plans"]:
        print("no fix plans (nothing actionable, or project stopped -> no level data).")
    for p in plan["plans"]:
        tag = "APPLY-ABLE" if p.get("actionable") else "not-yet"
        print("[%d] (%s) %s -- %s" % (p["id"], tag, p["kind"], p["human"]))
        print(f"     why: {p.get('reason', '')}")
        if p.get("actionable"):
            print(f"     exact write: {p['command']} {p['params']}")
    print("\nApprove one -> python scripts/mix_doctor_fix.py --apply <id>")
    print("Nothing applied. One fix at a time; each needs your explicit ok.")
    return 0


def do_apply(bridge, fix_id):
    if not PLAN_FILE.exists():
        print("no saved plans -- run propose first.")
        return 1
    plans = json.loads(PLAN_FILE.read_text(encoding="utf-8"))
    plan = next((p for p in plans if p["id"] == fix_id), None)
    if plan is None:
        print("no plan with id", fix_id)
        return 1
    if not plan.get("actionable"):
        print("plan %d (%s) is not wired for apply yet." % (fix_id, plan["kind"]))
        return 1
    print("applying fix [%d]: %s" % (fix_id, plan["human"]))
    rf = plan["restore_field"]
    res = safety.safe_write(
        bridge,
        tool=plan["tool"],
        scope=plan["scope"],
        command=plan["command"],
        params=plan["params"],
        build_restore=lambda b, p=plan, rf=rf: {
            "command": p["command"],
            "params": {"track": p["params"]["track"], "value": b[rf], "unit": "normalized"},
        },
    )
    before = res.get("before") or {}
    # The set handler reads back in the SAME tick -> stale (FL coalesces). Confirm
    # the true applied state with a FRESH read on a separate tick.
    track = plan["params"]["track"]
    fresh = bridge.call(protocol.CMD_MIXER_GET_TRACK, {"index": track})
    print(
        "  before         : vol_db={}  vol_norm={}".format(
            before.get("vol_db"), before.get("vol_norm")
        )
    )
    print(
        "  applied (fresh): vol_db={}  vol_norm={}".format(
            fresh.get("vol_db"), fresh.get("vol_norm")
        )
    )
    tgt = plan.get("target_fader_db")
    if fresh.get("vol_db") is not None and tgt is not None:
        ok = abs(fresh["vol_db"] - tgt) <= 0.6
        print(f"  readback {'MATCHES' if ok else 'DIFFERS from'} target {tgt:.1f} dB")
    print("\nUndo:  python scripts/mix_doctor_fix.py --rollback")
    return 0


def do_rollback(bridge):
    res = safety.rollback_last_change(bridge)
    print("rollback:", json.dumps(res, default=str)[:300])
    scope = res.get("scope") or ""
    if scope.startswith("mixer_track:"):  # fresh read (avoids same-tick stale echo)
        idx = int(scope.split(":")[1])
        fresh = bridge.call(protocol.CMD_MIXER_GET_TRACK, {"index": idx})
        print(
            "  restored (fresh): {}  vol_db={}  vol_norm={}".format(
                fresh.get("name"), fresh.get("vol_db"), fresh.get("vol_norm")
            )
        )
    return 0 if res.get("ok") else 1


def main() -> int:
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    bridge, transport = connect()
    if bridge is None:
        print("FL bridge NOT reachable. Open FL + bring up the MCP bridge.")
        return 1
    print(f"connected via {transport}.\n")
    if "--apply" in sys.argv:
        return do_apply(bridge, int(sys.argv[sys.argv.index("--apply") + 1]))
    if "--rollback" in sys.argv:
        return do_rollback(bridge)
    return do_propose(bridge)


if __name__ == "__main__":
    sys.exit(main())
