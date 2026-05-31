"""Channel organizer tools.

This module contains channel-level organization primitives that are higher
level than the Phase 1 volume/pan/mute/solo setters but still small enough to
be audited and rolled back individually.
"""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from .. import protocol, safety
from ..connection import fetch_all_pages, get_bridge


def _target_restore(channel: int, before: dict) -> dict:
    previous = before.get("target_fx_track")
    if not isinstance(previous, int):
        raise RuntimeError("cannot build rollback: previous channel target is unknown")
    return {
        "command": protocol.CMD_CHANNEL_SET_TARGET,
        "params": {"channel": channel, "track": previous},
    }


def _needs_assignment(channel: dict, *, include_master: bool = True) -> bool:
    target = channel.get("target_fx_track")
    if not isinstance(target, int):
        return True
    return include_master and target == 0


def _is_default_mixer_name(index: int, name) -> bool:
    if index == 0:
        return False
    return (name or "") in ("", f"Insert {index}")


def _find_free_mixer_track(bridge, *, start_track: int = 1) -> int | None:
    routing = fetch_all_pages(bridge, protocol.CMD_MIXER_GET_ROUTING_ALL, "routing")
    channels = fetch_all_pages(bridge, protocol.CMD_CHANNEL_ROUTING_SUMMARY, "channels")

    targeted = {
        c.get("target_mixer_track")
        for c in channels.get("channels", [])
        if isinstance(c.get("target_mixer_track"), int)
    }
    incoming: dict[int, list[int]] = {}
    for row in routing.get("routing", []):
        for route in row.get("routes_to", []):
            dst = route.get("dst")
            if isinstance(dst, int):
                incoming.setdefault(dst, []).append(row.get("i"))

    for row in routing.get("routing", []):
        track = row.get("i")
        if not isinstance(track, int) or track < start_track:
            continue
        if track == 0 or track in targeted or incoming.get(track):
            continue
        if not _is_default_mixer_name(track, row.get("name")):
            continue
        try:
            if bridge.call(protocol.CMD_PLUGIN_LIST, {"track": track}).get("slots"):
                continue
        except Exception:
            continue
        return track
    return None


def register(mcp: FastMCP) -> None:
    _RO = {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": True}
    _WR = {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }

    @mcp.tool(annotations={"title": "Get channel details", **_RO})
    def fl_get_channel_details(
        channel: Annotated[int, Field(ge=0, description="Channel-rack channel index.")],
    ) -> dict:
        """Read full details for one channel, including type, color, and mixer target."""
        return get_bridge().call(protocol.CMD_CHANNEL_GET, {"index": channel})

    @mcp.tool(annotations={"title": "Detect channels needing mixer assignment", **_RO})
    def fl_detect_unassigned_channels(
        include_master: Annotated[
            bool,
            Field(description="Treat channels routed only to Master as assignment candidates."),
        ] = True,
    ) -> dict:
        """Find channels with no mixer target, or optionally channels still routed to Master."""
        bridge = get_bridge()
        listed = fetch_all_pages(bridge, protocol.CMD_CHANNEL_LIST, "channels")
        candidates = []
        for item in listed.get("channels", []):
            detail = bridge.call(protocol.CMD_CHANNEL_GET, {"index": item.get("i", 0)})
            if _needs_assignment(detail, include_master=include_master):
                candidates.append(detail)
        return {"ok": True, "total": len(candidates), "channels": candidates}

    @mcp.tool(annotations={"title": "Set channel name", **_WR})
    def fl_set_channel_name(
        channel: Annotated[int, Field(ge=0, description="Channel-rack channel index.")],
        name: Annotated[str, Field(min_length=1, description="New channel name.")],
    ) -> dict:
        """Rename a channel. Snapshot + readback; rollback restores the prior name."""
        return safety.safe_write(
            get_bridge(),
            tool="channel_set_name",
            scope=f"channel:{channel}",
            command=protocol.CMD_CHANNEL_SET_NAME,
            params={"channel": channel, "name": name},
            build_restore=lambda b: {
                "command": protocol.CMD_CHANNEL_SET_NAME,
                "params": {"channel": channel, "name": b["name"]},
            },
        )

    @mcp.tool(annotations={"title": "Set channel mixer target", **_WR})
    def fl_set_channel_mixer_track(
        channel: Annotated[int, Field(ge=0, description="Channel-rack channel index.")],
        mixer_track: Annotated[int, Field(ge=0, description="Target mixer track index.")],
    ) -> dict:
        """Route a channel to a mixer track. Rollback restores the previous target."""
        return safety.safe_write(
            get_bridge(),
            tool="channel_set_target",
            scope=f"channel:{channel}",
            command=protocol.CMD_CHANNEL_SET_TARGET,
            params={"channel": channel, "track": mixer_track},
            verify=("target_fx_track", mixer_track),
            build_restore=lambda b: _target_restore(channel, b),
        )

    @mcp.tool(annotations={"title": "Assign channel to a free mixer track", **_WR})
    def fl_assign_channel_to_free_mixer_track(
        channel: Annotated[int, Field(ge=0, description="Channel-rack channel index.")],
        start_track: Annotated[int, Field(ge=1, description="First mixer track to consider.")] = 1,
    ) -> dict:
        """Find a default empty mixer track and route this channel to it.

        This does not rename or color the mixer track; it only changes the
        channel's mixer target so rollback remains one small restore.
        """
        bridge = get_bridge()
        track = _find_free_mixer_track(bridge, start_track=start_track)
        if track is None:
            return {"ok": False, "error": "no default empty mixer track found"}
        result = safety.safe_write(
            bridge,
            tool="channel_assign_free_mixer_track",
            scope=f"channel:{channel}",
            command=protocol.CMD_CHANNEL_SET_TARGET,
            params={"channel": channel, "track": track},
            verify=("target_fx_track", track),
            build_restore=lambda b: _target_restore(channel, b),
        )
        return {"ok": True, "assigned_track": track, "result": result}
