"""Mix Doctor: read a whole-mix snapshot and diagnose common problems.

Two layers, kept separate on purpose:

* ``gather_snapshot(bridge, ...)`` -- server-side orchestration of CHEAP reads
  (two paginated lists + per-track peaks/plugins/params). Thin controller; no
  heavy all-track loop in a single tick. Touches the bridge but never writes.
* ``diagnose(snapshot)`` -- PURE, threshold-based rules. No bridge, no FL, fully
  unit-testable. Every finding carries a severity + the exact evidence (track,
  value) and a *proposed* fix that maps to an existing intent. It NEVER applies
  anything -- the caller decides.

Thresholds live as named module constants so the rules stay transparent and
tunable.
"""
from __future__ import annotations

import math
import re

# --------------------------------------------------------------------------
# Thresholds (transparent + tunable)
# --------------------------------------------------------------------------
CLIP_DB = -1.0            # peak above this dBFS  -> clipping RISK
CLIP_HARD_DB = 0.0        # peak at/above 0 dBFS  -> actual clip
HOT_DB = -3.0             # a track is "hot" if its peak is above this
HOT_FRACTION = 0.4        # >= this share of audible tracks hot -> low headroom
IMBALANCE_DB = 6.0        # peak this far above the median peak -> imbalance
FADER_IMBALANCE_DB = 4.0  # fader this far above median fader (and above unity)
EQ_BOOST_DB = 3.0         # an EQ band boost above this is "significant"

# Name heuristics
LOW_END = ("kick", "sub", "bass", "808", "boom")   # HPF not expected here
FAMILIES = {
    "drums": ("kick", "snare", "hat", "clap", "perc", "tom", "drum", "ride", "crash", "cym"),
    "vocals": ("vox", "vocal", "adlib", "harmony", "bgv", "choir"),
    "bass": ("bass", "808", "sub"),
    "synth": ("synth", "lead", "pad", "pluck", "arp", "key", "saw", "stab"),
    "guitar": ("guitar", "gtr", "acoustic"),
}

SEV_RANK = {"high": 0, "medium": 1, "low": 2}


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def lin_to_db(x):
    """Linear amplitude (0..1, 1.0 = 0 dBFS) -> dBFS, or None."""
    if x is None or x <= 0:
        return None
    return 20.0 * math.log10(x)


def _parse_db(s):
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*dB", s or "", re.I)
    return float(m.group(1)) if m else None


def _parse_hz(s):
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*kHz", s or "", re.I)
    if m:
        return float(m.group(1)) * 1000.0
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*Hz", s or "", re.I)
    return float(m.group(1)) if m else None


def _octave_bucket(hz):
    """Coarse ~octave index from ~31 Hz, for grouping EQ boosts."""
    if not hz or hz <= 0:
        return None
    return int(round(math.log2(hz / 31.25)))


def finding(rule, severity, track, evidence, message, fix):
    return {"rule": rule, "severity": severity, "track": track,
            "evidence": evidence, "message": message, "proposed_fix": fix}


# --------------------------------------------------------------------------
# Snapshot gathering (bridge orchestration -- cheap calls only)
# --------------------------------------------------------------------------
def _fetch_params_bounded(bridge, protocol, track, slot, cap):
    """Page a plugin's params, stopping at ``cap`` (so a VST monster on a mixer
    slot can't blow up the snapshot). Effects we diagnose are small anyway."""
    params, start = [], 0
    for _ in range(50):
        page = bridge.call(protocol.CMD_PLUGIN_GET_PARAMS,
                           {"track": track, "slot": slot, "start": start})
        params.extend(page.get("params") or [])
        nxt = page.get("next_start")
        if nxt is None or int(nxt) <= start or len(params) >= cap:
            break
        start = int(nxt)
    return params


def gather_snapshot(bridge, *, with_params=True, max_tracks=64, param_cap=120):
    """Build a normalised whole-mix snapshot via cheap bridge reads.

    Returns ``{"playing", "track_count", "tracks": [...], "gather_errors": [...]}``.
    Each track: index, name, vol_db, vol_norm, pan, mute, solo, peak_max,
    peak_db, plugins[{slot,name,params?}], routes_to.
    """
    from .. import protocol
    from ..connection import fetch_all_pages

    errors = []

    def _safe(fn, label, default=None):
        try:
            return fn()
        except Exception as e:
            errors.append("%s -> %s: %s" % (label, type(e).__name__, e))
            return default

    ps = _safe(lambda: bridge.call(protocol.CMD_GET_PROJECT_STATE), "project_state", {}) or {}
    playing = bool(ps.get("playing"))

    tracks_raw = (_safe(lambda: fetch_all_pages(bridge, protocol.CMD_MIXER_LIST_TRACKS, "tracks"),
                        "mixer_list_tracks", {"tracks": []}) or {}).get("tracks", [])
    routing_raw = (_safe(lambda: fetch_all_pages(bridge, protocol.CMD_MIXER_GET_ROUTING_ALL, "routing"),
                         "mixer_get_routing_all", {"routing": []}) or {}).get("routing", [])
    route_by = {r.get("i", r.get("index")): (r.get("routes_to") or []) for r in routing_raw}

    tracks = []
    for t in tracks_raw[:max_tracks]:
        i = t.get("i", t.get("index"))
        peak = (_safe(lambda i=i: bridge.call(protocol.CMD_MIXER_GET_PEAKS, {"track": i}),
                      "peaks[%s]" % i, {}) or {}).get("peak_max")
        pl = _safe(lambda i=i: bridge.call(protocol.CMD_PLUGIN_LIST, {"track": i}),
                   "plugin_list[%s]" % i, {}) or {}
        plugins = []
        for s in pl.get("slots", []):
            slot = s.get("slot", s.get("index"))
            entry = {"slot": slot, "name": s.get("name")}
            if with_params and slot is not None:
                entry["params"] = _safe(
                    lambda i=i, slot=slot: _fetch_params_bounded(bridge, protocol, i, slot, param_cap),
                    "params[%s:%s]" % (i, slot), [])
            plugins.append(entry)
        tracks.append({
            "index": i, "name": t.get("name"),
            "vol_db": t.get("vol_db"), "vol_norm": t.get("vol_norm"),
            "pan": t.get("pan"), "mute": bool(t.get("mute")), "solo": bool(t.get("solo")),
            "peak_max": peak, "peak_db": lin_to_db(peak),
            "plugins": plugins, "routes_to": route_by.get(i, []),
        })
    return {"playing": playing, "track_count": len(tracks_raw),
            "tracks": tracks, "gather_errors": errors}


# --------------------------------------------------------------------------
# Diagnosis rules (PURE -- operate on the snapshot dict only)
# --------------------------------------------------------------------------
_DEFAULT_NAME = re.compile(r"^\s*(insert\s*\d+|master)\s*$", re.I)


def _is_used(t):
    """Skip empty/unused mixer inserts (default 'Insert N' name, no plugins,
    only the implicit Master route, no signal) -- noise, not real tracks."""
    if t.get("plugins"):
        return True
    nm = (t.get("name") or "")
    if nm and not _DEFAULT_NAME.match(nm):     # a custom name = a real track
        return True
    for d in (t.get("routes_to") or []):       # routes to a real bus (not just Master)
        dst = d.get("dst") if isinstance(d, dict) else d
        if dst not in (None, 0):
            return True
    pk = t.get("peak_db")
    return pk is not None and pk > -60.0       # carrying signal (while playing)


def _audible(tracks):
    return [t for t in tracks
            if t.get("index") != 0 and not t.get("mute") and _is_used(t)]


def rule_clipping(tracks):
    out = []
    for t in tracks:
        db = t.get("peak_db")
        if db is None:
            continue
        if db >= CLIP_HARD_DB:
            out.append(finding(
                "clipping", "high", t["name"], "peak %.1f dBFS (>= 0)" % db,
                "%s is clipping (peak %.1f dBFS). Pull its level down or add a limiter." % (t["name"], db),
                {"intent": "fl_set_mixer_volume", "args": {"track": t["index"]},
                 "alt_intent": "fl_apply_compression_intent",
                 "desc": "reduce %s ~ -3 dB, or limit it" % t["name"]}))
        elif db > CLIP_DB:
            out.append(finding(
                "clipping", "medium", t["name"], "peak %.1f dBFS" % db,
                "%s peaks at %.1f dBFS -- almost no headroom (clip risk)." % (t["name"], db),
                {"intent": "fl_set_mixer_volume", "args": {"track": t["index"]},
                 "desc": "trim %s a few dB" % t["name"]}))
    return out


def rule_headroom(tracks):
    out = []
    master = next((t for t in tracks if t.get("index") == 0), None)
    if master and master.get("peak_db") is not None and master["peak_db"] > CLIP_DB:
        out.append(finding(
            "headroom", "high", "Master", "Master peak %.1f dBFS" % master["peak_db"],
            "Master is near/over 0 dBFS (%.1f) -- no headroom for the master chain." % master["peak_db"],
            {"intent": "fl_set_mixer_volume", "args": {"track": 0},
             "desc": "lower Master / gain-stage to leave ~ -6 dB headroom"}))
    aud = [t for t in _audible(tracks) if t.get("peak_db") is not None]
    hot = [t for t in aud if t["peak_db"] > HOT_DB]
    if aud and len(hot) >= max(2, int(HOT_FRACTION * len(aud))):
        out.append(finding(
            "headroom", "medium", None,
            "%d/%d audible tracks hotter than %.0f dB: %s"
            % (len(hot), len(aud), HOT_DB, ", ".join(h["name"] for h in hot[:6])),
            "Many tracks run hot at once -- overall mix headroom is low. Pull faders or bus-process.",
            {"intent": "level", "args": {}, "desc": "trim the hot tracks ~ -3 dB or route them to a bus"}))
    return out


def rule_missing_hpf(tracks):
    """HEURISTIC: a melodic/vocal track with no EQ in its chain MIGHT benefit
    from a high-pass. Skips low-end (kick/bass/sub) AND drum-family tracks
    (drum buses keep their lows), so it only flags melodic/vocal material. Low
    confidence -- a suggestion, not a confirmed problem (we have no spectrum)."""
    out = []
    for t in _audible(tracks):
        nm = (t.get("name") or "").lower()
        if any(k in nm for k in LOW_END):              # bass/kick: HPF not expected
            continue
        if any(k in nm for k in FAMILIES["drums"]):    # drums/perc: keep their lows
            continue
        has_eq = any("eq" in (p.get("name") or "").lower() for p in t.get("plugins", []))
        if not has_eq:
            names = [p.get("name") for p in t.get("plugins", [])] or ["(no plugins)"]
            out.append(finding(
                "missing_hpf", "low", t["name"], "no EQ in chain (%s)" % ", ".join(names),
                "%s has no EQ in its chain -- consider a high-pass (heuristic, not a "
                "confirmed problem)." % t["name"],
                {"intent": "fl_apply_eq_intent",
                 "args": {"track": t["index"], "intent": "remove_mud"},
                 "desc": "consider a high-pass on %s" % t["name"]}))
    return out


def _imbalance(tracks, key, label, thresh, floor=None):
    vals = [(t, t.get(key)) for t in _audible(tracks) if t.get(key) is not None]
    if len(vals) < 3:
        return []
    arr = sorted(v for _, v in vals)
    median = arr[len(arr) // 2]
    out = []
    for t, v in vals:
        if (v - median) >= thresh and (floor is None or v > floor):
            out.append(finding(
                "imbalance", "medium", t["name"],
                "%s %.1f dB vs median %.1f dB" % (label, v, median),
                "%s sits %.1f dB above the mix median (%s) -- possible level imbalance."
                % (t["name"], v - median, label),
                {"intent": "fl_set_mixer_volume", "args": {"track": t["index"]},
                 "desc": "balance %s toward the mix" % t["name"]}))
    return out


def _dests(t):
    out = set()
    for d in (t.get("routes_to") or []):
        out.add(d.get("dst") if isinstance(d, dict) else d)
    return out


def rule_ungrouped(tracks):
    out = []
    fams = {}
    for t in _audible(tracks):
        nm = (t.get("name") or "").lower()
        for fam, kws in FAMILIES.items():
            if any(k in nm for k in kws):
                fams.setdefault(fam, []).append(t)
                break
    for fam, members in fams.items():
        if len(members) < 2:
            continue
        common = set.intersection(*[_dests(t) for t in members]) if members else set()
        common_bus = {d for d in common if d not in (None, 0)}
        if not common_bus:
            out.append(finding(
                "ungrouped", "low", None,
                "%d %s tracks not bused together: %s"
                % (len(members), fam, ", ".join(m["name"] for m in members)),
                "%d %s tracks route straight out with no shared bus -- group them for shared processing."
                % (len(members), fam),
                {"intent": "fl_group_tracks", "args": {"tracks": [m["index"] for m in members]},
                 "desc": "group the %s tracks onto a bus" % fam}))
    return out


def _eq_boosted_bands(params):
    """Best-effort: find EQ bands boosted >= EQ_BOOST_DB, with their freq.

    Relies on the plugin exposing per-band 'level/gain' + 'freq' params whose
    display strings read like '3.6 dB' / '240 Hz'. If the names don't cooperate
    this simply returns nothing (no false positives)."""
    bands = {}
    for p in params:
        name = (p.get("name") or "")
        s = p.get("s") or ""
        low = name.lower()
        bn = re.search(r"(\d+)", name)
        bno = int(bn.group(1)) if bn else None
        if bno is None:
            continue
        if ("level" in low or "gain" in low) and "hz" not in s.lower():
            db = _parse_db(s)
            if db is not None:
                bands.setdefault(bno, {})["gain"] = db
        elif "freq" in low:
            hz = _parse_hz(s)
            if hz is not None:
                bands.setdefault(bno, {})["freq"] = hz
    out = []
    for bno, b in bands.items():
        if b.get("gain") is not None and b["gain"] >= EQ_BOOST_DB and b.get("freq"):
            out.append({"band": bno, "gain": b["gain"], "freq": b["freq"]})
    return out


def rule_eq_clash(tracks):
    boosts = []
    for t in _audible(tracks):
        for p in t.get("plugins", []):
            if "eq" not in (p.get("name") or "").lower():
                continue
            for b in _eq_boosted_bands(p.get("params") or []):
                boosts.append((t["name"], b["freq"], b["gain"]))
    by_bucket = {}
    for name, hz, g in boosts:
        bucket = _octave_bucket(hz)
        if bucket is not None:
            by_bucket.setdefault(bucket, []).append((name, hz, g))
    out = []
    for _bucket, items in by_bucket.items():
        names = sorted({n for n, _, _ in items})
        if len(names) >= 2:
            ev = "; ".join("%s +%.1fdB@%.0fHz" % (n, g, hz) for n, hz, g in items)
            out.append(finding(
                "eq_clash", "medium", None, ev,
                "Tracks boost the same band (~%.0f Hz): %s -- competing EQ can muddy the mix."
                % (items[0][1], ", ".join(names)),
                {"intent": "fl_apply_eq_intent", "args": {},
                 "desc": "ease overlapping boosts on %s" % " / ".join(names)}))
    return out


def diagnose(snapshot):
    """Run all rules on a snapshot. Returns findings ranked by severity +
    notes (e.g. 'play the project for level data'). PURE -- no writes."""
    tracks = snapshot.get("tracks", [])
    playing = snapshot.get("playing")
    findings, notes = [], []

    if playing:
        findings += rule_clipping(tracks)
        findings += rule_headroom(tracks)
        findings += _imbalance(tracks, "peak_db", "peak", IMBALANCE_DB)
    else:
        notes.append("Project STOPPED -- level rules (clipping, headroom, peak "
                     "imbalance) skipped. Press play and re-run for level diagnosis.")
        findings += _imbalance(tracks, "vol_db", "fader", FADER_IMBALANCE_DB, floor=0.0)

    findings += rule_missing_hpf(tracks)
    findings += rule_ungrouped(tracks)
    findings += rule_eq_clash(tracks)

    findings.sort(key=lambda f: (SEV_RANK.get(f["severity"], 9), f["rule"]))
    summary = {sev: sum(1 for f in findings if f["severity"] == sev)
               for sev in ("high", "medium", "low")}
    return {"playing": playing, "track_count": len(tracks),
            "findings": findings, "notes": notes, "summary": summary}
