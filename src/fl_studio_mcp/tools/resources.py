"""MCP resources -- read-only project context the LLM assistant can pull WITHOUT a tool call.

All reuse existing (budget-paginated) reads, so no new heavy controller loops.
Kept COMPACT: summaries + counts, capped, with a note pointing to the detail
tool when a list is large. Every resource degrades gracefully if the bridge is
down (returns an {error} dict instead of throwing) so an auto-pull never breaks.
"""

from __future__ import annotations

from fastmcp import FastMCP

from .. import protocol
from ..connection import fetch_all_pages, get_bridge

_CAPS = {
    "channels": 24,
    "tracks": 28,
    "patterns": 80,
}


def _safe(fn):
    try:
        return fn()
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def _summary(full, key, detail_tool):
    items = full.get(key) or []
    total = full.get("total", len(items))
    cap = _CAPS.get(key, 24)
    out = {"total": total, "shown": min(len(items), cap), key: items[:cap]}
    if len(items) > cap:
        out["truncated"] = True
        out["note"] = f"showing first {cap} of {total} -- call {detail_tool} for the rest"
    return out


def register(mcp: FastMCP) -> None:

    @mcp.resource("fl://status")
    def status() -> dict:
        """Bridge alive + a cheap transport/tempo snapshot."""

        def _do():
            b = get_bridge()
            wait = getattr(b, "wait_for_heartbeat", None)
            if callable(wait):
                wait(timeout=1.0)
            alive = b.is_alive()
            out = {"alive": alive, "heartbeat_age_seconds": b.heartbeat_age() if alive else None}
            if alive:
                ps = b.call(protocol.CMD_GET_PROJECT_STATE)
                out.update(
                    {
                        "fl_version": ps.get("fl_version"),
                        "tempo_bpm": ps.get("tempo_bpm"),
                        "playing": ps.get("playing"),
                    }
                )
            return out

        return _safe(_do)

    @mcp.resource("fl://project")
    def project() -> dict:
        """Tempo, transport, and channel/mixer/pattern counts."""
        return _safe(lambda: get_bridge().call(protocol.CMD_GET_PROJECT_STATE))

    @mcp.resource("fl://transport")
    def transport() -> dict:
        """Live transport: playing/recording, song position, tempo."""

        def _do():
            b = get_bridge()
            out = dict(b.call(protocol.CMD_GET_PLAY_STATE))
            out["song_position"] = b.call(protocol.CMD_GET_SONG_POS)
            out["tempo"] = b.call(protocol.CMD_GET_TEMPO)
            return out

        return _safe(_do)

    @mcp.resource("fl://channels")
    def channels() -> dict:
        """Channel-rack summary (name + vol/pan/mute/solo), capped."""
        return _safe(
            lambda: _summary(
                fetch_all_pages(get_bridge(), protocol.CMD_CHANNEL_LIST, "channels"),
                "channels",
                "fl_get_channel_state",
            )
        )

    @mcp.resource("fl://mixer")
    def mixer() -> dict:
        """Mixer-track summary (name + vol/pan/mute/solo), capped."""
        return _safe(
            lambda: _summary(
                fetch_all_pages(get_bridge(), protocol.CMD_MIXER_LIST_TRACKS, "tracks"),
                "tracks",
                "fl_get_mixer_state",
            )
        )

    @mcp.resource("fl://patterns")
    def patterns() -> dict:
        """Pattern list (1-based index + name), capped."""
        return _safe(
            lambda: _summary(
                fetch_all_pages(get_bridge(), protocol.CMD_PATTERN_LIST, "patterns"),
                "patterns",
                "fl_get_project_state",
            )
        )
