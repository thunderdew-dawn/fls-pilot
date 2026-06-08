"""Target validation helpers for dynamic FL Studio project state."""

from __future__ import annotations

from .. import protocol


def mixer_track_count(bridge) -> int | None:
    """Return the current dynamic mixer-track count when FL exposes it."""
    try:
        value = bridge.call(protocol.CMD_GET_PROJECT_STATE).get("mixer_track_count")
        count = int(value)
    except Exception:
        return None
    return count if count >= 0 else None


def mixer_track_error(
    bridge,
    track: int,
    *,
    allow_master: bool = True,
    purpose: str = "mixer operation",
) -> dict | None:
    """Return an MCP-friendly error when ``track`` is outside current project bounds."""
    count = mixer_track_count(bridge)
    if count is None:
        return None
    if track < 0 or (not allow_master and track == 0) or track >= count:
        highest = max(0, count - 1)
        return {
            "ok": False,
            "error": f"mixer track {track} is not available in this project",
            "purpose": purpose,
            "mixer_track_count": count,
            "valid_range": {"min": 0 if allow_master else 1, "max": highest},
            "dynamic_mixer_tracks": True,
            "note": (
                "FL Studio projects can expose fewer mixer tracks until tracks are created "
                "inside FL. This is a target/fixture issue, not evidence that the API failed."
            ),
        }
    return None


def no_free_mixer_track_response(bridge, *, start_track: int) -> dict:
    count = mixer_track_count(bridge)
    return {
        "ok": False,
        "error": "no default empty mixer track found",
        "mixer_track_count": count,
        "start_track": start_track,
        "requires_mixer_track_creation": True,
        "probe_needed": True,
        "manual_action": "Create or reveal another mixer track in FL Studio, then retry.",
        "note": (
            "This tool only assigns channels to existing empty mixer tracks. "
            "Creating dynamic mixer tracks is not exposed as a user-facing write "
            "until a rollback-safe Image-Line API path is live-probed."
        ),
    }
