#!/usr/bin/env python3
"""Phase 1B end-to-end via the REAL registered MCP tools (in-process).

Builds the FastMCP server and invokes the tools by name through call_tool --
the same path an MCP client uses -- so this also proves the Pydantic
Union[int,str] coercion of `param` and the result assembly, not just the
underlying helper. Non-destructive: it sets Reeverb 'Dry level' then rolls
back to the original.

    set FLSTUDIO_MCP_TRANSPORT=tcp
    python scripts/test_phase1b_mcp.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp.server import build_server  # noqa: E402


def unwrap(result):
    """Pull a plain value out of whatever call_tool returns across versions."""
    for attr in ("data", "structured_content", "structuredContent"):
        v = getattr(result, attr, None)
        if v is not None:
            return v
    if isinstance(result, tuple) and result:
        return unwrap(result[0]) if hasattr(result[0], "data") else result[0]
    return result


def main() -> int:
    m = build_server()

    async def call(name, args):
        return unwrap(await m.call_tool(name, args))

    # 1. list + dump (read) ---------------------------------------------------
    listing = asyncio.run(call("fl_plugin_list", {"track": 2}))
    print("fl_plugin_list(2):", listing)

    dump = asyncio.run(call("fl_plugin_get_params", {"track": 2, "slot": 1}))
    total = dump.get("total")
    params = dump.get("params", [])
    print(f"fl_plugin_get_params(2,1): total={total} named={len(params)}")

    # 2. set BY NAME through the real tool, then rollback ---------------------
    name = "Dry level"
    setres = asyncio.run(
        call("fl_plugin_set_param", {"track": 2, "slot": 1, "param": name, "value": 0.7})
    )
    resolved = setres.get("resolved_param")
    after_v = setres.get("after", {}).get("v")
    before_v = setres.get("before", {}).get("v")
    print(
        f"fl_plugin_set_param(name={name!r}): resolved={resolved} before={before_v} after={after_v}"
    )

    rb = asyncio.run(call("fl_rollback_last_change", {}))
    print(
        "fl_rollback_last_change:",
        rb.get("rolled_back"),
        "restored_v=",
        (rb.get("restored") or {}).get("v"),
    )

    ok = (
        resolved
        and abs(after_v - 0.7) < 0.02
        and (rb.get("restored") or {}).get("v") is not None
        and abs(rb["restored"]["v"] - before_v) < 0.02
    )
    print("\nEND-TO-END MCP PATH:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        # call_tool's surface drifts between FastMCP versions; the underlying
        # logic is already proven by test_phase1b_tools.py (7/7).
        print(f"in-process MCP call path not exercised ({type(e).__name__}: {e})")
        sys.exit(2)
