# Assign to Free Mixer Track (API Limitation)

**Date**: 2026-06-04
**Agent/Author**: Antigravity
**Topic**: Mixer Routing & Assign to Free Mixer Track
**Affected File/API**: `channels.py` (`fl_apply_audio_clip_safe_defaults`), `mixer.getFreeTrack()`
**Context**: When assigning many unrouted audio clips to free mixer tracks, the internal pagination/scanning mechanism (`_find_free_mixer_track` via `CMD_MIXER_GET_ROUTING_ALL`) stopped finding tracks after a limit (e.g. 18 tracks).
**Observation**: The user pointed out that FL Studio has a UI function to "assign to new mixer track". While the Python API lacks a single magic macro like `channels.assignToFreeMixerTrack(index)`, the API *does* provide `mixer.getFreeTrack()` to reliably get the next empty track without manually paginating the entire routing matrix.
**Tested Values**: `mixer.getFreeTrack()` vs manual scanning.
**Result**: Using manual scanning can fail if the mixer payload size or track count logic truncates empty tracks. The native `mixer.getFreeTrack()` (if available) or proper payload scanning should be used. 
**Confidence Level**: docs_confirmed
**Source/Method**: Web Research (FL Studio API Stubs documentation and forum discussions) and User feedback.
**Open Questions**: Does `mixer.getFreeTrack()` return tracks beyond the currently visible/active block if the project only has 18 active tracks, or is `mixer.trackCount()` legitimately returning a lower number in this specific project?
**Next Recommended Action**: Refactor `_find_free_mixer_track` to use `mixer.getFreeTrack()` directly via a new bridge command `CMD_MIXER_GET_FREE_TRACK` instead of parsing all routing pages.
