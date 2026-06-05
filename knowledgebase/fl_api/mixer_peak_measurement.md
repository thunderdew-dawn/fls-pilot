# Mixer Peak Measurement (Pre-Fader vs. Post-Fader)

**Date**: 2026-06-05
**Agent/Author**: Antigravity / USER
**Topic**: Peak Measurement
**Affected File/API**: `levels.measure_track_level` / `protocol.CMD_MIXER_GET_TRACK`
**Confidence Level**: implementation_verified

## Context
When calculating thresholds for dynamic plugins (like compressors) automatically, it's essential to use the pre-fader peak.

## Observation
The peak level returned by FL Studio's level measurement API (used in `levels.measure_track_level`) is measured **Post-Fader**. This means the returned peak is affected by the mixer track's volume fader.

## Tested Values & Result
To obtain the true **Pre-Fader** peak of the incoming signal, the current volume of the track fader (`vol_db`) must be subtracted from the measured post-fader peak (`peak_db`).

Calculation: `pre_fader_peak = measured["peak_db"] - vol_db`

## Source/Method
User provided a patch in `src/fl_studio_mcp/tools/mixing.py` that fixes a bug in automatic threshold calculation by implementing this offset using `protocol.CMD_MIXER_GET_TRACK`.

## Reproduction Steps
1. Measure a track's peak level using `levels.measure_track_level` with fader at 0 dB.
2. Lower the fader by 10 dB.
3. Observe that the measured peak level drops by 10 dB.
4. Calculate `pre_fader_peak` by subtracting `vol_db` from `peak_db` and observe that it remains constant regardless of fader position.

## Open Questions
None.

## Next Recommended Action
Ensure that all future tools requiring threshold or raw signal level calculation account for the post-fader nature of the level measurement API by offsetting the fader volume.
