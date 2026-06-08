#!/usr/bin/env python3
"""Verify the canonical GitHub Project issue fingerprint via gh CLI."""

from __future__ import annotations

import json
import subprocess

OWNER = "thunderdew-dawn"
PROJECT = "7"
EXPECTED = {
    "items": {"min": 3, "max": 48, "count": 46},
    "lanes": {"Now": 2, "Next": 3, "Later": 33, "Done": 8},
    "statuses": {"Todo": 36, "Next": 2, "Done": 8},
    "priorities": {"P0": 3, "P1": 6, "P2": 25, "P3": 12},
}


def _gh_json(*args: str) -> dict:
    result = subprocess.run(
        ["gh", *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return json.loads(result.stdout)


def _count(values: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        if value:
            out[value] = out.get(value, 0) + 1
    return out


def main() -> int:
    data = _gh_json(
        "project",
        "item-list",
        PROJECT,
        "--owner",
        OWNER,
        "--limit",
        "100",
        "--format",
        "json",
    )
    items = data.get("items", [])
    numbers = sorted(int(item["content"]["number"]) for item in items)
    observed = {
        "items": {"min": min(numbers), "max": max(numbers), "count": len(numbers)},
        "lanes": _count([item.get("roadmap Lane", "") for item in items]),
        "statuses": _count([item.get("status", "") for item in items]),
        "priorities": _count([item.get("priority", "") for item in items]),
    }
    if observed != EXPECTED:
        print(json.dumps({"expected": EXPECTED, "observed": observed}, indent=2))
        return 1
    print(json.dumps(observed, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
