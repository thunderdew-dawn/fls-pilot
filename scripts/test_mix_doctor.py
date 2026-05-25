#!/usr/bin/env python3
"""Offline test for Mix Doctor diagnosis rules -- SYNTHETIC snapshots, no FL.

Each rule gets a snapshot that should trip it (and a clean mix that shouldn't).
Proves the rules are transparent + correct before we trust them live.

    python scripts/test_mix_doctor.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp.music import mix_doctor as md  # noqa: E402

_P = _F = 0


def check(label, cond, detail=""):
    global _P, _F
    if cond:
        _P += 1
    else:
        _F += 1
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", label, ("  -- " + detail) if detail else ""))


def trk(index, name, *, vol_db=0.0, vol_norm=0.8, peak_max=None, mute=False,
        plugins=None, routes_to=None):
    return {"index": index, "name": name, "vol_db": vol_db, "vol_norm": vol_norm,
            "pan": 0.0, "mute": mute, "solo": False, "peak_max": peak_max,
            "peak_db": md.lin_to_db(peak_max), "plugins": plugins or [],
            "routes_to": routes_to or []}


def rules_hit(res):
    return {f["rule"] for f in res["findings"]}


def main() -> int:
    # 1) clipping + headroom (playing): Master at 0 dBFS, a track over 0.
    snap = {"playing": True, "tracks": [
        trk(0, "Master", peak_max=1.0),
        trk(1, "Lead", peak_max=1.05, plugins=[{"slot": 0, "name": "Fruity parametric EQ 2"}]),
        trk(2, "Pad", peak_max=0.3, plugins=[{"slot": 0, "name": "Fruity parametric EQ 2"}]),
    ]}
    r = md.diagnose(snap)
    hits = rules_hit(r)
    check("clipping flagged when track > 0 dBFS", "clipping" in hits, str(hits))
    check("clipping severity high for Lead",
          any(f["severity"] == "high" and f["track"] == "Lead" for f in r["findings"]))
    check("headroom flagged when Master near 0 dBFS", "headroom" in hits, str(hits))

    # 2) missing high-pass: a Vox track with NO eq; Bass skipped; Synth w/ EQ ok.
    snap = {"playing": False, "tracks": [
        trk(0, "Master"),
        trk(1, "Lead Vox", plugins=[]),
        trk(2, "Bass", plugins=[]),
        trk(3, "Synth", plugins=[{"slot": 0, "name": "Fruity parametric EQ 2"}]),
        trk(4, "Snare", plugins=[]),
    ]}
    r = md.diagnose(snap)
    hpf_tracks = {f["track"] for f in r["findings"] if f["rule"] == "missing_hpf"}
    check("missing_hpf flags Lead Vox (no EQ)", "Lead Vox" in hpf_tracks, str(hpf_tracks))
    check("missing_hpf SKIPS Bass (low-end)", "Bass" not in hpf_tracks)
    check("missing_hpf SKIPS Synth (has EQ)", "Synth" not in hpf_tracks)
    check("missing_hpf SKIPS Snare (drum-family)", "Snare" not in hpf_tracks)

    # 3) fader imbalance (stopped): one track way above the median fader.
    snap = {"playing": False, "tracks": [
        trk(0, "Master"),
        trk(1, "A", vol_db=0.0), trk(2, "B", vol_db=0.0),
        trk(3, "C", vol_db=0.0), trk(4, "Loud", vol_db=5.5),
    ]}
    r = md.diagnose(snap)
    imb = {f["track"] for f in r["findings"] if f["rule"] == "imbalance"}
    check("fader imbalance flags the outlier 'Loud'", "Loud" in imb, str(imb))
    check("balanced tracks not flagged", imb == {"Loud"}, str(imb))

    # 4) ungrouped drums: Kick + Snare both route to Master (no shared bus).
    snap = {"playing": False, "tracks": [
        trk(0, "Master"),
        trk(1, "Kick", routes_to=[]),
        trk(2, "Snare", routes_to=[]),
    ]}
    r = md.diagnose(snap)
    check("ungrouped flagged for 2 drum tracks on Master", "ungrouped" in rules_hit(r))
    # ...but NOT when they share a bus (dst=20)
    snap2 = {"playing": False, "tracks": [
        trk(0, "Master"),
        trk(1, "Kick", routes_to=[{"dst": 20}]),
        trk(2, "Snare", routes_to=[{"dst": 20}]),
    ]}
    check("ungrouped NOT flagged when drums share a bus",
          "ungrouped" not in rules_hit(md.diagnose(snap2)))

    # 5) EQ clash: two tracks boosting ~240 Hz.
    eq = lambda: {"slot": 0, "name": "Fruity parametric EQ 2", "params": [
        {"i": 0, "name": "Band 2 - Level", "s": "4.0 dB"},
        {"i": 1, "name": "Band 2 - Freq", "s": "240 Hz"}]}
    snap = {"playing": False, "tracks": [
        trk(0, "Master"),
        trk(1, "Gtr L", plugins=[eq()]),
        trk(2, "Gtr R", plugins=[eq()]),
    ]}
    r = md.diagnose(snap)
    check("eq_clash flagged for two boosts in same band", "eq_clash" in rules_hit(r), str(rules_hit(r)))

    # 6) clean mix -> nothing (stopped; balanced; bass/kick skipped; EQs flat,
    #    non-low tracks carry an EQ so missing_hpf stays quiet).
    flat_eq = {"slot": 0, "name": "Fruity parametric EQ 2",
               "params": [{"i": 0, "name": "Band 2 - Level", "s": "0.0 dB"},
                          {"i": 1, "name": "Band 2 - Freq", "s": "1000 Hz"}]}
    snap = {"playing": False, "tracks": [
        trk(0, "Master"),
        trk(1, "Bass", vol_db=0.0, plugins=[]),
        trk(2, "Kick", vol_db=0.0, plugins=[], routes_to=[{"dst": 30}]),
        trk(3, "Snare", vol_db=0.0, plugins=[dict(flat_eq)], routes_to=[{"dst": 30}]),
        trk(4, "Vox", vol_db=0.0, plugins=[dict(flat_eq)]),
    ]}
    r = md.diagnose(snap)
    check("clean mix yields no findings", len(r["findings"]) == 0,
          "got %s" % [f["rule"] for f in r["findings"]])

    print("\n%d passed, %d failed" % (_P, _F))
    return 0 if _F == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
