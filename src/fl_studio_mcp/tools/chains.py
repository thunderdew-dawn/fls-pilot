"""Genre processing-chain setup -- map a recipe to a track's EXISTING plugins.

fl_setup_chain reads the track's loaded plugins and returns a PLAN: which existing
intents to apply (with the matched slot) for a genre chain, + which steps can't be
done because the plugin isn't loaded (FL can't load plugins -- add manually). Apply
the plan via the existing fl_apply_eq_intent / fl_apply_compression_intent /
fl_apply_reverb_intent after the user approves. fl_list_chains lists the recipes.
"""
from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from .. import protocol
from ..connection import get_bridge
from ..music import chains as ch


def register(mcp: FastMCP) -> None:
    _RO = {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": True}

    @mcp.tool(annotations={"title": "List genre chains", **_RO})
    def fl_list_chains() -> dict:
        """List the built-in genre processing-chain recipes (vocal, drum_bus,
        bass, master) and their ordered steps."""
        return {"ok": True, "chains": ch.describe()}

    @mcp.tool(annotations={"title": "Set up a genre chain (plan)", **_RO})
    def fl_setup_chain(
        track: Annotated[int, Field(ge=0, description="Mixer track index.")],
        chain_type: Annotated[str, Field(description="Recipe: 'vocal', 'drum_bus', 'bass', 'master'.")],
    ) -> dict:
        """Plan a genre-appropriate processing chain over a track's EXISTING
        plugins. READ-ONLY plan: returns the ordered intent calls (each with the
        matched plugin + slot) and which steps are MISSING because the needed
        plugin isn't loaded (FL can't load plugins -- add those manually). After
        the user approves, apply each step by calling its 'apply' tool+args
        (fl_apply_eq_intent / fl_apply_compression_intent / fl_apply_reverb_intent
        -- each logged + rollback-able). e.g. vocal: HP -> comp -> presence ->
        air -> reverb."""
        try:
            pl = get_bridge().call(protocol.CMD_PLUGIN_LIST, {"track": track}) or {}
        except Exception as e:
            return {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}
        plugins = pl.get("slots", [])
        plan = ch.plan_chain(chain_type, plugins)
        if not plan.get("ok"):
            return plan
        steps = [{"role": s["role"], "plugin": s["plugin"],
                  "apply": {"tool": s["tool"],
                            "args": {"track": track, "slot": s["slot"], "intent": s["intent"]}}}
                 for s in plan["steps"]]
        return {"ok": True, "track": track, "chain_type": plan["chain_type"],
                "loaded_plugins": [p.get("name") for p in plugins],
                "steps": steps, "missing": plan["missing"],
                "guidance": ("After the user approves, apply each step's 'apply' (tool + args). "
                             "MISSING steps need a plugin FL cannot load -- tell the user to add "
                             "it manually, then re-run. Nothing applied here."
                             + ("" if steps else " No loaded plugins matched this recipe."))}
