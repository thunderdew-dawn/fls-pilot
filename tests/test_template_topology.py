#!/usr/bin/env python3
"""Regression tests for template-aware project diagnostics."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp import project_templates as templates  # noqa: E402
from fl_studio_mcp import protocol  # noqa: E402
from fl_studio_mcp.music import mix_doctor as md  # noqa: E402
from fl_studio_mcp.tools import routing  # noqa: E402


def _route(*dests):
    return [{"dst": dst, "dst_name": f"Track {dst}", "level": 0.8} for dst in dests]


def _electro_rows(placeholder_stop: int = 33):
    rows = [
        {"i": 0, "name": "Master", "routes_to": []},
        {"i": 1, "name": "PreMaster MS", "routes_to": _route(0)},
        {"i": 2, "name": "PreMaster M", "routes_to": _route(1)},
        {"i": 3, "name": "PreMaster S", "routes_to": _route(1)},
        {"i": 4, "name": "Kick 1", "routes_to": _route(117)},
        {"i": 5, "name": "Kick 2", "routes_to": _route(117)},
        {"i": 6, "name": "Snare 1", "routes_to": _route(118)},
        {"i": 7, "name": "Snare 2", "routes_to": _route(118)},
        {"i": 8, "name": "Hi-Hats", "routes_to": _route(119)},
        {"i": 9, "name": "Cymbals", "routes_to": _route(119)},
        {"i": 10, "name": "Sub 1", "routes_to": _route(125)},
        {"i": 11, "name": "Bass 1", "routes_to": _route(123)},
        {"i": 12, "name": "Bass 2", "routes_to": _route(123)},
        {"i": 13, "name": "Synth 1", "routes_to": _route(120)},
        {"i": 14, "name": "Synth 2", "routes_to": _route(120)},
        {"i": 15, "name": "Strings", "routes_to": _route(121)},
        {"i": 16, "name": "Pad", "routes_to": _route(121)},
        {"i": 17, "name": "Vocals 1", "routes_to": _route(122)},
        {"i": 18, "name": "Vocals 2", "routes_to": _route(122)},
        {"i": 19, "name": "Vocals 3", "routes_to": _route(122)},
        {"i": 20, "name": "Vocals Back", "routes_to": _route(122)},
        {"i": 21, "name": "Riser Noise Metal", "routes_to": _route(120)},
        {"i": 116, "name": "Drums \u25ba Mix", "routes_to": _route(2, 3)},
        {"i": 117, "name": "Kick \u25ba Mix", "routes_to": _route(116, 124)},
        {"i": 118, "name": "Snare \u25ba Mix", "routes_to": _route(116, 124)},
        {"i": 119, "name": "Overhead \u25ba Mix", "routes_to": _route(116)},
        {"i": 120, "name": "Instruments \u25ba Mix", "routes_to": _route(2, 3)},
        {"i": 121, "name": "Background \u25ba Mix", "routes_to": _route(2, 3)},
        {"i": 122, "name": "Vocals \u25ba Mix", "routes_to": _route(2, 3)},
        {"i": 123, "name": "SideChained \u25ba Mix", "routes_to": _route(2, 3)},
        {
            "i": 124,
            "name": "SideChain",
            "routes_to": [
                {"dst": 123, "dst_name": "SideChained \u25ba Mix", "level": 0.0},
                {"dst": 125, "dst_name": "Sub \u25ba Mix", "level": 0.0},
            ],
        },
        {"i": 125, "name": "Sub \u25ba Mix", "routes_to": _route(2), "stereo_sep": 1.0},
    ]
    rows.extend(
        {"i": idx, "name": f"Insert {idx}", "routes_to": _route(120)}
        for idx in range(22, placeholder_stop + 1)
    )
    return sorted(rows, key=lambda row: row["i"])


def _snapshot_tracks(rows):
    out = []
    for row in rows:
        out.append(
            {
                "index": row["i"],
                "name": row["name"],
                "vol_db": 0.0,
                "vol_norm": 0.8,
                "pan": 0.0,
                "stereo_sep": row.get("stereo_sep", 0.0),
                "mute": False,
                "solo": False,
                "peak_db": None,
                "plugins": [],
                "routes_to": row.get("routes_to", []),
            }
        )
    return out


def test_electro_topology_classifier_marks_reserved_placeholders() -> None:
    rows = _electro_rows()
    context = templates.classify_topology(rows, rows)

    assert context["matched"] is True
    assert context["template_name"] == "Electro"
    assert templates.role_for(context, 1) == templates.ROLE_PREMASTER
    assert templates.role_for(context, 116) == templates.ROLE_STEM_BUS
    assert templates.role_for(context, 124) == templates.ROLE_SIDECHAIN_CONTROL
    assert templates.role_for(context, 22) == templates.ROLE_RESERVED_PLACEHOLDER
    assert templates.is_template_control_route(context, 124, 123, 0.0) is True


def test_mix_review_suppresses_electro_placeholder_and_bus_false_findings() -> None:
    tracks = _snapshot_tracks(_electro_rows())
    context = templates.classify_topology(tracks)
    snap = {
        "playing": False,
        "levels_valid": False,
        "tracks": templates.annotate_tracks(tracks, context),
        "template_context": context,
    }

    result = md.diagnose(snap)
    hpf_tracks = {f["track"] for f in result["findings"] if f["rule"] == "missing_hpf"}
    assert "Insert 22" not in hpf_tracks
    assert "PreMaster MS" not in hpf_tracks
    assert "Instruments \u25ba Mix" not in hpf_tracks
    assert "ungrouped" not in {f["rule"] for f in result["findings"]}
    assert result["template_context"]["template_name"] == "Electro"


def test_low_end_review_treats_electro_sub_bus_as_template_context() -> None:
    tracks = _snapshot_tracks(_electro_rows())
    context = templates.classify_topology(tracks)
    snap = {
        "playing": False,
        "levels_valid": False,
        "tracks": templates.annotate_tracks(tracks, context),
        "template_context": context,
    }

    result = md.low_end_stereo_safety(snap)
    hit_pairs = {(f["rule"], f["track"]) for f in result["findings"]}
    hit_rules = {f["rule"] for f in result["findings"]}
    assert ("low_end_off_center", "Bass 1") not in hit_pairs
    assert "low_end_layering_review" not in hit_rules
    assert not any(
        f["rule"] == "low_end_stereo_width" and f["track"] == "Sub \u25ba Mix"
        for f in result["findings"]
    )
    assert result["template_context"]["template_name"] == "Electro"


class _CleanupBridge:
    def call(self, command, params=None):
        if command == protocol.CMD_PLUGIN_LIST:
            return {"track": (params or {}).get("track"), "slots": []}
        raise AssertionError(f"unexpected command: {command!r}")


def test_cleanup_preserves_electro_reserved_placeholder_routes(monkeypatch) -> None:
    rows = _electro_rows()

    def fake_fetch(_bridge, command, key):
        if command == protocol.CMD_CHANNEL_ROUTING_SUMMARY:
            return {"channels": []}
        if command == protocol.CMD_MIXER_GET_ROUTING_ALL:
            return {"routing": rows}
        raise AssertionError(f"unexpected fetch {command}/{key}")

    monkeypatch.setattr(routing, "fetch_all_pages", fake_fetch)
    result = routing.detect_cleanup(_CleanupBridge(), max_plugin_checks=120)

    unused = {row["track"] for row in result["unused_mixer_tracks"]}
    assert 22 not in unused
    assert result["template_context"]["template_name"] == "Electro"
