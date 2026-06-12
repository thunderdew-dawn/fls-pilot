(function () {
  "use strict";

  var data = window.FLS_PILOT_DASHBOARD_DATA || {};

  function byId(id) {
    return document.getElementById(id);
  }

  function text(id, value) {
    var node = byId(id);
    if (node) {
      node.textContent = value == null || value === "" ? "N/A" : String(value);
    }
  }

  function numberValue(value, digits) {
    if (value == null || value === "") {
      return "N/A";
    }
    var numeric = Number(value);
    if (!Number.isFinite(numeric)) {
      return String(value);
    }
    return digits == null ? String(Math.round(numeric)) : numeric.toFixed(digits);
  }

  function bpm(value) {
    if (value == null) {
      return "N/A";
    }
    return numberValue(value, 3);
  }

  function ms(value) {
    if (value == null) {
      return "N/A";
    }
    return numberValue(value) + " ms";
  }

  function yesNo(value) {
    return value ? "YES" : "NO";
  }

  function stateLabel(state) {
    if (!state) {
      return "Unavailable";
    }
    if (state === "server-state") {
      return "Server";
    }
    return state.charAt(0).toUpperCase() + state.slice(1);
  }

  function generatedTime(value) {
    var date = value ? new Date(value) : null;
    if (!date || Number.isNaN(date.getTime())) {
      return "N/A";
    }
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }

  function count(resource) {
    if (!resource || resource.state !== "live") {
      return "N/A";
    }
    return resource.total == null ? resource.shown || 0 : resource.total;
  }

  function setBridge() {
    var bridge = data.bridge || {};
    var project = data.project || {};
    var live = bridge.state === "live";
    var pill = byId("bridge-pill");
    var state = byId("bridge-state");
    var dot = byId("connection-dot");

    if (pill) {
      pill.textContent = live ? "Live" : "Unavailable";
      pill.className = live ? "pill pill-live" : "pill pill-unavailable";
    }
    if (state) {
      state.textContent = live ? "Alive" : "Unavailable";
      state.parentElement.classList.toggle("unavailable", !live);
    }
    if (dot) {
      dot.classList.toggle("live", live);
    }

    text("heartbeat-age", ms(bridge.heartbeat_age_ms));
    text("controller-status", live ? "OK" : "Check");
    text("bridge-detail", bridge.error || "Controller heartbeat is current.");
    text("connected-version", project.fl_version || bridge.fl_version || "Version unavailable");
    text("connected-target", live ? "FL Studio (Local)" : "FL Studio");
  }

  function setProject() {
    var project = data.project || {};
    var resources = data.resources || {};
    text("tempo-value", bpm(project.tempo_bpm));
    text("channel-count", project.channel_count == null ? count(resources.channels) : project.channel_count);
    text("mixer-count", project.mixer_track_count == null ? count(resources.mixer) : project.mixer_track_count);
    text("pattern-count", project.pattern_count == null ? count(resources.patterns) : project.pattern_count);
    text(
      "playlist-count",
      project.playlist_track_count == null ? count(resources.playlist) : project.playlist_track_count
    );
  }

  function setTransport() {
    var transport = data.transport || {};
    var project = data.project || {};
    var playing = transport.playing;
    if (playing == null) {
      playing = project.playing;
    }
    var recording = transport.recording;
    if (recording == null) {
      recording = project.recording;
    }
    text("playing-state", playing == null ? "N/A" : yesNo(Boolean(playing)));
    text("record-state", recording == null ? "N/A" : recording ? "ON" : "OFF");
    text("song-position", formatPosition(transport.song_position));
  }

  function formatPosition(value) {
    if (value == null) {
      return "N/A";
    }
    if (typeof value === "object") {
      if (value.song_position != null) {
        return formatPosition(value.song_position);
      }
      if (value.position != null) {
        return formatPosition(value.position);
      }
    }
    return String(value);
  }

  function setSafety() {
    var safety = data.safety || {};
    text("read-only-state", yesNo(safety.read_only !== false));
    text("rollback-state", safety.rollback_available ? "YES" : "NO");
    text("dry-run-state", safety.dry_run_available ? "YES" : "NO");
  }

  function setRisk() {
    var risk = (data.analysis || {}).mix_risk || {};
    text("mix-risk-state", stateLabel(risk.state || "limited"));
    text("mix-risk-detail", risk.detail || risk.headline || "Run Mix Review for audio-level evidence.");
  }

  function setOrganization() {
    var container = byId("organization-list");
    var organization = (data.analysis || {}).organization || {};
    var signals = organization.signals || [];
    if (!container) {
      return;
    }
    container.innerHTML = "";
    if (!signals.length) {
      signals = [
        {
          label: "Organization Signals",
          value: "N/A",
          state: "unavailable",
          detail: "No project metadata was available."
        }
      ];
    }
    signals.slice(0, 7).forEach(function (signal) {
      var item = document.createElement("div");
      item.className = "signal-item";
      item.dataset.state = signal.state || "live";
      item.title = signal.detail || "";

      var label = document.createElement("span");
      label.textContent = signal.label || "Signal";
      var value = document.createElement("strong");
      value.className = "signal-value";
      value.textContent = signal.value == null ? "N/A" : String(signal.value);
      item.append(label, value);
      container.appendChild(item);
    });
  }

  function setEvidence() {
    var table = byId("evidence-table");
    var evidence = data.evidence || [];
    if (!table) {
      return;
    }
    table.innerHTML = "";
    if (!evidence.length) {
      evidence = [
        {
          label: "Dashboard data",
          state: "unavailable",
          value: "N/A",
          source: "Generated data",
          detail: "Run fls-pilot-dashboard to generate current local data."
        }
      ];
    }
    evidence.forEach(function (entry) {
      var row = document.createElement("div");
      row.className = "evidence-row";
      row.dataset.state = entry.state || "unavailable";

      var state = document.createElement("span");
      state.className = "evidence-state";
      state.textContent = stateLabel(entry.state || "unavailable");

      var label = document.createElement("strong");
      label.textContent = entry.label || "Evidence";

      var value = document.createElement("span");
      value.textContent = entry.value == null ? "N/A" : String(entry.value);

      var source = document.createElement("span");
      source.textContent = entry.source || entry.detail || "Source unavailable";
      source.title = entry.detail || "";

      row.append(state, label, value, source);
      table.appendChild(row);
    });
  }

  function setConfidence() {
    var evidence = data.evidence || [];
    var measured = evidence.filter(function (entry) {
      return entry.state !== "limited";
    });
    var live = evidence.filter(function (entry) {
      return entry.state === "live";
    });
    var denominator = Math.max(1, measured.length || evidence.length || 1);
    var confidence = Math.round((live.length / denominator) * 100);
    text("data-confidence", confidence + "%");
  }

  function wireActions() {
    var refresh = byId("refresh-button");
    if (refresh) {
      refresh.addEventListener("click", function () {
        window.location.reload();
      });
    }

    var copy = byId("copy-json");
    if (copy) {
      copy.addEventListener("click", function () {
        var payload = JSON.stringify(data, null, 2);
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(payload).then(function () {
            copy.textContent = "Copied";
            window.setTimeout(function () {
              copy.textContent = "Copy JSON";
            }, 1200);
          });
        }
      });
    }

    document.querySelectorAll(".nav-item").forEach(function (button) {
      button.addEventListener("click", function () {
        document.querySelectorAll(".nav-item").forEach(function (item) {
          item.classList.remove("active");
        });
        button.classList.add("active");
        var target = byId(button.dataset.target);
        if (target) {
          target.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      });
    });
  }

  function setHeader() {
    var version = (data.app || {}).target_version || "v3 alpha";
    text("version-pill", version);
    text("refresh-time", generatedTime(data.generated_at));
  }

  function init() {
    setHeader();
    setBridge();
    setProject();
    setTransport();
    setSafety();
    setRisk();
    setOrganization();
    setEvidence();
    setConfidence();
    wireActions();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
