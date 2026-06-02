"""Project-level read-only diagnostics.

These tools aggregate existing safe primitives into high-signal reports.
"""

from __future__ import annotations

from fastmcp import FastMCP

from .. import protocol
from ..connection import fetch_all_pages, get_bridge


def _find_duplicate_names(rows: list[dict], key: str) -> list[str]:
    counts: dict[str, int] = {}
    for row in rows:
        name = str(row.get(key) or "").strip()
        if not name:
            continue
        counts[name] = counts.get(name, 0) + 1
    return sorted([name for name, c in counts.items() if c > 1])


def _suggest_pattern_name(index: int) -> str:
    return f"Pattern {index}"


def register(mcp: FastMCP) -> None:
    _RO = {
        "readOnlyHint": True,
        "idempotentHint": True,
        "openWorldHint": True,
        "safetyClass": "read-only",
    }

    @mcp.tool(annotations={"title": "Project health report", **_RO})
    def fl_project_health_report() -> dict:
        """Build a read-only project health report from safe low-level reads.

        Safety: Read-Only.
        """
        bridge = get_bridge()
        project = bridge.call(protocol.CMD_GET_PROJECT_STATE)
        channels = fetch_all_pages(bridge, protocol.CMD_CHANNEL_LIST, "channels").get(
            "channels", []
        )
        patterns = fetch_all_pages(bridge, protocol.CMD_PATTERN_LIST, "patterns").get(
            "patterns", []
        )
        playlist_tracks = fetch_all_pages(bridge, protocol.CMD_PLAYLIST_LIST_TRACKS, "tracks").get(
            "tracks", []
        )
        mixer_tracks = fetch_all_pages(bridge, protocol.CMD_MIXER_LIST_TRACKS, "tracks").get(
            "tracks", []
        )

        unassigned_channels = []
        for row in channels:
            idx = int(row.get("i", 0))
            detail = bridge.call(protocol.CMD_CHANNEL_GET, {"index": idx})
            if int(detail.get("target_fx_track", 0)) == 0:
                unassigned_channels.append({"index": idx, "name": detail.get("name", "")})

        findings = []
        if unassigned_channels:
            findings.append(
                {
                    "id": "unassigned_channels",
                    "severity": "medium",
                    "message": "Channels are still routed to Master only.",
                    "count": len(unassigned_channels),
                }
            )

        empty_pattern_names = [p for p in patterns if not str(p.get("name") or "").strip()]
        if empty_pattern_names:
            findings.append(
                {
                    "id": "unnamed_patterns",
                    "severity": "low",
                    "message": "Patterns with empty names found.",
                    "count": len(empty_pattern_names),
                }
            )

        dup_patterns = _find_duplicate_names(patterns, "name")
        if dup_patterns:
            findings.append(
                {
                    "id": "duplicate_pattern_names",
                    "severity": "low",
                    "message": "Duplicate pattern names found.",
                    "names": dup_patterns,
                }
            )

        dup_mixer = _find_duplicate_names(mixer_tracks, "name")
        if dup_mixer:
            findings.append(
                {
                    "id": "duplicate_mixer_names",
                    "severity": "low",
                    "message": "Duplicate mixer track names found.",
                    "names": dup_mixer,
                }
            )

        muted_playlist = [t for t in playlist_tracks if t.get("mute")]
        if muted_playlist:
            findings.append(
                {
                    "id": "muted_playlist_tracks",
                    "severity": "info",
                    "message": "Muted playlist tracks present (intentional or stale).",
                    "count": len(muted_playlist),
                }
            )

        return {
            "ok": True,
            "project": project,
            "summary": {
                "channels": len(channels),
                "patterns": len(patterns),
                "playlist_tracks": len(playlist_tracks),
                "mixer_tracks": len(mixer_tracks),
                "findings": len(findings),
            },
            "findings": findings,
            "details": {
                "unassigned_channels": unassigned_channels,
            },
        }

    @mcp.tool(annotations={"title": "Export readiness report", **_RO})
    def fl_export_readiness_report() -> dict:
        """Build a read-only readiness report for stem/mix export prep.

        Safety: Read-Only.
        """
        report = fl_project_health_report()
        findings = list(report.get("findings", []))
        blockers = [f for f in findings if f.get("severity") in ("high", "medium")]
        return {
            "ok": True,
            "ready": len(blockers) == 0,
            "blockers": blockers,
            "advisories": [f for f in findings if f.get("severity") in ("low", "info")],
            "source": report,
        }

    @mcp.tool(annotations={"title": "Project dry-run fix plan", **_RO})
    def fl_project_dry_run_fix_plan(
        include_low_priority: bool = True,
    ) -> dict:
        """Build a read-only, ordered fix plan over existing rollback-safe tools.

        Safety: Read-Only.
        """
        report = fl_project_health_report()
        findings = list(report.get("findings", []))
        details = report.get("details", {})
        channels = fetch_all_pages(get_bridge(), protocol.CMD_CHANNEL_LIST, "channels").get(
            "channels", []
        )
        patterns = fetch_all_pages(get_bridge(), protocol.CMD_PATTERN_LIST, "patterns").get(
            "patterns", []
        )
        playlist_tracks = fetch_all_pages(
            get_bridge(), protocol.CMD_PLAYLIST_LIST_TRACKS, "tracks"
        ).get("tracks", [])

        actions = []
        action_id = 1

        unassigned = details.get("unassigned_channels", [])
        for row in unassigned:
            actions.append(
                {
                    "id": action_id,
                    "priority": "high",
                    "kind": "channel_routing",
                    "tool": "fl_assign_channel_to_free_mixer_track",
                    "params": {"channel": int(row["index"])},
                    "reason": "Channel is routed to Master only.",
                    "rollback": "single safe_write entry",
                }
            )
            action_id += 1

        if include_low_priority:
            unnamed = [p for p in patterns if not str(p.get("name") or "").strip()]
            for p in unnamed:
                idx = int(p.get("index", p.get("pattern", 0)))
                if idx <= 0:
                    continue
                actions.append(
                    {
                        "id": action_id,
                        "priority": "low",
                        "kind": "pattern_naming",
                        "tool": "fl_pattern_rename",
                        "params": {"index": idx, "name": _suggest_pattern_name(idx)},
                        "reason": "Pattern has an empty name.",
                        "rollback": "single safe_write entry",
                    }
                )
                action_id += 1

            duplicate_patterns = _find_duplicate_names(patterns, "name")
            for name in duplicate_patterns:
                dup_rows = [p for p in patterns if str(p.get("name") or "").strip() == name]
                for row in dup_rows[1:]:
                    idx = int(row.get("index", row.get("pattern", 0)))
                    if idx <= 0:
                        continue
                    actions.append(
                        {
                            "id": action_id,
                            "priority": "low",
                            "kind": "pattern_deduplicate",
                            "tool": "fl_pattern_rename",
                            "params": {"index": idx, "name": f"{name} ({idx})"},
                            "reason": "Pattern name duplicates another pattern.",
                            "rollback": "single safe_write entry",
                        }
                    )
                    action_id += 1

            muted_tracks = [t for t in playlist_tracks if t.get("mute")]
            for row in muted_tracks:
                actions.append(
                    {
                        "id": action_id,
                        "priority": "low",
                        "kind": "playlist_review",
                        "tool": "fl_playlist_set_mute",
                        "params": {"index": int(row["index"]), "state": False},
                        "reason": "Track is muted. Unmute only if mute is stale.",
                        "rollback": "single safe_write entry",
                        "manual_review": True,
                    }
                )
                action_id += 1

        actionable = [a for a in actions if a.get("priority") in ("high", "medium")]
        if include_low_priority:
            actionable = actions

        readiness = fl_export_readiness_report()
        return {
            "ok": True,
            "dry_run": True,
            "summary": {
                "findings": len(findings),
                "planned_actions": len(actions),
                "channels_scanned": len(channels),
                "patterns_scanned": len(patterns),
                "playlist_tracks_scanned": len(playlist_tracks),
            },
            "source_report": {
                "ready": readiness.get("ready"),
                "blockers": readiness.get("blockers"),
            },
            "plan": actionable,
            "notes": [
                "This tool is read-only and applies no FL changes.",
                "Execute one action at a time and verify readback before the next write.",
                "Use fl_rollback_last_change immediately if a write result is unexpected.",
            ],
        }
