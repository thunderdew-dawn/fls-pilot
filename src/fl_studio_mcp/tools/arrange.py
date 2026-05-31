"""Arrangement primitives (Slice 1).

FL's API can't place pattern clips on the playlist (confirmed by probe), so
"arrangement" here = create/name/fill section PATTERNS + mark the timeline with
named markers; the user drags the patterns onto the playlist.

Filling notes reuses the existing piano-roll bridge (fl_write_piano_roll_notes),
which writes into the CURRENTLY SELECTED pattern -- so the flow is
new_pattern (selects it) -> write notes.
"""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from .. import protocol, safety
from ..connection import get_bridge


def register(mcp: FastMCP) -> None:
    _WR = {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    }

    @mcp.tool(annotations={"title": "New named pattern (selects it)", **_WR})
    def fl_arrange_new_pattern(
        name: Annotated[str, Field(description="Pattern name, e.g. 'INTRO'.")],
    ) -> dict:
        """Create + select + name the next empty pattern. Rollback uses FL undo."""
        return safety.safe_write(
            get_bridge(),
            tool="arrange_new_pattern",
            scope="patterns_all",
            command=protocol.CMD_ARRANGE_NEW_PATTERN,
            params={"name": name},
            build_restore=lambda _b: {"command": protocol.CMD_GENERAL_UNDO, "params": {}},
        )

    @mcp.tool(annotations={"title": "Select channel (note-bridge target)", **_WR})
    def fl_arrange_select_channel(
        channel: Annotated[int, Field(ge=0, description="Channel-rack channel index.")],
    ) -> dict:
        """Make a channel active; rollback restores the previously selected channel."""
        return safety.safe_write(
            get_bridge(),
            tool="arrange_select_channel",
            scope="selected_channel",
            command=protocol.CMD_CHANNEL_SELECT,
            params={"channel": channel},
            build_restore=lambda b: {
                "command": protocol.CMD_CHANNEL_SELECT,
                "params": {"channel": b["selected"]},
            },
        )

    @mcp.tool(annotations={"title": "Clone a pattern (copies notes)", **_WR})
    def fl_arrange_clone_pattern(
        src: Annotated[int, Field(ge=1, description="Source pattern index.")],
        new_name: Annotated[str, Field(description="Name for the clone.")],
    ) -> dict:
        """Clone a pattern and rename the clone. Rollback uses FL undo."""
        return safety.safe_write(
            get_bridge(),
            tool="arrange_clone_pattern",
            scope="patterns_all",
            command=protocol.CMD_ARRANGE_CLONE_PATTERN,
            params={"src": src, "new_name": new_name},
            build_restore=lambda _b: {"command": protocol.CMD_GENERAL_UNDO, "params": {}},
        )

    @mcp.tool(annotations={"title": "Add a section marker at a bar", **_WR})
    def fl_arrange_add_marker(
        bar: Annotated[int, Field(ge=1, description="Bar number (1 = song start).")],
        name: Annotated[str, Field(description="Marker name, e.g. 'Verse'.")],
    ) -> dict:
        """Add a named timeline marker at a bar. Rollback uses FL undo."""
        return safety.safe_write(
            get_bridge(),
            tool="arrange_add_marker",
            scope="project_state",
            command=protocol.CMD_ARRANGE_ADD_MARKER,
            params={"bar": bar, "name": name},
            build_restore=lambda _b: {"command": protocol.CMD_GENERAL_UNDO, "params": {}},
        )
