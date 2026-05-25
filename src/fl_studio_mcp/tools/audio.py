"""Audio analysis (Integration 2/3): tempo + key (Stage 1).

Pure server-side analysis -- does NOT touch FL. librosa/numpy are imported
LAZILY inside the functions so the MCP server starts fast and stays usable
even if the optional [audio] extra isn't installed.

Key detection (Krumhansl-Schmuckler chroma correlation) is ~60-80% accurate and
often confuses relative major/minor -- always labelled 'estimated'.
"""
from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

# Krumhansl-Schmuckler key profiles (C-rooted; rotated per candidate tonic).
_KS_MAJOR = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
_KS_MINOR = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
_NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def estimate_key(chroma_mean):
    """12-bin mean chroma -> {key, tonic, mode, confidence, estimated}."""
    import numpy as np
    maj, minr = np.array(_KS_MAJOR), np.array(_KS_MINOR)
    best = None
    for i in range(12):
        for mode, prof in (("major", maj), ("minor", minr)):
            r = float(np.corrcoef(np.roll(prof, i), chroma_mean)[0, 1])
            if best is None or r > best["confidence"]:
                best = {"tonic": _NOTES[i], "mode": mode, "confidence": r}
    return {"key": "%s %s" % (best["tonic"], best["mode"]),
            "tonic": best["tonic"], "mode": best["mode"],
            "confidence": round(best["confidence"], 3), "estimated": True}


def audio_analyze(path):
    """Tempo (beat_track), estimated key, duration, beat/onset counts."""
    import numpy as np
    import librosa
    y, sr = librosa.load(path, mono=True)          # WAV direct; MP3 via ffmpeg
    duration = float(librosa.get_duration(y=y, sr=sr))
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    tempo = float(np.atleast_1d(tempo).ravel()[0])
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    key = estimate_key(chroma.mean(axis=1))
    onsets = librosa.onset.onset_detect(y=y, sr=sr)
    out = {"path": str(path), "duration_sec": round(duration, 2),
           "tempo_bpm": round(tempo, 1), "beats": int(len(beats)),
           "onsets": int(len(onsets)), "key": key,
           "note": "key is ESTIMATED (~60-80% accurate; may confuse relative major/minor)"}
    # beat_track often locks to 2x on busy material -> surface the halved value.
    if tempo > 180.0:
        out["tempo_bpm_likely"] = round(tempo / 2.0, 1)
        out["tempo_note"] = ("tempo > 180 BPM -- likely a 2x (octave) detection; "
                             "tempo_bpm_likely is the halved, probably-real value")
    return out


def register(mcp: FastMCP) -> None:
    _RO = {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": True}

    @mcp.tool(annotations={"title": "Analyze audio (tempo/key)", **_RO})
    def fl_analyze_audio(
        path: Annotated[str, Field(description="Path to a WAV/MP3 file (MP3 needs ffmpeg on PATH).")],
    ) -> dict:
        """Estimate tempo + key (+ duration, beats, onsets) of an audio file.
        Pure offline analysis -- does NOT touch FL. Key is ESTIMATED."""
        import os
        if not os.path.isfile(path):
            return {"ok": False, "error": "file not found: %s" % path}
        try:
            return {"ok": True, **audio_analyze(path)}
        except Exception as e:
            return {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}
