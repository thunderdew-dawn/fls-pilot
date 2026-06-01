"""Phase 4 MCP tools -- author notes, chords, and apply transformations into FL's piano roll.

Uses the generate-script bridge: since FL's controller API cannot directly read or write
notes, we generate a .pyscript with note data or actions baked in, write it to the Piano Roll
scripts folder, and send Ctrl+Alt+Y (Cmd+Opt+Y on macOS) to trigger it.
Requires a one-time arm: run "MCP Apply" once from the Piano Roll Scripting menu.
"""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from .. import protocol, safety
from ..connection import get_bridge
from ..music.scales import parse_root_note
from ..pyscript_gen import quantize_notes


class PianoRollNote(BaseModel):
    pitch: int = Field(ge=0, le=127, description="MIDI note (60 = middle C; FL displays it as C5).")
    time_bars: float = Field(0.0, ge=0.0, description="Start, in bars from the pattern start.")
    length_bars: float = Field(1.0, gt=0.0, description="Duration in bars.")
    velocity: float = Field(
        100 / 127.0, ge=0.0, le=1.0, description="0.0-1.0 (0.787 ~= MIDI velocity 100)."
    )


CHORD_TEMPLATES = {
    "maj": [0, 4, 7],
    "major": [0, 4, 7],
    "": [0, 4, 7],
    "min": [0, 3, 7],
    "minor": [0, 3, 7],
    "m": [0, 3, 7],
    "7": [0, 4, 7, 10],
    "dom7": [0, 4, 7, 10],
    "maj7": [0, 4, 7, 11],
    "m7": [0, 3, 7, 10],
    "min7": [0, 3, 7, 10],
    "m7b5": [0, 3, 6, 10],
    "halfdim": [0, 3, 6, 10],
    "dim7": [0, 3, 6, 9],
    "dim": [0, 3, 6, 9],
    "aug": [0, 4, 8],
    "sus4": [0, 5, 7],
    "sus2": [0, 2, 7],
    "9": [0, 4, 7, 10, 14],
    "maj9": [0, 4, 7, 11, 14],
    "m9": [0, 3, 7, 10, 14],
    "min9": [0, 3, 7, 10, 14],
}


def _target_payload(channel: int | None, pattern: int | None) -> dict:
    payload = {}
    if channel is not None:
        payload["channel"] = int(channel)
    if pattern is not None:
        payload["pattern"] = int(pattern)
    return payload


def _ensure_piano_roll(bridge, channel: int | None, pattern: int | None) -> dict:
    return bridge.call(protocol.CMD_ENSURE_PIANO_ROLL, _target_payload(channel, pattern))


def register(mcp: FastMCP) -> None:
    _RO = {
        "readOnlyHint": True,
        "idempotentHint": True,
        "openWorldHint": True,
        "safetyClass": "read-only",
    }
    _WR = {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
        "safetyClass": "write-safe",
    }

    # ---- Legacy Tool Names (Aliased/Kept for Backwards Compatibility) -------

    @mcp.tool(
        annotations={
            "title": "Write piano-roll notes (legacy)",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
            "safetyClass": "write-safe",
        }
    )
    def fl_write_piano_roll_notes(
        notes: list[PianoRollNote],
        mode: Annotated[
            str,
            Field(description="'replace' clears first; 'append' adds."),
        ] = "replace",
        quantize: Annotated[float, Field(description="Quantization grid in bars.")] = 0.0,
    ) -> dict:
        """Legacy write notes wrapper. Use fl_piano_write_notes instead.

        Safety: Write-Safe with Rollback. Piano Roll writes are undo-backed;
        note readback to MCP remains API-limited.
        """
        return fl_piano_write_notes(notes, mode, quantize)

    @mcp.tool(annotations={"title": "Quantize piano-roll notes (legacy)", **_WR})
    def fl_quantize_pattern(
        grid_bars: Annotated[float, Field(gt=0, description="Snap resolution.")] = 0.0625,
        snap_ends: Annotated[bool, Field(description="Snap note lengths.")] = False,
    ) -> dict:
        """Legacy quantize wrapper. Use fl_piano_quantize instead.

        Safety: Write-Safe with Rollback. Piano Roll writes are undo-backed;
        note readback to MCP remains API-limited.
        """
        return fl_piano_quantize(grid_bars, snap_ends)

    # ---- Phase 4 First-Class Piano Roll Tools -------------------------------

    @mcp.tool(
        annotations={
            "title": "Write notes to Piano roll",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
            "safetyClass": "write-safe",
        }
    )
    def fl_piano_write_notes(
        notes: list[PianoRollNote],
        mode: Annotated[
            str,
            Field(description="'replace' clears the pattern first; 'append' adds to it."),
        ] = "replace",
        quantize: Annotated[
            float,
            Field(description="Optional grid (bars) to snap note starts to: 0.0625=1/16, 0=off."),
        ] = 0.0,
        channel: Annotated[
            int | None,
            Field(ge=0, description="Optional channel-rack index to retarget before writing."),
        ] = None,
        pattern: Annotated[
            int | None,
            Field(ge=1, description="Optional FL pattern index to select before writing."),
        ] = None,
    ) -> dict:
        """Write notes into the currently active pattern's Piano roll.

        Safety: Write-Safe with Rollback. The generated Piano Roll script uses
        FL undo for rollback; note readback to MCP remains API-limited.
        """
        arr = [n.model_dump() for n in notes]
        if quantize and quantize > 0:
            arr = quantize_notes(arr, float(quantize))
        bridge = get_bridge()
        _ensure_piano_roll(bridge, channel, pattern)

        return safety.safe_piano_roll_write(
            bridge,
            tool="piano_write_notes",
            params={
                "notes": arr,
                "mode": mode,
                "quantize": quantize,
                **_target_payload(channel, pattern),
            },
            apply=lambda: bridge.apply_notes(arr, mode, channel=channel, pattern=pattern),
        )

    @mcp.tool(annotations={"title": "Write chord to Piano roll", **_WR})
    def fl_piano_write_chord(
        chord_name: Annotated[
            str,
            Field(description="Chord type, for example 'maj7', 'min7', 'sus4', 'm9'."),
        ],
        root_note: Annotated[
            str | int,
            Field(description="Root note as name or MIDI number."),
        ],
        time_bars: Annotated[
            float,
            Field(ge=0.0, description="Start in bars from pattern start."),
        ] = 0.0,
        length_bars: Annotated[float, Field(gt=0.0, description="Duration in bars.")] = 1.0,
        velocity: Annotated[
            float,
            Field(ge=0.0, le=1.0, description="Velocity 0-1."),
        ] = 100 / 127.0,
        mode: Annotated[
            str,
            Field(description="'replace' clears first; 'append' adds."),
        ] = "append",
        channel: Annotated[
            int | None,
            Field(ge=0, description="Optional channel-rack index to retarget before writing."),
        ] = None,
        pattern: Annotated[
            int | None,
            Field(ge=1, description="Optional FL pattern index to select before writing."),
        ] = None,
    ) -> dict:
        """Write a named chord into the Piano roll at the active pattern.

        Safety: Write-Safe with Rollback. The generated Piano Roll script uses
        FL undo for rollback; note readback to MCP remains API-limited.
        """
        try:
            root = parse_root_note(root_note)
        except ValueError as e:
            return {"ok": False, "error": f"Invalid root note: {e}"}

        chord_type = chord_name.strip().lower()
        if chord_type not in CHORD_TEMPLATES:
            return {
                "ok": False,
                "error": (
                    f"Unknown chord type: {chord_name!r}. "
                    f"Supported types: {list(CHORD_TEMPLATES.keys())}"
                ),
            }

        intervals = CHORD_TEMPLATES[chord_type]
        chord_notes = []
        for offset in intervals:
            pitch = root + offset
            if 0 <= pitch <= 127:
                chord_notes.append(
                    {
                        "pitch": pitch,
                        "time_bars": float(time_bars),
                        "length_bars": float(length_bars),
                        "velocity": float(velocity),
                    }
                )

        bridge = get_bridge()
        _ensure_piano_roll(bridge, channel, pattern)

        return safety.safe_piano_roll_write(
            bridge,
            tool="piano_write_chord",
            params={
                "chord_name": chord_name,
                "root_note": root_note,
                "time_bars": time_bars,
                "length_bars": length_bars,
                "velocity": velocity,
                "mode": mode,
                **_target_payload(channel, pattern),
            },
            apply=lambda: bridge.apply_notes(chord_notes, mode, channel=channel, pattern=pattern),
        )

    @mcp.tool(annotations={"title": "Clear all notes in Piano roll", **_WR})
    def fl_piano_clear(
        channel: Annotated[
            int | None,
            Field(ge=0, description="Optional channel-rack index to retarget before clearing."),
        ] = None,
        pattern: Annotated[
            int | None,
            Field(ge=1, description="Optional FL pattern index to select before clearing."),
        ] = None,
    ) -> dict:
        """Clear all notes in the currently active pattern's Piano roll.

        Safety: Write-Safe with Rollback. The generated Piano Roll script uses
        FL undo for rollback; note readback to MCP remains API-limited.
        """
        bridge = get_bridge()
        _ensure_piano_roll(bridge, channel, pattern)
        return safety.safe_piano_roll_write(
            bridge,
            tool="piano_clear",
            params=_target_payload(channel, pattern),
            apply=lambda: bridge.apply_notes([], mode="replace", channel=channel, pattern=pattern),
        )

    @mcp.tool(annotations={"title": "Quantize piano-roll notes", **_WR})
    def fl_piano_quantize(
        grid_bars: Annotated[
            float, Field(gt=0, description="Snap grid in bars: 0.0625=1/16, 0.125=1/8, 0.25=1/4.")
        ] = 0.0625,
        snap_ends: Annotated[
            bool, Field(description="Also snap note lengths to the grid.")
        ] = False,
        channel: Annotated[
            int | None,
            Field(ge=0, description="Optional channel-rack index to retarget before quantizing."),
        ] = None,
        pattern: Annotated[
            int | None,
            Field(ge=1, description="Optional FL pattern index to select before quantizing."),
        ] = None,
    ) -> dict:
        """Quantize the notes in the active Piano roll.

        Safety: Write-Safe with Rollback. The generated Piano Roll script uses
        FL undo for rollback; note readback to MCP remains API-limited.
        """
        bridge = get_bridge()
        _ensure_piano_roll(bridge, channel, pattern)
        return safety.safe_piano_roll_write(
            bridge,
            tool="piano_quantize",
            params={
                "grid_bars": float(grid_bars),
                "snap_ends": bool(snap_ends),
                **_target_payload(channel, pattern),
            },
            apply=lambda: bridge.apply_notes(
                [],
                trigger=True,
                quantize=float(grid_bars),
                snap_ends=snap_ends,
                channel=channel,
                pattern=pattern,
            ),
        )

    @mcp.tool(annotations={"title": "Transpose notes in Piano roll", **_WR})
    def fl_piano_transpose(
        semitones: Annotated[
            int,
            Field(description="Number of semitones to shift notes."),
        ],
        channel: Annotated[
            int | None,
            Field(ge=0, description="Optional channel-rack index to retarget before transposing."),
        ] = None,
        pattern: Annotated[
            int | None,
            Field(ge=1, description="Optional FL pattern index to select before transposing."),
        ] = None,
    ) -> dict:
        """Transpose all notes in the active pattern's Piano roll.

        Safety: Write-Safe with Rollback. The generated Piano Roll script uses
        FL undo for rollback; note readback to MCP remains API-limited.
        """
        bridge = get_bridge()
        _ensure_piano_roll(bridge, channel, pattern)
        return safety.safe_piano_roll_write(
            bridge,
            tool="piano_transpose",
            params={"semitones": semitones, **_target_payload(channel, pattern)},
            apply=lambda: bridge.apply_notes(
                [], trigger=True, transpose=semitones, channel=channel, pattern=pattern
            ),
        )

    @mcp.tool(annotations={"title": "Duplicate Piano roll notes forward", **_WR})
    def fl_piano_duplicate(
        offset_bars: Annotated[
            float,
            Field(gt=0.0, description="How far forward to duplicate notes, in bars."),
        ] = 1.0,
        channel: Annotated[
            int | None,
            Field(ge=0, description="Optional channel-rack index to retarget before duplicating."),
        ] = None,
        pattern: Annotated[
            int | None,
            Field(ge=1, description="Optional FL pattern index to select before duplicating."),
        ] = None,
    ) -> dict:
        """Duplicate all notes in the active Piano roll forward by a bar offset.

        Safety: Write-Safe with Rollback. The generated Piano Roll script uses
        FL undo for rollback; note readback to MCP remains API-limited.
        """
        bridge = get_bridge()
        _ensure_piano_roll(bridge, channel, pattern)
        return safety.safe_piano_roll_write(
            bridge,
            tool="piano_duplicate",
            params={"offset_bars": float(offset_bars), **_target_payload(channel, pattern)},
            apply=lambda: bridge.apply_notes(
                [],
                trigger=True,
                duplicate_bars=float(offset_bars),
                channel=channel,
                pattern=pattern,
            ),
        )

    @mcp.tool(annotations={"title": "Apply Piano roll velocity ramp", **_WR})
    def fl_piano_velocity_ramp(
        start: Annotated[float, Field(ge=0.0, le=1.0, description="Start velocity 0..1.")],
        end: Annotated[float, Field(ge=0.0, le=1.0, description="End velocity 0..1.")],
        channel: Annotated[
            int | None,
            Field(ge=0, description="Optional channel-rack index to retarget before editing."),
        ] = None,
        pattern: Annotated[
            int | None,
            Field(ge=1, description="Optional FL pattern index to select before editing."),
        ] = None,
    ) -> dict:
        """Apply a linear velocity ramp over note order in the active Piano roll.

        Safety: Write-Safe with Rollback. The generated Piano Roll script uses
        FL undo for rollback; note readback to MCP remains API-limited.
        """
        bridge = get_bridge()
        _ensure_piano_roll(bridge, channel, pattern)
        return safety.safe_piano_roll_write(
            bridge,
            tool="piano_velocity_ramp",
            params={"start": float(start), "end": float(end), **_target_payload(channel, pattern)},
            apply=lambda: bridge.apply_notes(
                [],
                trigger=True,
                velocity_ramp=(float(start), float(end)),
                channel=channel,
                pattern=pattern,
            ),
        )

    @mcp.tool(annotations={"title": "Probe Piano roll return channel", **_RO})
    def fl_piano_probe_return_channel() -> dict:
        """Report current Piano roll note-readback capability and known limitations.

        Safety: Read-Only.
        """
        return {
            "ok": True,
            "readback_available": False,
            "status": "api-limited",
            "reason": (
                "Piano Roll scripts can read notes locally, but there is no verified, "
                "safe return channel back to the MCP server in this branch."
            ),
            "recommended_path": (
                "Use write tools with undo-backed rollback. Treat note readback as probe-only "
                "until a version-stable return channel is implemented."
            ),
        }

    @mcp.tool(annotations={"title": "Add Piano roll marker", **_WR})
    def fl_piano_add_marker(
        time_bars: Annotated[float, Field(ge=0.0, description="Marker position in bars.")],
        name: Annotated[str, Field(min_length=1, description="Marker label.")],
        mode: Annotated[int, Field(description="Marker mode/type integer.", ge=0)] = 0,
        channel: Annotated[
            int | None,
            Field(ge=0, description="Optional channel-rack index to retarget first."),
        ] = None,
        pattern: Annotated[
            int | None,
            Field(ge=1, description="Optional FL pattern index to select before adding marker."),
        ] = None,
    ) -> dict:
        """Add one marker in the active Piano roll.

        Safety: Write-Safe with Rollback. The generated Piano Roll script uses
        FL undo for rollback; marker readback to MCP remains API-limited.
        """
        bridge = get_bridge()
        _ensure_piano_roll(bridge, channel, pattern)
        return safety.safe_piano_roll_write(
            bridge,
            tool="piano_add_marker",
            params={
                "time_bars": float(time_bars),
                "name": name,
                "mode": int(mode),
                **_target_payload(channel, pattern),
            },
            apply=lambda: bridge.apply_notes(
                [],
                trigger=True,
                marker_add={"time_bars": float(time_bars), "name": name, "mode": int(mode)},
                channel=channel,
                pattern=pattern,
            ),
        )

    @mcp.tool(annotations={"title": "Add Piano roll time-signature marker", **_WR})
    def fl_piano_add_time_signature_marker(
        time_bars: Annotated[float, Field(ge=0.0, description="Marker position in bars.")],
        numerator: Annotated[int, Field(ge=1, description="Time-signature numerator.")],
        denominator: Annotated[int, Field(ge=1, description="Time-signature denominator.")],
        name: Annotated[
            str, Field(description="Optional marker label, defaults to 'Time Signature'.")
        ] = "Time Signature",
        channel: Annotated[
            int | None,
            Field(ge=0, description="Optional channel-rack index to retarget first."),
        ] = None,
        pattern: Annotated[
            int | None,
            Field(ge=1, description="Optional FL pattern index to select before adding marker."),
        ] = None,
    ) -> dict:
        """Add a time-signature marker in the active Piano roll.

        Safety: Write-Safe with Rollback. The generated Piano Roll script uses
        FL undo for rollback; marker readback to MCP remains API-limited.
        """
        bridge = get_bridge()
        _ensure_piano_roll(bridge, channel, pattern)
        return safety.safe_piano_roll_write(
            bridge,
            tool="piano_add_time_signature_marker",
            params={
                "time_bars": float(time_bars),
                "numerator": int(numerator),
                "denominator": int(denominator),
                "name": name,
                **_target_payload(channel, pattern),
            },
            apply=lambda: bridge.apply_notes(
                [],
                trigger=True,
                marker_add={
                    "time_bars": float(time_bars),
                    "name": name,
                    "mode": 8,
                    "ts_num": int(numerator),
                    "ts_den": int(denominator),
                },
                channel=channel,
                pattern=pattern,
            ),
        )

    @mcp.tool(annotations={"title": "Clear Piano roll markers", **_WR})
    def fl_piano_clear_markers(
        channel: Annotated[
            int | None,
            Field(ge=0, description="Optional channel-rack index to retarget first."),
        ] = None,
        pattern: Annotated[
            int | None,
            Field(ge=1, description="Optional FL pattern index to select before clearing markers."),
        ] = None,
    ) -> dict:
        """Clear all markers in the active Piano roll.

        Safety: Write-Safe with Rollback. The generated Piano Roll script uses
        FL undo for rollback; marker readback to MCP remains API-limited.
        """
        bridge = get_bridge()
        _ensure_piano_roll(bridge, channel, pattern)
        return safety.safe_piano_roll_write(
            bridge,
            tool="piano_clear_markers",
            params=_target_payload(channel, pattern),
            apply=lambda: bridge.apply_notes(
                [], trigger=True, marker_clear=True, channel=channel, pattern=pattern
            ),
        )

    @mcp.tool(annotations={"title": "Get notes in active Piano roll (API Limited)", **_RO})
    def fl_piano_get_notes() -> dict:
        """Read back notes from the Piano roll (API Limited -- returns error).

        Safety: Read-Only.
        """
        return {
            "ok": False,
            "error": "Piano Roll readback to the MCP server is currently api-limited.",
            "details": (
                "FL Studio's Python controller script API does not expose any methods to read "
                "back notes from a pattern, and the Piano Roll script sandbox has no communication "
                "channel back to the MIDI/MCP server. Note operations are write-only."
            ),
        }
