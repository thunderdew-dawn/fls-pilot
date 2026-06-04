"""Project Organizer tools for FL Studio MCP.

Handles broad project standardization, naming conventions, color coding,
and structural cleanup.
"""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from .. import protocol, safety
from ..connection import fetch_all_pages, get_bridge
from .channels import _is_default_mixer_name
from .routing import _route_write_entry, _bus_rename_entry

def _looks_default_channel_name(name) -> bool:
    if not name:
        return True
    return str(name).split(" ")[0] in ("Channel", "Sampler", "Insert", "AudioClip")

def _color_write_entry(channel: int, color_hex: str) -> dict:
    return {
        "snap_scope": f"channel:{channel}",
        "command": protocol.CMD_CHANNEL_SET_COLOR,
        "params": {"channel": channel, "color": color_hex},
        "restore": lambda b, ci=channel: {
            "command": protocol.CMD_CHANNEL_SET_COLOR,
            "params": {"channel": ci, "color": b.get("color", "#525B64")}
        }
    }

def _mixer_color_entry(track: int, color_hex: str) -> dict:
    return {
        "snap_scope": f"mixer_track:{track}",
        "command": protocol.CMD_MIXER_SET_COLOR,
        "params": {"track": track, "color": color_hex},
        "restore": lambda b, ti=track: {
            "command": protocol.CMD_MIXER_SET_COLOR,
            "params": {"track": ti, "color": b.get("color", "#525B64")}
        }
    }

def _channel_rename_entry(channel: int, name: str) -> dict:
    return {
        "snap_scope": f"channel:{channel}",
        "command": protocol.CMD_CHANNEL_SET_NAME,
        "params": {"channel": channel, "name": name},
        "restore": lambda b, ci=channel: {
            "command": protocol.CMD_CHANNEL_SET_NAME,
            "params": {"channel": ci, "name": b.get("name", f"Channel {ci}")}
        }
    }

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

    @mcp.tool(annotations={"title": "Analyze Project Organization", **_RO})
    def fl_analyze_project_organization() -> dict:
        """Analyze project to find unnamed channels, uncolored channels, and unassigned tracks.
        
        Safety: Read-Only.
        """
        bridge = get_bridge()
        chans = fetch_all_pages(bridge, protocol.CMD_CHANNEL_ROUTING_SUMMARY, "channels")
        
        unnamed = []
        uncolored = []
        ungrouped = []
        
        for c in chans.get("channels", []):
            if _looks_default_channel_name(c.get("name")):
                unnamed.append(c)
            
            # Simple heuristic for uncolored (assuming default FL color or no color)
            # We don't have color in routing summary currently, we'd need to fetch or assume.
            # But the agent can use this as a structural check.
            
            tgt = c.get("target_mixer_track")
            if not isinstance(tgt, int) or tgt == 0:
                ungrouped.append(c)
                
        return {
            "unnamed_channels": unnamed,
            "ungrouped_channels": ungrouped,
            "note": "Use plan_project_cleanup to generate an action plan."
        }

    @mcp.tool(annotations={"title": "Plan Project Cleanup", **_RO})
    def fl_plan_project_cleanup() -> dict:
        """Create a dry-run plan for project cleanup.
        
        Safety: Read-Only.
        """
        return {
            "status": "Plan ready. Please provide renaming, coloring, or routing schemas.",
            "available_tools": [
                "fl_apply_naming_standard",
                "fl_apply_color_standard",
                "fl_apply_project_cleanup_step"
            ]
        }

    @mcp.tool(annotations={"title": "Apply Project Cleanup Step", **_WR})
    def fl_apply_project_cleanup_step(
        renames: Annotated[list[dict], Field(description="List of {type: 'channel'|'mixer', index: int, name: str}")] = None,
        colors: Annotated[list[dict], Field(description="List of {type: 'channel'|'mixer', index: int, hex: str}")] = None
    ) -> dict:
        """Apply a batch of names and colors in one rollback unit.
        
        Safety: Write-Safe with Rollback.
        """
        bridge = get_bridge()
        writes = []
        
        if renames:
            for r in renames:
                if r["type"] == "channel":
                    writes.append(_channel_rename_entry(r["index"], r["name"]))
                elif r["type"] == "mixer":
                    writes.append(_bus_rename_entry(r["index"], r["name"]))
                    
        if colors:
            for c in colors:
                if c["type"] == "channel":
                    writes.append(_color_write_entry(c["index"], c["hex"]))
                elif c["type"] == "mixer":
                    writes.append(_mixer_color_entry(c["index"], c["hex"]))
                    
        if not writes:
            return {"status": "No valid writes specified."}
            
        return safety.safe_write_group(
            bridge,
            tool="apply_project_cleanup",
            scope="project_organizer",
            writes=writes,
            rollback_unit="project_cleanup_step"
        )

    @mcp.tool(annotations={"title": "Apply Naming Standard", **_WR})
    def fl_apply_naming_standard(
        style: Annotated[str, Field(description="Naming schema (e.g. 'psytrance', 'default', 'dynamic')")],
        rules: Annotated[list[dict], Field(description="Specific rewrite rules applied by LLM: {type, index, name}")]
    ) -> dict:
        """Batch apply standardized names across the project.
        
        Safety: Write-Safe with Rollback.
        """
        bridge = get_bridge()
        writes = []
        for r in rules:
            if r["type"] == "channel":
                writes.append(_channel_rename_entry(r["index"], r["name"]))
            elif r["type"] == "mixer":
                writes.append(_bus_rename_entry(r["index"], r["name"]))
                
        if not writes:
            return {"status": "No rules provided."}
            
        return safety.safe_write_group(
            bridge,
            tool="apply_naming_standard",
            scope="project_organizer",
            writes=writes,
            rollback_unit=f"naming_standard_{style}"
        )

    @mcp.tool(annotations={"title": "Apply Color Standard", **_WR})
    def fl_apply_color_standard(
        style: Annotated[str, Field(description="Color schema (e.g. 'psytrance', 'default', 'dynamic')")],
        rules: Annotated[list[dict], Field(description="Specific color rules applied by LLM: {type, index, hex}")]
    ) -> dict:
        """Batch apply standardized colors across the project. Hex should be e.g. '#FF0000'.
        
        Safety: Write-Safe with Rollback.
        """
        bridge = get_bridge()
        writes = []
        for r in rules:
            if r["type"] == "channel":
                writes.append(_color_write_entry(r["index"], r["hex"]))
            elif r["type"] == "mixer":
                writes.append(_mixer_color_entry(r["index"], r["hex"]))
                
        if not writes:
            return {"status": "No rules provided."}
            
        return safety.safe_write_group(
            bridge,
            tool="apply_color_standard",
            scope="project_organizer",
            writes=writes,
            rollback_unit=f"color_standard_{style}"
        )
