"""Safety layer: snapshot / changelog / rollback / dry-run for write tools.

Lives on the MCP-SERVER side -- the server can do file I/O, the FL controller
script cannot. Every write tool routes through :func:`safe_write`, which
snapshots the affected scope, logs the change, executes, reads back, and
returns before+after so the caller (and a human) can see exactly what changed.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections import deque
from pathlib import Path

from .protocol import (
    CMD_CHANNEL_GET,
    CMD_CHANNEL_LIST,
    CMD_CHANNEL_SELECTED,
    CMD_GET_PROJECT_STATE,
    CMD_GET_TEMPO,
    CMD_MIXER_GET_ROUTING,
    CMD_MIXER_GET_TRACK,
    CMD_MIXER_LIST_TRACKS,
    CMD_PATTERN_LIST,
    CMD_PLUGIN_GET_PARAM,
)

_DIR = Path.home() / ".flstudio-mcp"
_PATH = _DIR / "changelog.jsonl"
_MAX = 50
_SCHEMA_VERSION = 1


class ChangeLog:
    """Rolling deque of the last ``_MAX`` writes, persisted to a jsonl file."""

    def __init__(self, path: Path = _PATH, max_entries: int = _MAX) -> None:
        self._path = Path(path)
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._dq: deque = deque(maxlen=max_entries)
        self._load()

    def _load(self) -> None:
        try:
            if self._path.exists():
                migrated = False
                for line in self._path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line:
                        raw = json.loads(line)
                        entry = self._normalize(raw)
                        migrated = migrated or entry != raw
                        self._dq.append(entry)
                if migrated:
                    self._persist()
        except Exception:
            pass

    def _persist(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text("".join(json.dumps(e) + "\n" for e in self._dq), encoding="utf-8")
        except Exception:
            pass

    def _normalize(self, entry: dict) -> dict:
        out = dict(entry)
        out.setdefault("schema_version", _SCHEMA_VERSION)
        out.setdefault("change_id", _new_change_id())
        out.setdefault("ts", time.time())
        return out

    def append(self, entry: dict) -> dict:
        entry = self._normalize(entry)
        with self._lock:
            self._dq.append(entry)
            self._persist()
        return entry

    def pop_last(self):
        with self._lock:
            if not self._dq:
                return None
            entry = self._dq.pop()
            self._persist()
            return entry

    def pop_latest_matching(self, change_id: str):
        with self._lock:
            if not self._dq:
                return None, "empty"
            latest = self._dq[-1]
            if latest.get("change_id") == change_id:
                entry = self._dq.pop()
                self._persist()
                return entry, None
            for entry in self._dq:
                if entry.get("change_id") == change_id:
                    return None, "non_lifo"
            return None, "not_found"

    def recent(self, n: int = 10, *, include_payload: bool = False) -> list:
        with self._lock:
            entries = list(self._dq)[-max(0, int(n)) :]
        if include_payload:
            return entries
        return [_entry_summary(e) for e in entries]

    def path(self) -> str:
        return str(self._path)

    def export(self, output_path: str | None = None, *, include_payload: bool = True) -> dict:
        entries = self.recent(self._max_entries, include_payload=include_payload)
        data = {
            "schema_version": _SCHEMA_VERSION,
            "exported_at": time.time(),
            "count": len(entries),
            "entries": entries,
        }
        if output_path:
            out = Path(output_path).expanduser()
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(data, indent=2), encoding="utf-8")
            data["path"] = str(out)
        else:
            data["path"] = self.path()
            data["format"] = "jsonl"
        return data


def _new_change_id() -> str:
    return f"chg_{time.time_ns()}_{uuid.uuid4().hex[:8]}"


def _entry_summary(entry: dict) -> dict:
    out = {
        "change_id": entry.get("change_id"),
        "ts": entry.get("ts"),
        "tool": entry.get("tool"),
        "scope": entry.get("scope"),
        "group": bool(entry.get("group")),
        "command": entry.get("command"),
    }
    if entry.get("rollback_note"):
        out["rollback_note"] = entry.get("rollback_note")
    return out


_log = ChangeLog()
_dry_run = False


def set_dry_run(enabled) -> dict:
    global _dry_run
    _dry_run = bool(enabled)
    return {"dry_run": _dry_run}


def is_dry_run() -> bool:
    return _dry_run


def get_changelog() -> ChangeLog:
    return _log


def take_snapshot(bridge, scope):
    """Read current state for a scope so it can be restored or recorded.

    scope: "mixer_track:N" | "channel:N" | "mixer_all" | "channels_all"
           | "plugin_param:TRACK:SLOT:PARAM" | "tempo" | "selected_channel"
           | "patterns_all" | "project_state"
    """
    kind, _, arg = str(scope).partition(":")
    if kind == "tempo":
        return bridge.call(CMD_GET_TEMPO)
    if kind == "selected_channel":
        return bridge.call(CMD_CHANNEL_SELECTED)
    if kind == "project_state":
        return bridge.call(CMD_GET_PROJECT_STATE)
    if kind == "patterns_all":
        from .connection import fetch_all_pages

        out = fetch_all_pages(bridge, CMD_PATTERN_LIST, "patterns")
        out["project"] = bridge.call(CMD_GET_PROJECT_STATE)
        return out
    if kind == "mixer_track":
        return bridge.call(CMD_MIXER_GET_TRACK, {"index": int(arg)})
    if kind == "channel":
        return bridge.call(CMD_CHANNEL_GET, {"index": int(arg)})
    if kind == "plugin_param":
        track, slot, idx = (int(x) for x in arg.split(":"))
        return bridge.call(CMD_PLUGIN_GET_PARAM, {"track": track, "slot": slot, "param": idx})
    if kind == "route":
        src, dst = (int(x) for x in arg.split(":"))
        info = bridge.call(CMD_MIXER_GET_ROUTING, {"track": src})
        enabled = any(d.get("dst") == dst for d in info.get("routes_to", []))
        return {"src": src, "dst": dst, "enabled": enabled}
    if kind == "mixer_all":
        from .connection import fetch_all_pages

        return fetch_all_pages(bridge, CMD_MIXER_LIST_TRACKS, "tracks")
    if kind == "channels_all":
        from .connection import fetch_all_pages

        return fetch_all_pages(bridge, CMD_CHANNEL_LIST, "channels")
    raise ValueError(f"unknown snapshot scope: {scope!r}")


def _dry_run_plan(tool, command, params):
    return {
        "ok": True,
        "dry_run": True,
        "planned": {"tool": tool, "command": command, "params": params},
    }


def _verify_retry(bridge, command, params, result, verify, attempts=4, delay=0.06):
    """Re-issue a toggle-style command until its reported state sticks.

    FL occasionally drops a mute/solo toggle when it lands too close to other
    writes (it coalesces these over a short window). Each re-issue is a fresh
    SysEx = a fresh FL script-tick + latency = spacing, so it lands.
    """
    if verify is None:
        return result
    field, expected = verify
    n = 0
    while result.get(field) != expected and n < attempts:
        time.sleep(delay)
        result = bridge.call(command, params)
        n += 1
    return result


def safe_write(bridge, *, tool, scope, command, params, build_restore, verify=None):
    """Snapshot -> log -> execute -> (verify+retry) -> read back. Honors dry-run.

    ``build_restore(before)`` returns ``{"command", "params"}`` that undoes
    this change. ``verify=(field, expected)`` re-issues the command until the
    reported state matches (used for flaky toggle writes like mute/solo).
    """
    if _dry_run:
        return _dry_run_plan(tool, command, params)
    before = take_snapshot(bridge, scope)
    restore = build_restore(before)
    echo = bridge.call(command, params)
    echo = _verify_retry(bridge, command, params, echo, verify)
    # FL commits some writes (notably mixer fader volume/pan) on a LATER
    # script-tick, so the handler's SAME-tick readback (echo) can report the
    # stale pre-write value. Re-read the scope on a FRESH tick for the TRUE
    # post-write state. Fall back to the echo if the scope can't be re-read.
    try:
        after = take_snapshot(bridge, scope)
    except Exception:
        after = echo
    entry = _log.append(
        {
            "tool": tool,
            "scope": scope,
            "command": command,
            "params": params,
            "before": before,
            "after": after,
            "echo": echo,
            "restore": restore,
            "ts": time.time(),
        }
    )
    return {"ok": True, "change_id": entry["change_id"], "before": before, "after": after}


def safe_piano_roll_write(bridge, *, tool, params, apply):
    """Run a generated Piano Roll script and log FL undo as the restore action.

    FL's Piano Roll scripting API can mutate notes, but the controller API
    cannot read those notes back into the MCP server. The generated scripts wrap
    their edit in ``flp.score.undoSection()`` when available, so the reversible
    primitive we can expose is FL's own undo stack via ``general.undoUp``.
    """
    from . import protocol

    if _dry_run:
        return _dry_run_plan(tool, "piano_roll_apply", params)
    before = {"undo_backed": True, "note_readback_available": False}
    result = apply()
    restore = {"command": protocol.CMD_GENERAL_UNDO, "params": {}}
    entry = {
        "tool": tool,
        "scope": "piano_roll",
        "command": "piano_roll_apply",
        "params": params,
        "before": before,
        "after": result,
        "echo": result,
        "restore": restore,
        "ts": time.time(),
        "rollback_note": "Uses FL Studio undo for the generated Piano Roll script.",
    }
    entry = _log.append(entry)
    return {
        "ok": True,
        "change_id": entry["change_id"],
        "before": before,
        "after": result,
        "rollback": "fl_rollback_last_change uses FL Studio undo for this Piano Roll edit",
    }


def safe_write_group(bridge, *, tool, scope, writes):
    """Apply several param writes as ONE rollback unit.

    ``writes`` is a list of dicts, each:
        {"snap_scope": "plugin_param:T:S:I",   # what to snapshot for restore
         "command": CMD, "params": {...},      # the write to execute
         "restore": callable(before)->{"command","params"}}  # how to undo it

    Snapshots ALL writes first (so we capture originals before any change),
    then executes them, and logs ONE changelog entry whose ``restores`` is a
    LIST -- so :func:`rollback_last_change` reverts the whole group atomically.
    Honors dry-run. Returns {"ok", "before":[...], "after":[...]}.
    """
    if _dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "planned": {
                "tool": tool,
                "scope": scope,
                "writes": [{"command": w["command"], "params": w["params"]} for w in writes],
            },
        }
    befores, restores = [], []
    for w in writes:  # snapshot all first
        before = take_snapshot(bridge, w["snap_scope"])
        befores.append(before)
        restores.append(w["restore"](before))
    afters = [bridge.call(w["command"], w["params"]) for w in writes]
    entry = _log.append(
        {
            "tool": tool,
            "scope": scope,
            "group": True,
            "befores": befores,
            "afters": afters,
            "restores": restores,
            "ts": time.time(),
        }
    )
    return {"ok": True, "change_id": entry["change_id"], "before": befores, "after": afters}


def rollback_last_change(bridge):
    entry = _log.pop_last()
    if entry is None:
        return {"ok": False, "error": "changelog is empty"}
    return _rollback_entry(bridge, entry)


def rollback_change(bridge, change_id: str):
    entry, error = _log.pop_latest_matching(str(change_id))
    if entry is not None:
        return _rollback_entry(bridge, entry)
    if error == "non_lifo":
        return {
            "ok": False,
            "error": "change is not the latest entry; refusing non-LIFO rollback",
            "change_id": change_id,
        }
    if error == "empty":
        return {"ok": False, "error": "changelog is empty", "change_id": change_id}
    return {"ok": False, "error": "change_id not found", "change_id": change_id}


def change_history(limit: int = 10, *, include_payload: bool = False) -> dict:
    entries = _log.recent(limit, include_payload=include_payload)
    return {"ok": True, "count": len(entries), "entries": entries}


def export_change_log(output_path: str | None = None, *, include_payload: bool = True) -> dict:
    return {"ok": True, **_log.export(output_path, include_payload=include_payload)}


def _rollback_entry(bridge, entry: dict):
    change_id = entry.get("change_id")
    if entry.get("group"):  # grouped write -> replay every restore
        restored = [
            bridge.call(r["command"], r.get("params") or {})
            for r in reversed(entry.get("restores") or [])
        ]
        return {
            "ok": True,
            "rolled_back": entry.get("tool"),
            "scope": entry.get("scope"),
            "change_id": change_id,
            "restored": restored,
        }
    restore = entry.get("restore")
    if not restore:
        return {
            "ok": False,
            "error": "entry has no restore action",
            "tool": entry.get("tool"),
            "change_id": change_id,
        }
    rparams = restore.get("params") or {}
    restored = bridge.call(restore["command"], rparams)
    # mute/solo restores are toggles -> verify+retry like safe_write
    if "state" in rparams:
        field = "mute" if "mute" in restored else ("solo" if "solo" in restored else None)
        if field is not None:
            restored = _verify_retry(
                bridge, restore["command"], rparams, restored, (field, rparams["state"])
            )
    return {
        "ok": True,
        "rolled_back": entry.get("tool"),
        "scope": entry.get("scope"),
        "change_id": change_id,
        "restored": restored,
    }
