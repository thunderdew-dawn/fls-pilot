"""Raga / scale composer -- write LLM-generated notes via the note bridge.

NO theory engine: The LLM assistant knows the ragas (Hamsadhwani, Charukesi, Mohanam,
Kalyani, ...) and supplies the notes; these tools just SELECT the target channel
and WRITE the notes through the existing (hardened) piano-roll bridge. raga/root
are echoed for labelling only.

Setup (same as the note bridge): Piano roll open + 'MCP_Apply' armed once per
session (Ctrl+Alt+Y target). Writes into the SELECTED pattern + channel.
"""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from .. import protocol, safety
from ..connection import get_bridge


class RagaNote(BaseModel):
    pitch: int = Field(ge=0, le=127, description="MIDI note (60 = middle C / FL C5).")
    time_bars: float = Field(0.0, ge=0.0, description="Start in bars from pattern start.")
    length_bars: float = Field(0.25, gt=0.0, description="Duration in bars.")
    velocity: float = Field(0.787, ge=0.0, le=1.0, description="0..1 (0.787 ~= MIDI vel 100).")


def _write(notes, channel, mode):
    bridge = get_bridge()
    dumped = [n.model_dump() for n in notes]

    def apply():
        out = {}
        previous_channel = None
        if channel is not None:
            previous_channel = bridge.call(protocol.CMD_CHANNEL_SELECTED)
            if previous_channel.get("selected") != channel:
                out["channel_selected"] = bridge.call(
                    protocol.CMD_CHANNEL_SELECT, {"channel": channel}
                )
        try:
            out["notes"] = bridge.apply_notes(dumped, mode, channel=channel)
        finally:
            if previous_channel is not None:
                selected = previous_channel.get("selected")
                if isinstance(selected, int) and selected != channel:
                    out["channel_restored"] = bridge.call(
                        protocol.CMD_CHANNEL_SELECT, {"channel": selected}
                    )
        return out

    return safety.safe_piano_roll_write(
        bridge,
        tool="write_scale_notes",
        params={"notes": dumped, "channel": channel, "mode": mode},
        apply=apply,
    )


def register(mcp: FastMCP) -> None:
    _WR = {
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True,
        "safetyClass": "write-safe-required",
    }

    @mcp.tool(annotations={"title": "Write a raga/scale MELODY", **_WR})
    def fl_write_raga_melody(
        notes: list[RagaNote],
        raga: Annotated[
            str | None, Field(description="Raga/scale name (label only), e.g. 'Hamsadhwani'.")
        ] = None,
        root: Annotated[
            str | None, Field(description="Root/tonic (label only), e.g. 'C', 'D#'.")
        ] = None,
        channel: Annotated[
            int | None,
            Field(ge=0, description="Channel-rack channel to write into (selected first)."),
        ] = None,
        mode: Annotated[
            str, Field(description="'replace' clears the pattern first; 'append' adds.")
        ] = "replace",
    ) -> dict:
        """Write a MELODY (single-line, sequential notes) into the selected channel
        via the piano-roll bridge. YOU (the LLM assistant) generate the swaras for the named
        raga/root -> MIDI notes (use the proper aarohana/avarohana; respect the
        raga's allowed swaras); this tool only selects the channel + writes. SHOW
        the user the notes/swaras BEFORE calling. Needs the Piano roll open +
        MCP_Apply armed once this session (see the note-bridge setup).

        Safety: Write-Safe-Required with Rollback.
        """
        return {
            "ok": True,
            "wrote": len(notes),
            "raga": raga,
            "root": root,
            "channel": channel,
            "bridge": _write(notes, channel, mode),
        }

    @mcp.tool(annotations={"title": "Write raga/scale CHORDS", **_WR})
    def fl_write_raga_chords(
        notes: list[RagaNote],
        raga: Annotated[str | None, Field(description="Raga/scale name (label only).")] = None,
        root: Annotated[str | None, Field(description="Root/tonic (label only).")] = None,
        channel: Annotated[
            int | None,
            Field(ge=0, description="Channel-rack channel to write into (selected first)."),
        ] = None,
        mode: Annotated[
            str, Field(description="'replace' clears the pattern first; 'append' adds.")
        ] = "replace",
    ) -> dict:
        """Write CHORDS / a progression (stacked notes sharing start times) into
        the selected channel via the bridge. YOU stack chord tones drawn from the
        raga/scale (give simultaneous notes the SAME time_bars). Tool selects the
        channel + writes. SHOW the user the chords BEFORE calling.

        Safety: Write-Safe-Required with Rollback.
        """
        return {
            "ok": True,
            "wrote": len(notes),
            "raga": raga,
            "root": root,
            "channel": channel,
            "bridge": _write(notes, channel, mode),
        }

    _RO = {
        "readOnlyHint": True,
        "idempotentHint": True,
        "openWorldHint": True,
        "safetyClass": "read-only",
    }

    @mcp.tool(annotations={"title": "List all scales and ragas", **_RO})
    def fl_scale_list() -> dict:
        """Get a categorized list of all available scales and ragas,
        including their families and moods.

        Safety: Read-Only.
        """
        from ..music.scales import SCALES_CATALOGUE

        families = {}
        for k, v in SCALES_CATALOGUE.items():
            fam = v["family"]
            if fam not in families:
                families[fam] = []
            families[fam].append({"key": k, "name": v["name"], "mood": v["mood"]})
        return {"ok": True, "families": families}

    @mcp.tool(annotations={"title": "Get details of a scale or raga", **_RO})
    def fl_scale_get(
        scale_name: Annotated[
            str,
            Field(description="Scale or Raga key/name, for example 'dorian'."),
        ],
        root_note: Annotated[
            str | int,
            Field(description="Root note, for example 'C5', 'F#4', or MIDI number."),
        ] = "C5",
        octave_range: Annotated[
            int,
            Field(ge=1, le=4, description="Generate pitches over this many octaves."),
        ] = 1,
    ) -> dict:
        """Get the notes, MIDI numbers, and mood of a scale/raga relative to a root note.

        Safety: Read-Only.
        """
        from ..music import scales

        try:
            res = scales.get_scale_notes(scale_name, root_note, octave_range)
            res["ok"] = True
            return res
        except Exception as e:
            return {"ok": False, "error": str(e)}
