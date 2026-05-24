# name=FLStudioMCP
# url=https://github.com/paper-kasu/flstudio-mcp
# receiveFrom=
# supportedDevices=
"""FLStudioMCP controller script -- v0.2 MIDI-only transport.

Lives at:
    Documents/Image-Line/FL Studio/Settings/Hardware/FLStudioMCP/device_FLStudioMCP.py

v0.1 tried to use a file-based JSON queue. That doesn't work: FL's
controller-script Python sandbox blocks every form of file write (open(),
os.open, os.makedirs all raise SystemError or TypeError with no useful
message). This v0.2 rewrite uses MIDI SysEx for both directions.

To activate in FL:
  1. Create two loopMIDI ports (Windows) or two IAC Driver buses (macOS):
        FLStudioMCP RX   -- the MCP server's OUTPUT, FL's INPUT
        FLStudioMCP TX   -- FL's OUTPUT,           the MCP server's INPUT
  2. Options > MIDI Settings:
        Input  list -> enable "FLStudioMCP RX", Controller type = FLStudioMCP,
                       Port = some number (e.g. 42).
        Output list -> enable "FLStudioMCP TX", Port = SAME number (42).
  3. The matching port number is how FL's `device.midiOutSysex(...)` routes
     to the right output. Without it, our responses go nowhere.

Wire format: see src/fl_studio_mcp/protocol.py.

Dependencies inside FL Studio:
  - json, base64, binascii (all available -- _json, _codecs, binascii are
    in FL's built-in module list)
  - NO socket, NO requests, NO pip packages, NO file I/O
"""

import base64
import json
import math
import time

# FL Studio's built-in API modules. These are NOT importable outside FL.
import channels
import device
import general
import midi
import mixer
import patterns
import playlist
import plugins
import transport
import ui


# ---------------------------------------------------------------------------
# Protocol constants -- MUST stay in sync with src/fl_studio_mcp/protocol.py
# ---------------------------------------------------------------------------

PROTOCOL_VERSION = 2

SYSEX_MANUFACTURER = 0x7D
SYSEX_MAGIC = (0x4D, 0x43, 0x50)   # ASCII "MCP"

DIR_REQUEST = 0x01
DIR_RESPONSE = 0x02
DIR_HEARTBEAT = 0x03

REQUEST_ID_LEN = 8
_HEADER_LEN = 1 + 3 + 1 + REQUEST_ID_LEN

HEARTBEAT_INTERVAL = 0.5  # seconds between heartbeats


# ---------------------------------------------------------------------------
# Module state
# ---------------------------------------------------------------------------

_last_heartbeat = 0.0
_fl_version = "unknown"

# `device.midiOutSysex` is what we want; some old builds expose
# `midiOutSysEx` (capital E). Resolve at OnInit.
_send_sysex_fn = None


# ---------------------------------------------------------------------------
# FL Studio lifecycle callbacks
# ---------------------------------------------------------------------------

def OnInit():
    global _fl_version, _send_sysex_fn
    try:
        _fl_version = ui.getVersion()
    except Exception:
        _fl_version = "unknown"

    # Resolve the SysEx-out function name across FL builds.
    _send_sysex_fn = getattr(device, "midiOutSysex", None)
    if _send_sysex_fn is None:
        _send_sysex_fn = getattr(device, "midiOutSysEx", None)

    print("[FLStudioMCP] Ready. FL " + str(_fl_version)
          + ", protocol v" + str(PROTOCOL_VERSION) + ".")
    if _send_sysex_fn is None:
        print("[FLStudioMCP] WARNING: device.midiOutSysex not available -- "
              "responses cannot be sent back to the MCP server.")
    # Send a heartbeat immediately so the server doesn't have to wait.
    _emit_heartbeat()
    return


def OnDeInit():
    print("[FLStudioMCP] Shutting down.")
    return


def OnIdle():
    """Called by FL frequently. Used here ONLY for heartbeat emission."""
    global _last_heartbeat
    now = time.time()
    if now - _last_heartbeat >= HEARTBEAT_INTERVAL:
        _emit_heartbeat()
        _last_heartbeat = now


def _handle_request_sysex(event, source):
    """Decode + dispatch an incoming SysEx request from the MCP server.

    Returns True if the SysEx carried our magic bytes and was a request (so
    the caller can mark event.handled). Non-SysEx MIDI and SysEx without our
    magic are ignored so we coexist with other devices on the same input port.

    FL builds differ in which callback delivers incoming SysEx: some use
    OnMidiMsg, FL 21+/scripting-v40 uses OnSysEx. Both delegate here.
    """
    sysex = getattr(event, "sysex", None)
    if sysex is None:
        return False

    raw = bytes(sysex)
    # Strip F0/F7 framing if FL gave it to us. Some builds include both
    # markers, some only F0, some neither -- be tolerant.
    if len(raw) >= 1 and raw[0] == 0xF0:
        raw = raw[1:]
    if len(raw) >= 1 and raw[-1] == 0xF7:
        raw = raw[:-1]

    decoded = _decode_message(raw)
    if decoded is None:
        # Not ours -- let FL keep processing as it would normally.
        return False

    direction, request_id, request = decoded
    if direction != DIR_REQUEST:
        # Not for us (could be a stray response heard back on the input).
        return False

    command = request.get("cmd", "")
    params = request.get("params") or {}

    try:
        result = _dispatch(command, params)
        payload = {"v": PROTOCOL_VERSION, "ok": True, "data": result}
    except _ClientError as e:
        payload = {"v": PROTOCOL_VERSION, "ok": False, "error": str(e), "code": e.code}
    except Exception as e:
        payload = {
            "v": PROTOCOL_VERSION,
            "ok": False,
            "error": "%s: %s" % (type(e).__name__, e),
            "code": "internal_error",
        }

    _send_message(DIR_RESPONSE, request_id, payload)
    return True


def OnMidiMsg(event):
    """Some FL builds deliver incoming SysEx through this callback."""
    event.handled = _handle_request_sysex(event, "OnMidiMsg")


def OnSysEx(event):
    """FL 21+ / MIDI scripting v40 delivers incoming SysEx here."""
    event.handled = _handle_request_sysex(event, "OnSysEx")


def OnRefresh(flags):
    return


# ---------------------------------------------------------------------------
# SysEx encode / decode -- mirrors src/fl_studio_mcp/protocol.py
# ---------------------------------------------------------------------------

def _encode_message(direction, request_id, payload):
    # Returns the SysEx bytes WITHOUT F0/F7 framing (caller adds them).
    rid = request_id.encode("ascii")
    if len(rid) != REQUEST_ID_LEN:
        rid = (rid + b"00000000")[:REQUEST_ID_LEN]
    body_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    body_b64 = base64.b64encode(body_json.encode("ascii"))
    out = bytearray()
    out.append(SYSEX_MANUFACTURER)
    out.append(SYSEX_MAGIC[0])
    out.append(SYSEX_MAGIC[1])
    out.append(SYSEX_MAGIC[2])
    out.append(direction & 0x7F)
    out.extend(rid)
    out.extend(body_b64)
    return bytes(out)


def _decode_message(data):
    if len(data) < _HEADER_LEN:
        return None
    if data[0] != SYSEX_MANUFACTURER:
        return None
    if data[1] != SYSEX_MAGIC[0] or data[2] != SYSEX_MAGIC[1] or data[3] != SYSEX_MAGIC[2]:
        return None
    direction = data[4]
    try:
        request_id = data[5:5 + REQUEST_ID_LEN].decode("ascii", errors="replace")
    except Exception:
        return None
    body = data[_HEADER_LEN:]
    try:
        body_json = base64.b64decode(bytes(body)).decode("utf-8")
        payload = json.loads(body_json)
    except Exception:
        return None
    return direction, request_id, payload


def _send_message(direction, request_id, payload):
    if _send_sysex_fn is None:
        return
    body = _encode_message(direction, request_id, payload)
    framed = bytes([0xF0]) + body + bytes([0xF7])
    try:
        _send_sysex_fn(framed)
    except Exception as e:
        print("[FLStudioMCP] midiOutSysex failed: %s" % e)


def _emit_heartbeat():
    _send_message(
        DIR_HEARTBEAT,
        "00000000",
        {
            "v": PROTOCOL_VERSION,
            "fl_version": _fl_version,
            "ts": time.time(),
        },
    )


# ---------------------------------------------------------------------------
# Command dispatcher
# ---------------------------------------------------------------------------

class _ClientError(Exception):
    """Raised by handlers for bad input. Mapped to ok=false with code=client."""
    def __init__(self, message, code="client"):
        Exception.__init__(self, message)
        self.code = code


def _dispatch(command, params):
    handler = _HANDLERS.get(command)
    if handler is None:
        raise _ClientError("Unknown command: %s" % command, code="unknown_command")
    return handler(params)


# -- transport handlers ------------------------------------------------------

def _h_ping(params):
    return {
        "fl_version": _fl_version,
        "protocol_version": PROTOCOL_VERSION,
        "ts": time.time(),
    }


def _tempo_scale():
    # FL stores tempo as BPM * 1000 internally. Adjust here if a future FL
    # build changes the scale -- the raw value is exposed in get_tempo so the
    # ratio is observable.
    return 1000.0


def _h_get_tempo(params):
    raw = mixer.getCurrentTempo()
    return {"bpm": raw / _tempo_scale(), "raw": raw}


def _h_set_tempo(params):
    bpm = float(params.get("bpm", 0))
    if bpm < 10.0 or bpm > 999.0:
        raise _ClientError("bpm out of range (10-999)")
    flags = midi.REC_UpdateValue | midi.REC_UpdateControl
    general.processRECEvent(midi.REC_Tempo, int(bpm * _tempo_scale()), flags)
    return {"bpm": mixer.getCurrentTempo() / _tempo_scale()}


def _is_playing():
    try:
        return bool(transport.isPlaying())
    except Exception:
        return False


def _is_recording():
    try:
        return bool(transport.isRecording())
    except Exception:
        return False


def _h_play(params):
    if not _is_playing():
        transport.start()
    return {"playing": True, "recording": _is_recording()}


def _h_stop(params):
    if _is_playing():
        transport.stop()
    return {"playing": False, "recording": _is_recording()}


def _h_toggle_play(params):
    transport.start()
    return {"playing": _is_playing(), "recording": _is_recording()}


def _h_record(params):
    transport.record()
    return {"playing": _is_playing(), "recording": _is_recording()}


def _h_get_play_state(params):
    return {"playing": _is_playing(), "recording": _is_recording()}


_SONGLENGTH_MS = 0
_SONGLENGTH_ABSTICKS = 2


def _h_get_song_pos(params):
    ms = transport.getSongPos(_SONGLENGTH_MS)
    ticks = transport.getSongPos(_SONGLENGTH_ABSTICKS)
    bpm = mixer.getCurrentTempo() / _tempo_scale()
    beats = (ms / 1000.0) * (bpm / 60.0)
    return {
        "position_ms": ms,
        "position_ticks": ticks,
        "position_beats": beats,
        "bpm": bpm,
    }


def _h_set_song_pos(params):
    if "ms" in params:
        transport.setSongPos(float(params["ms"]), _SONGLENGTH_MS)
    elif "beats" in params:
        bpm = mixer.getCurrentTempo() / _tempo_scale()
        if bpm <= 0:
            bpm = 120.0
        ms = float(params["beats"]) * 60000.0 / bpm
        transport.setSongPos(ms, _SONGLENGTH_MS)
    elif "ticks" in params:
        transport.setSongPos(int(params["ticks"]), _SONGLENGTH_ABSTICKS)
    else:
        raise _ClientError("Provide one of: ms, beats, ticks")
    return _h_get_song_pos({})


# -- Phase 1: project / mixer / channel read surface -------------------------
# SysEx payloads >~1.5 KB are dropped (probe: 1000 B OK, 2000 B lost). LIST
# reads paginate by PAYLOAD BUDGET (not a fixed count) and truncate names, so a
# page never exceeds the safe size no matter how long the names are. Full
# untruncated names stay available via the single-item gets.

_LIST_BUDGET = 600   # max bytes of 'data' JSON/page -> ~843 B wire (< safe 1000)
_NAME_CAP = 24       # name length in LIST responses only


def _truncate_name(name):
    name = name or ""
    return (name[:_NAME_CAP], True) if len(name) > _NAME_CAP else (name, False)


def _paginate(total, start, entry_fn, key):
    start = max(0, min(int(start), total))
    out, i = [], start
    while i < total:
        out.append(entry_fn(i))
        i += 1
        nxt = i if i < total else None
        size = len(json.dumps({"total": total, "start": start, "next_start": nxt, key: out},
                              separators=(",", ":")))
        if size > _LIST_BUDGET and len(out) > 1:
            out.pop()           # this entry overflowed the page -> next page
            i -= 1
            break
    return {"total": total, "start": start,
            "next_start": (i if i < total else None), key: out}


def _h_get_project_state(params):
    try:
        pat_num = patterns.patternNumber()
    except Exception:
        pat_num = -1
    return {
        "fl_version": _fl_version,
        "tempo_bpm": mixer.getCurrentTempo() / _tempo_scale(),
        "playing": _is_playing(),
        "recording": _is_recording(),
        "pattern_number": pat_num,
        "pattern_count": patterns.patternCount(),
        "channel_count": channels.channelCount(),
        "mixer_track_count": mixer.trackCount(),
    }


def _mixer_track_dict(i):
    return {
        "i": i,
        "name": mixer.getTrackName(i),
        "pan": round(mixer.getTrackPan(i), 4),
        "mute": bool(mixer.isTrackMuted(i)),
        "solo": bool(mixer.isTrackSolo(i)),
        **_vol_out(mixer.getTrackVolume(i)),
    }


def _mixer_list_entry(i):
    name, cut = _truncate_name(mixer.getTrackName(i))
    e = {"i": i, "name": name, "pan": round(mixer.getTrackPan(i), 4),
         "mute": bool(mixer.isTrackMuted(i)), "solo": bool(mixer.isTrackSolo(i)),
         **_vol_out(mixer.getTrackVolume(i))}
    if cut:
        e["trunc"] = True
    return e


def _h_mixer_list_tracks(params):
    return _paginate(mixer.trackCount(), params.get("start", 0), _mixer_list_entry, "tracks")


def _h_mixer_get_track(params):
    return _mixer_track_dict(int(params.get("index", 0)))


def _channel_dict(i):
    return {
        "i": i,
        "name": channels.getChannelName(i),
        "pan": round(channels.getChannelPan(i), 4),
        "mute": bool(channels.isChannelMuted(i)),
        "solo": bool(channels.isChannelSolo(i)),
        **_vol_out(channels.getChannelVolume(i)),
    }


def _channel_list_entry(i):
    name, cut = _truncate_name(channels.getChannelName(i))
    e = {"i": i, "name": name, "pan": round(channels.getChannelPan(i), 4),
         "mute": bool(channels.isChannelMuted(i)),
         "solo": bool(channels.isChannelSolo(i)),
         **_vol_out(channels.getChannelVolume(i))}
    if cut:
        e["trunc"] = True
    return e


def _h_channel_list(params):
    return _paginate(channels.channelCount(), params.get("start", 0), _channel_list_entry, "channels")


def _h_channel_get(params):
    return _channel_dict(int(params.get("index", 0)))


# -- Phase 1A write surface --------------------------------------------------
# Volume: FL normalized 0.8 == unity (0 dB), NOT 1.0. Convert with that anchor
# and ALWAYS read back the value FL actually accepted (FL clamps).

_UNITY = 0.8


def _db_to_norm(db):
    return max(0.0, min(1.0, _UNITY * (10.0 ** (db / 20.0))))


def _norm_to_db(norm):
    return -120.0 if norm <= 0.0 else 20.0 * math.log10(norm / _UNITY)


def _vol_out(norm):
    # Unified volume representation used by EVERY volume-bearing response
    # (reads + writes, mixer + channel): normalized 0..1 and dB (0.8 = unity).
    return {"vol_norm": round(norm, 4), "vol_db": round(_norm_to_db(norm), 2)}


def _resolve_vol(p):
    v = float(p["value"])
    return _db_to_norm(v) if p.get("unit") == "db" else max(0.0, min(1.0, v))


def _clamp_pan(v):
    return max(-1.0, min(1.0, float(v)))   # FL pan range is -1..+1


def _h_mixer_set_volume(p):
    t = int(p["track"])
    mixer.setTrackVolume(t, _resolve_vol(p))
    out = {"track": t}
    out.update(_vol_out(mixer.getTrackVolume(t)))
    return out


def _h_mixer_set_pan(p):
    t = int(p["track"])
    mixer.setTrackPan(t, _clamp_pan(p["value"]))
    return {"track": t, "pan": round(mixer.getTrackPan(t), 4)}


def _h_mixer_set_mute(p):
    # FL coalesces multiple mute ops per script-tick and the explicit-value
    # form muteTrack(t,1) does not mute on this build -- so set state with a
    # single bare toggle (one per SysEx = one tick).
    t = int(p["track"])
    if bool(mixer.isTrackMuted(t)) != bool(p["state"]):
        mixer.muteTrack(t)
    return {"track": t, "mute": bool(mixer.isTrackMuted(t))}


def _h_mixer_set_solo(p):
    t = int(p["track"])
    if bool(mixer.isTrackSolo(t)) != bool(p["state"]):
        mixer.soloTrack(t)
    return {"track": t, "solo": bool(mixer.isTrackSolo(t))}


def _h_mixer_set_name(p):
    t = int(p["track"])
    mixer.setTrackName(t, str(p["name"]))
    return {"track": t, "name": mixer.getTrackName(t)}


def _h_channel_set_volume(p):
    c = int(p["channel"])
    channels.setChannelVolume(c, _resolve_vol(p))
    out = {"channel": c}
    out.update(_vol_out(channels.getChannelVolume(c)))
    return out


def _h_channel_set_pan(p):
    c = int(p["channel"])
    channels.setChannelPan(c, _clamp_pan(p["value"]))
    return {"channel": c, "pan": round(channels.getChannelPan(c), 4)}


def _h_channel_set_mute(p):
    c = int(p["channel"])
    if bool(channels.isChannelMuted(c)) != bool(p["state"]):
        channels.muteChannel(c)
    return {"channel": c, "mute": bool(channels.isChannelMuted(c))}


def _h_channel_set_solo(p):
    c = int(p["channel"])
    if bool(channels.isChannelSolo(c)) != bool(p["state"]):
        channels.soloChannel(c)
    return {"channel": c, "solo": bool(channels.isChannelSolo(c))}


# -- Phase 1B: plugin parameters --------------------------------------------
# plugins API arg order (IL-Group): getPluginName(index, slot),
# getParamCount(index, slot), getParamName(paramIndex, index, slot),
# getParamValue(paramIndex, index, slot), setParamValue(value, paramIndex,
# index, slot). For a mixer-track effect, index=mixer track, slot>=0.

def _h_plugin_list(p):
    track = int(p["track"])
    slots = []
    for s in range(10):              # 10 mixer effect slots
        try:
            if plugins.isValid(track, s):
                slots.append({"slot": s, "name": plugins.getPluginName(track, s)})
        except Exception:
            pass
    return {"track": track, "slots": slots}


def _h_plugin_get_params(p):
    track = int(p["track"])
    slot = int(p["slot"])
    if not plugins.isValid(track, slot):
        raise _ClientError("no plugin at track %d slot %d" % (track, slot))
    total = plugins.getParamCount(track, slot)
    start = max(0, int(p.get("start", 0)))
    out = []
    i = start
    scanned = 0
    while i < total and scanned < 150:        # cap scan/page (bounds VST 4240 cost)
        nm = plugins.getParamName(i, track, slot)
        cur = i
        i += 1
        scanned += 1
        if nm:                                 # skip empty-name slots (unused VST)
            out.append({
                "i": cur,
                "name": nm[:30],
                "v": round(plugins.getParamValue(cur, track, slot), 4),
                "s": (plugins.getParamValueString(cur, track, slot) or "")[:16],
            })
            if len(json.dumps(out, separators=(",", ":"))) > 480:
                break
    return {
        "track": track, "slot": slot, "plugin": plugins.getPluginName(track, slot),
        "total": total, "start": start,
        "next_start": (i if i < total else None), "params": out,
    }


def _h_plugin_get_param(p):
    track = int(p["track"])
    slot = int(p["slot"])
    idx = int(p["param"])
    if not plugins.isValid(track, slot):
        raise _ClientError("no plugin at track %d slot %d" % (track, slot))
    return {
        "track": track, "slot": slot, "param": idx,
        "name": plugins.getParamName(idx, track, slot),
        "v": round(plugins.getParamValue(idx, track, slot), 4),
        "s": (plugins.getParamValueString(idx, track, slot) or ""),
    }


def _h_plugin_set_param(p):
    track = int(p["track"])
    slot = int(p["slot"])
    idx = int(p["param"])
    val = float(p["value"])
    if not plugins.isValid(track, slot):
        raise _ClientError("no plugin at track %d slot %d" % (track, slot))
    plugins.setParamValue(val, idx, track, slot)
    return {
        "track": track, "slot": slot, "param": idx,
        "name": plugins.getParamName(idx, track, slot),
        "v": round(plugins.getParamValue(idx, track, slot), 4),
        "s": (plugins.getParamValueString(idx, track, slot) or ""),
    }


_HANDLERS = {
    "ping": _h_ping,
    "get_tempo": _h_get_tempo,
    "set_tempo": _h_set_tempo,
    "play": _h_play,
    "stop": _h_stop,
    "toggle_play": _h_toggle_play,
    "record": _h_record,
    "get_play_state": _h_get_play_state,
    "get_song_position": _h_get_song_pos,
    "set_song_position": _h_set_song_pos,
    "get_project_state": _h_get_project_state,
    "mixer_list_tracks": _h_mixer_list_tracks,
    "mixer_get_track": _h_mixer_get_track,
    "channel_list": _h_channel_list,
    "channel_get": _h_channel_get,
    "mixer_set_volume": _h_mixer_set_volume,
    "mixer_set_pan": _h_mixer_set_pan,
    "mixer_set_mute": _h_mixer_set_mute,
    "mixer_set_solo": _h_mixer_set_solo,
    "mixer_set_name": _h_mixer_set_name,
    "channel_set_volume": _h_channel_set_volume,
    "channel_set_pan": _h_channel_set_pan,
    "channel_set_mute": _h_channel_set_mute,
    "channel_set_solo": _h_channel_set_solo,
    "plugin_list": _h_plugin_list,
    "plugin_get_params": _h_plugin_get_params,
    "plugin_get_param": _h_plugin_get_param,
    "plugin_set_param": _h_plugin_set_param,
}
