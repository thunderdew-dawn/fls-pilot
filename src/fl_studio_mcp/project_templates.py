"""Read-only project template topology classification.

The classifier turns raw mixer/routing/channel readbacks into conservative
metadata that product workflows can use before making judgement calls. It does
not create executable operations and it does not mutate FL Studio state.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any


ELECTRO_TEMPLATE_NAME = "Electro"

ROLE_PREMASTER = "premaster"
ROLE_STEM_BUS = "stem_bus"
ROLE_SOURCE = "source"
ROLE_SIDECHAIN_CONTROL = "sidechain_control"
ROLE_RESERVED_PLACEHOLDER = "template_reserved_placeholder"

_DEFAULT_INSERT_RE = re.compile(r"^\s*insert\s+(\d+)\s*$", re.I)


def classify_topology(
    mixer_tracks: Iterable[Mapping[str, Any]],
    routing_rows: Iterable[Mapping[str, Any]] | None = None,
    channel_rows: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Classify a known mixer template from read-only project data.

    ``mixer_tracks`` may be rows from ``mixer_list_tracks`` or the normalised
    Mix Review snapshot. ``routing_rows`` may be rows from
    ``mixer_get_routing_all``; when omitted, per-track ``routes_to`` fields from
    ``mixer_tracks`` are used.
    """
    tracks = [_normalise_track(row) for row in mixer_tracks]
    tracks = [row for row in tracks if row.get("index") is not None]
    route_source = list(routing_rows) if routing_rows is not None else tracks
    route_by = {
        int(row.get("i", row.get("index"))): list(row.get("routes_to") or [])
        for row in route_source
        if row.get("i", row.get("index")) is not None
    }
    name_by = {int(row["index"]): str(row.get("name") or "") for row in tracks}

    electro = _classify_electro(name_by, route_by)
    if electro.get("matched"):
        if channel_rows is not None:
            electro["channel_summary"] = _channel_summary(channel_rows, electro)
        return electro

    return {
        "matched": False,
        "template_name": None,
        "confidence_level": None,
        "track_roles": {},
        "summary": {
            "template_name": None,
            "matched": False,
            "reserved_placeholders": 0,
            "premaster_tracks": 0,
            "stem_bus_tracks": 0,
            "source_tracks": 0,
            "sidechain_control_tracks": 0,
        },
        "notes": [],
    }


def annotate_tracks(
    tracks: Iterable[Mapping[str, Any]],
    template_context: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Return track rows with template metadata attached."""
    roles = _roles(template_context)
    out: list[dict[str, Any]] = []
    for row in tracks:
        item = dict(row)
        idx = _track_index(item)
        role = roles.get(idx)
        if role:
            item["template_role"] = role.get("role")
            item["template_name"] = role.get("template")
            item["template_reason"] = role.get("reason")
        out.append(item)
    return out


def compact_context(template_context: Mapping[str, Any]) -> dict[str, Any] | None:
    """Compact user-facing template context."""
    if not template_context.get("matched"):
        return None
    summary = dict(template_context.get("summary") or {})
    kb_refs = [
        "knowledgebase/templates/electro_template_mixer_setup.json"
        if template_context.get("template_name") == ELECTRO_TEMPLATE_NAME
        else None
    ]
    return {
        "template_name": template_context.get("template_name"),
        "confidence_level": template_context.get("confidence_level"),
        "summary": summary,
        "notes": list(template_context.get("notes") or []),
        "kb_refs": [ref for ref in kb_refs if ref],
    }


def role_for(template_context: Mapping[str, Any], track: int | None) -> str | None:
    """Return the classified role for a track, if any."""
    if track is None:
        return None
    role = _roles(template_context).get(int(track))
    return str(role.get("role")) if role else None


def is_reserved_placeholder(template_context: Mapping[str, Any], track: int | None) -> bool:
    return role_for(template_context, track) == ROLE_RESERVED_PLACEHOLDER


def is_template_bus(template_context: Mapping[str, Any], track: int | None) -> bool:
    return role_for(template_context, track) in {
        ROLE_PREMASTER,
        ROLE_STEM_BUS,
        ROLE_SIDECHAIN_CONTROL,
    }


def is_template_control_route(
    template_context: Mapping[str, Any],
    src: int | None,
    dst: int | None,
    level: Any = None,
) -> bool:
    """Whether a route is a known non-audio/control route in a matched template."""
    if template_context.get("template_name") != ELECTRO_TEMPLATE_NAME:
        return False
    if src != 124 or dst not in {123, 125}:
        return False
    val = _as_float(level)
    return val is None or abs(val) <= 0.0001


def _classify_electro(name_by: dict[int, str], route_by: dict[int, list]) -> dict[str, Any]:
    premaster_names = {
        1: "PreMaster MS",
        2: "PreMaster M",
        3: "PreMaster S",
    }
    stem_names = {
        116: "Drums \u25ba Mix",
        117: "Kick \u25ba Mix",
        118: "Snare \u25ba Mix",
        119: "Overhead \u25ba Mix",
        120: "Instruments \u25ba Mix",
        121: "Background \u25ba Mix",
        122: "Vocals \u25ba Mix",
        123: "SideChained \u25ba Mix",
        124: "SideChain",
        125: "Sub \u25ba Mix",
    }
    expected_routes = {
        1: {0},
        2: {1},
        3: {1},
        116: {2, 3},
        117: {116, 124},
        118: {116, 124},
        119: {116},
        120: {2, 3},
        121: {2, 3},
        122: {2, 3},
        123: {2, 3},
        124: {123, 125},
        125: {2},
    }

    evidence = []
    for idx, expected in {**premaster_names, **stem_names}.items():
        if name_by.get(idx) == expected:
            evidence.append(f"name:{idx}")
    for idx, expected in expected_routes.items():
        if expected.issubset(_route_dests(route_by.get(idx, []))):
            evidence.append(f"route:{idx}")

    placeholder_tracks = []
    for idx in range(22, 116):
        if _is_default_insert_name(idx, name_by.get(idx)) and 120 in _route_dests(
            route_by.get(idx, [])
        ):
            placeholder_tracks.append(idx)

    # Require both the premaster/stem skeleton and a meaningful placeholder bank.
    matched = len(evidence) >= 20 and len(placeholder_tracks) >= 12
    if not matched:
        return {"matched": False}

    roles: dict[int, dict[str, Any]] = {}
    for idx in premaster_names:
        roles[idx] = _role(ROLE_PREMASTER, "Electro M/S premaster stage")
    for idx in stem_names:
        role = ROLE_SIDECHAIN_CONTROL if idx == 124 else ROLE_STEM_BUS
        reason = "Electro sidechain control bus" if idx == 124 else "Electro stem bus"
        roles[idx] = _role(role, reason)
    for idx in placeholder_tracks:
        roles[idx] = _role(
            ROLE_RESERVED_PLACEHOLDER,
            "Electro reserved Insert routed to Instruments Mix",
        )

    source_routes = {
        4: "kick source",
        5: "kick source",
        6: "snare source",
        7: "snare source",
        8: "overhead source",
        9: "overhead source",
        10: "sub source",
        11: "sidechained bass source",
        12: "sidechained bass source",
        13: "instrument source",
        14: "instrument source",
        15: "background source",
        16: "background source",
        17: "vocal source",
        18: "vocal source",
        19: "vocal source",
        20: "vocal source",
        21: "instrument source",
    }
    for idx, reason in source_routes.items():
        if idx in name_by:
            roles[idx] = _role(ROLE_SOURCE, f"Electro {reason}")

    summary = {
        "template_name": ELECTRO_TEMPLATE_NAME,
        "matched": True,
        "reserved_placeholders": len(placeholder_tracks),
        "reserved_placeholder_range": [min(placeholder_tracks), max(placeholder_tracks)]
        if placeholder_tracks
        else None,
        "premaster_tracks": 3,
        "stem_bus_tracks": 9,
        "source_tracks": sum(1 for r in roles.values() if r.get("role") == ROLE_SOURCE),
        "sidechain_control_tracks": 1,
    }
    return {
        "matched": True,
        "template_name": ELECTRO_TEMPLATE_NAME,
        "confidence_level": "measured_once",
        "track_roles": roles,
        "summary": summary,
        "notes": [
            "Electro template topology detected; preserve M/S premaster and stem bus structure.",
            "Default-named routed inserts in the placeholder bank are reservations, not cleanup targets.",
            "SideChain sends at level 0.0 can be control routes in this template.",
        ],
        "evidence": {
            "matched_points": evidence,
            "placeholder_tracks": placeholder_tracks,
        },
    }


def _role(role: str, reason: str) -> dict[str, str]:
    return {"role": role, "template": ELECTRO_TEMPLATE_NAME, "reason": reason}


def _normalise_track(row: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(row)
    idx = _track_index(out)
    out["index"] = idx
    return out


def _track_index(row: Mapping[str, Any]) -> int | None:
    idx = row.get("i", row.get("index", row.get("track")))
    try:
        return int(idx)
    except (TypeError, ValueError):
        return None


def _route_dests(routes: Iterable[Any]) -> set[int]:
    out: set[int] = set()
    for route in routes or []:
        dst = route.get("dst") if isinstance(route, Mapping) else route
        try:
            out.add(int(dst))
        except (TypeError, ValueError):
            continue
    return out


def _is_default_insert_name(index: int, name: str | None) -> bool:
    match = _DEFAULT_INSERT_RE.match(str(name or ""))
    return bool(match and int(match.group(1)) == int(index))


def _roles(template_context: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    raw = template_context.get("track_roles") or {}
    out: dict[int, Mapping[str, Any]] = {}
    for key, value in raw.items():
        try:
            out[int(key)] = value
        except (TypeError, ValueError):
            continue
    return out


def _channel_summary(
    channel_rows: Iterable[Mapping[str, Any]],
    template_context: Mapping[str, Any],
) -> dict[str, Any]:
    by_role: dict[str, int] = {}
    for row in channel_rows:
        track = row.get("target_mixer_track")
        role = role_for(template_context, int(track)) if isinstance(track, int) else None
        if role:
            by_role[role] = by_role.get(role, 0) + 1
    return {"target_roles": by_role}


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
