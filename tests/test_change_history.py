#!/usr/bin/env python3
"""Offline tests for MCP changelog and targeted rollback behavior.

No FL Studio connection is needed. The fake bridge records restore calls so we
can verify safety semantics without mutating a project.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp import safety  # noqa: E402

_P = _F = 0


class FakeBridge:
    def __init__(self) -> None:
        self.calls = []

    def call(self, command, params=None):
        params = params or {}
        self.calls.append((command, params))
        return {"ok": True, "command": command, "params": params}


def check(label, cond, detail=""):
    global _P, _F
    _P += 1 if cond else 0
    _F += 0 if cond else 1
    status = "PASS" if cond else "FAIL"
    suffix = f" -- {detail}" if detail else ""
    print(f"  [{status}] {label}{suffix}")


def main() -> int:
    original_log = safety._log
    try:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "changelog.jsonl"
            log = safety.ChangeLog(path=path, max_entries=10)
            safety._log = log

            e1 = log.append(
                {
                    "tool": "first_write",
                    "scope": "mixer_track:1",
                    "restore": {"command": "restore_first", "params": {"value": 1}},
                }
            )
            e2 = log.append(
                {
                    "tool": "second_write",
                    "scope": "mixer_track:2",
                    "restore": {"command": "restore_second", "params": {"value": 2}},
                }
            )

            check(
                "change ids are generated",
                e1["change_id"].startswith("chg_") and e2["change_id"].startswith("chg_"),
            )
            check("change ids are unique", e1["change_id"] != e2["change_id"])

            summaries = log.recent(2)
            check(
                "recent summaries omit restore payload",
                "restore" not in summaries[0] and summaries[0]["tool"] == "first_write",
            )
            check(
                "recent summaries expose rollback unit",
                summaries[0]["rollback_unit"] == "first_write",
            )
            payload = log.recent(1, include_payload=True)
            check(
                "payload view includes restore",
                payload[0]["restore"]["command"] == "restore_second",
            )

            export_path = Path(tmp) / "export.json"
            exported = log.export(str(export_path), include_payload=False)
            exported_json = json.loads(export_path.read_text(encoding="utf-8"))
            check(
                "export writes requested JSON file",
                exported["path"] == str(export_path) and exported_json["count"] == 2,
            )

            bridge = FakeBridge()
            non_lifo = safety.rollback_change(bridge, e1["change_id"])
            check(
                "rollback by id refuses older non-LIFO entry",
                non_lifo["ok"] is False and "non-LIFO" in non_lifo["error"],
            )
            check("non-LIFO refusal does not call bridge", bridge.calls == [])

            latest = safety.rollback_change(bridge, e2["change_id"])
            check(
                "rollback by id accepts latest entry",
                latest["ok"] is True and latest["change_id"] == e2["change_id"],
            )
            check(
                "latest rollback replays restore",
                bridge.calls[-1] == ("restore_second", {"value": 2}),
            )

            last = safety.rollback_last_change(bridge)
            check(
                "rollback last handles remaining legacy path",
                last["ok"] is True and last["change_id"] == e1["change_id"],
            )

            group = log.append(
                {
                    "tool": "group_write",
                    "rollback_unit": "named_group",
                    "scope": "mixer:bulk",
                    "group": True,
                    "restores": [
                        {"command": "restore_first_in_group", "params": {"order": 1}},
                        {"command": "restore_second_in_group", "params": {"order": 2}},
                    ],
                }
            )
            group_summary = log.recent(1)[0]
            check(
                "group summary exposes explicit rollback unit",
                group_summary["rollback_unit"] == "named_group",
            )
            group_result = safety.rollback_change(bridge, group["change_id"])
            check("group rollback succeeds", group_result["ok"] is True)
            check(
                "group rollback replays restores in reverse order",
                bridge.calls[-2:]
                == [
                    ("restore_second_in_group", {"order": 2}),
                    ("restore_first_in_group", {"order": 1}),
                ],
            )
    finally:
        safety._log = original_log

    print(f"\n{_P} passed, {_F} failed")
    return 0 if _F == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
