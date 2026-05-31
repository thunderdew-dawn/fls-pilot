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


def register(mcp: FastMCP) -> None:
    _RO = {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": True}

    @mcp.tool(annotations={"title": "Project health report", **_RO})
    def fl_project_health_report() -> dict:
        """Build a read-only project health report from safe low-level reads."""
        bridge = get_bridge()
        project = bridge.call(protocol.CMD_GET_PROJECT_STATE)
        channels = fetch_all_pages(bridge, protocol.CMD_CHANNEL_LIST, "channels").get("channels", [])
        patterns = fetch_all_pages(bridge, protocol.CMD_PATTERN_LIST, "patterns").get("patterns", [])
        playlist_tracks = fetch_all_pages(bridge, protocol.CMD_PLAYLIST_LIST_TRACKS, "tracks").get(
            "tracks", []
        )
        mixer_tracks = fetch_all_pages(bridge, protocol.CMD_MIXER_LIST_TRACKS, "tracks").get("tracks", [])

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
        """Build a read-only readiness report for stem/mix export prep."""
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
