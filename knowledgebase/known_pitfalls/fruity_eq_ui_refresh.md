Topic: Fruity Parametric EQ 2 Parameter Pagination and UI Refresh
Agent/Author: Antigravity
Date: 2026-06-04

Affected File/API: `CMD_PLUGIN_GET_PARAMS`, `Fruity Parametric EQ 2` plugin.

Context: 
Applying high-pass filters using `fl_apply_eq_intent` sets the `Band 1 type` parameter to index 21. When reading back the parameters using `CMD_PLUGIN_GET_PARAMS`, we noticed that only a subset of parameters (e.g., indices 0 to ~10) were returned unless pagination was handled via `fetch_all_pages`.

Observation:
1. `CMD_PLUGIN_GET_PARAMS` limits the number of returned parameters per request. To see all parameters of an EQ (like band types, which sit at indices 21-27), the MCP client must fetch all pages.
2. When parameters like `Band 1 type` are set via `CMD_PLUGIN_SET_PARAM`, FL Studio does not always immediately trigger a repaint of the plugin's graphical UI if the window is currently open and focused.

Result:
The API successfully applies the EQ curve, but the user might report that the EQ did not change visually.

Confidence Level: `implementation_verified`

Source/Method:
Tested via direct TCP connection to the FL Studio MIDI bridge during the Guided Fix workflow. We sent parameter changes, read them back successfully using `fetch_all_pages`, but the user reported not seeing the visual change until they interacted with the plugin window.

Open Questions:
- Is there a way to force a UI repaint via the FL Studio Python API when parameters are changed?

Next Recommended Action:
- When applying EQ changes programmatically, the MCP assistant should inform the user that they may need to close/reopen the plugin window to see the graphical changes.
