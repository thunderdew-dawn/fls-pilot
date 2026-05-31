#!/usr/bin/env python3
"""Offline test: chains.plan_chain recipe -> existing-plugin matching (no FL).

python scripts/test_chains.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp.music import chains as ch  # noqa: E402

_P = _F = 0


def check(label, cond, detail=""):
    global _P, _F
    _P += 1 if cond else 0
    _F += 0 if cond else 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}{'  -- ' + detail if detail else ''}")


def main() -> int:
    eq = {"slot": 0, "name": "Fruity Parametric EQ 2"}
    comp = {"slot": 1, "name": "FabFilter Pro-C 3"}

    # vocal with EQ + comp but NO reverb -> reverb step missing.
    plan = ch.plan_chain("vocal", [eq, comp])
    roles = [s["role"] for s in plan["steps"]]
    miss = [m["role"] for m in plan["missing"]]
    check(
        "vocal: EQ steps -> EQ slot 0",
        all(s["slot"] == 0 for s in plan["steps"] if s["kind"] == "eq"),
    )
    check(
        "vocal: comp -> comp slot 1",
        any(s["kind"] == "comp" and s["slot"] == 1 for s in plan["steps"]),
    )
    check("vocal: reverb step MISSING (no reverb loaded)", "space" in miss, str(miss))
    check(
        "vocal: HP/presence/air present",
        {"high-pass", "presence", "air"}.issubset(set(roles)),
        str(roles),
    )
    check(
        "steps carry valid tool + intent",
        all(s["tool"].startswith("fl_apply_") and s["intent"] for s in plan["steps"]),
    )

    bad = ch.plan_chain("nonsense", [eq])
    check(
        "unknown chain_type -> ok False + available list",
        bad["ok"] is False and "vocal" in bad.get("available", []),
    )

    empty = ch.plan_chain("drum_bus", [])
    check(
        "no plugins -> 0 steps, all missing",
        len(empty["steps"]) == 0 and len(empty["missing"]) == 3,
        str(empty["missing"]),
    )

    check("describe() lists all recipes", set(ch.describe()) == set(ch.available()))

    print("\n%d passed, %d failed" % (_P, _F))
    return 0 if _F == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
