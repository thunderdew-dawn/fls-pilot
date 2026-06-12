window.FLS_PILOT_DASHBOARD_DATA = {
  "schema_version": 1,
  "app": {
    "name": "fls-pilot",
    "version": "3.0.0a1",
    "target_version": "v3 alpha"
  },
  "mode": "read-only",
  "generated_at": "1970-01-01T00:00:00Z",
  "bridge": {
    "state": "unavailable",
    "alive": false,
    "heartbeat_age_ms": null,
    "fl_version": null,
    "error": "Run fls-pilot-dashboard to generate current local data."
  },
  "project": {
    "state": "unavailable"
  },
  "transport": {
    "state": "unavailable"
  },
  "resources": {
    "channels": { "state": "unavailable", "total": 0, "shown": 0, "items": [] },
    "mixer": { "state": "unavailable", "total": 0, "shown": 0, "items": [] },
    "patterns": { "state": "unavailable", "total": 0, "shown": 0, "items": [] },
    "playlist": { "state": "unavailable", "total": 0, "shown": 0, "items": [] }
  },
  "safety": {
    "state": "server-state",
    "read_only": true,
    "dry_run_available": true,
    "rollback_available": false
  },
  "analysis": {
    "mix_risk": {
      "state": "limited",
      "headline": "Audio peak/headroom risk is not measured by this dashboard.",
      "detail": "Run Mix Review or peak watch for audio-level evidence."
    },
    "organization": {
      "state": "unavailable",
      "signals": []
    }
  },
  "evidence": []
};
