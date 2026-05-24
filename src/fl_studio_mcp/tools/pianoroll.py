"""Phase 2 MCP tool -- author notes into FL's piano roll.

Uses the generate-script bridge (pyscript can't read/write files, so the
daemon generates a .pyscript with the notes baked in, then force-focuses FL
and fires Ctrl+Alt+Y). Requires the FL Piano roll open, and a one-time setup:
run 'MCP_Apply' once from the piano-roll Scripting menu so that
'Run last script again' (Ctrl+Alt+Y) targets it.
"""

from __future__ import annotations

from typing import Annotated, List

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from ..connection import get_bridge


class PianoRollNote(BaseModel):
    pitch: int = Field(ge=0, le=127,
                       description="MIDI note (60 = middle C; FL displays it as C5).")
    time_bars: float = Field(0.0, ge=0.0,
                             description="Start, in bars from the pattern start.")
    length_bars: float = Field(1.0, gt=0.0, description="Duration in bars.")
    velocity: float = Field(100 / 127.0, ge=0.0, le=1.0,
                            description="0.0-1.0 (0.787 ~= MIDI velocity 100).")


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations={
        "title": "Write piano-roll notes",
        "readOnlyHint": False,
        "destructiveHint": True,   # mode='replace' clears existing notes
        "idempotentHint": False,
        "openWorldHint": True,
    })
    def fl_write_piano_roll_notes(
        notes: List[PianoRollNote],
        mode: Annotated[str, Field(
            description="'replace' clears the pattern first; 'append' adds to it.",
        )] = "replace",
    ) -> dict:
        """Write notes into the currently-open FL Piano roll.

        Each note: {pitch (MIDI), time_bars, length_bars, velocity 0-1}.
        Setup: open the Piano roll and run 'MCP_Apply' once from its Scripting
        menu (so Ctrl+Alt+Y targets it). mode='replace' clears first.
        """
        arr = [n.model_dump() for n in notes]
        return get_bridge().apply_notes(arr, mode)
