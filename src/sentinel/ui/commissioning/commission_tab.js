function $(id) {
  const el = document.getElementById(id);
  if (!el) throw new Error(`Missing element: ${id}`);
  return el;
}

function api(path) {
  return `/api/v1${path}`;
}

function wsUrl(path) {
  const proto = window.location && window.location.protocol === "https:" ? "wss" : "ws";
  const host = window.location && window.location.host ? window.location.host : "localhost";
  return `${proto}://${host}${path}`;
}

function logProjectWs(action, detail) {
  const a = String(action || "").trim();
  let code = "WS-INFO-101";
  let label = "SOCKET_EVENT";
  if (a === "open") {
    code = "WS-INFO-100";
    label = "SOCKET_OPEN";
  } else if (a === "sync.request") {
    code = "WS-INFO-120";
    label = "SYNC_REQUEST";
  } else if (a === "close") {
    const d = String(detail || "").trim().toLowerCase();
    if (d === "unexpected") {
      code = "WS-ERR-310";
      label = "SOCKET_CLOSE_UNEXPECTED";
    } else {
      code = "WS-INFO-150";
      label = "SOCKET_CLOSE";
    }
  } else if (a === "connect") {
    code = "WS-INFO-102";
    label = "SOCKET_CONNECT";
  } else if (a === "error") {
    code = "WS-WARN-230";
    label = "SOCKET_ERROR";
  } else if (a === "conn-id") {
    code = "WS-INFO-103";
    label = "CONNECT_ATTEMPT";
  } else if (a === "recv:json-parse-failed") {
    code = "WS-WARN-240";
    label = "JSON_PARSE_FAILED";
  }
  try {
    const logger = window.__sentinelWsLog;
    if (typeof logger === "function") {
      logger(code, label, "project-ws", { action: a, detail: detail == null ? "" : detail });
      return;
    }
  } catch (_e) {}
  try {
    if (typeof console !== "undefined" && console.log) console.log(`[project-ws] ${a}`, detail == null ? "" : detail);
  } catch (_e) {}
}

function logCommissionWs(action, detail) {
  const a = String(action || "").trim();
  let code = "WS-INFO-160";
  let label = "COMMISSION_EVENT";
  if (a === "reconnect-sync") {
    code = "WS-INFO-121";
    label = "SYNC_RECONCILE";
  } else if (a === "snapshot:activities-applied") {
    code = "WS-INFO-140";
    label = "SNAPSHOT_APPLIED";
  } else if (a === "close") {
    code = "WS-INFO-151";
    label = "CONSUMER_CLOSE";
  }
  try {
    const logger = window.__sentinelWsLog;
    if (typeof logger === "function") {
      logger(code, label, "commission-ws", { action: a, detail: detail == null ? "" : detail });
      return;
    }
  } catch (_e) {}
  try {
    if (typeof console !== "undefined" && console.log) console.log(`[commission-ws] ${a}`, detail == null ? "" : detail);
  } catch (_e) {}
}

function formatTimestampUtc(ts) {
  const s = String(ts || "").trim();
  if (!s) return "";
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return s;
  // Compact UTC: MM-DD HH:MM:SSZ (full timestamp kept in title attributes).
  const iso = d.toISOString(); // always UTC
  const mmdd = iso.slice(5, 10);
  const time = iso.slice(11, 19);
  return `${mmdd} ${time}Z`;
}

function currentProjectId() {
  const sel = document.getElementById("projectSelect");
  return sel ? sel.value : "";
}

function isCommissionVisible() {
  const panel = document.getElementById("panel-commission");
  return !!panel && !panel.hidden;
}

function isCommissioningHydrating() {
  return !!window.__sentinelCommissioningHydrating;
}

async function refreshCommissionTopboxTitle(projectId) {
  const panel = document.getElementById("panel-commission");
  if (!panel) return;
  const title = panel.querySelector(".panel-context .panel-context-title");
  if (!title) return;

  const clientName = selectedOptionText("clientSelect");
  const projectName = selectedOptionText("projectSelect");
  const lastGen = document.getElementById("lastGeneratedLabel");
  const raw = lastGen ? String(lastGen.textContent || "").trim() : "";
  const filename = raw.toLowerCase().startsWith("last generated:") ? raw.slice("last generated:".length).trim() : raw;

  const parts = [clientName, projectName].map((s) => String(s || "").trim()).filter(Boolean);
  if (filename) parts.push(filename);
  title.textContent = parts.join(" -> ");
}

function pctStyle(pct01) {
  const pct = Math.max(0, Math.min(1, Number(pct01) || 0)) * 100;
  return { "--pct": String(pct) };
}

function applyStyleVars(el, vars) {
  for (const [k, v] of Object.entries(vars || {})) {
    el.style.setProperty(k, v);
  }
}

function ensureCommissionPies() {
  const panel = document.getElementById("panel-commission");
  if (!panel) return null;
  const shell = panel.querySelector(".commission-shell");
  if (!shell) return null;

  // Remove legacy ring KPI row; replaced by pies.
  const legacy = shell.querySelector(".commission-kpis");
  if (legacy) legacy.remove();

  let pies = document.getElementById("commissionPies");
  if (pies) return pies;

  pies = document.createElement("div");
  pies.className = "commission-pies";
  pies.id = "commissionPies";
  pies.dataset.testid = "commission-pies";

  shell.prepend(pies);

  return pies;
}

function _pieCardInnerHtml({ title, valueId, subId, pieId }) {
  return `
    <div class="piecard-title">${title}</div>
    <div class="piecard-body">
      <div class="pie" id="${pieId}" aria-label="${title}"></div>
      <div class="piecard-metrics">
        <div class="piecard-value" id="${valueId}">0%</div>
        <div class="piecard-sub" id="${subId}">0/0 passed</div>
      </div>
    </div>
  `.trim();
}

function ensurePieCard({ key, title, testId, color }) {
  const pies = ensureCommissionPies();
  if (!pies) return null;

  const cardId = `commissionPie-${key}`;
  let card = document.getElementById(cardId);
  if (card) {
    const titleEl = card.querySelector(".piecard-title");
    if (titleEl) titleEl.textContent = title;
    if (testId) card.dataset.testid = testId;
    if (color) card.style.setProperty("--pie-fill", color);
    return card;
  }

  card = document.createElement("section");
  card.className = "piecard";
  card.id = cardId;
  if (testId) card.dataset.testid = testId;
  if (color) card.style.setProperty("--pie-fill", color);

  const pieId = `${cardId}-chart`;
  const valueId = `${cardId}-value`;
  const subId = `${cardId}-sub`;
  card.innerHTML = _pieCardInnerHtml({ title, valueId, subId, pieId });

  pies.appendChild(card);
  return card;
}

function setPieCardProgress(card, { passed, total }) {
  if (!card) return;
  const p = Number(passed || 0);
  const t = Number(total || 0);
  const pct01 = t > 0 ? p / t : 0;

  const pie = card.querySelector(".pie");
  if (pie) applyStyleVars(pie, pctStyle(pct01));

  const value = card.querySelector(".piecard-value");
  if (value) value.textContent = `${Math.round(pct01 * 100)}%`;

  const sub = card.querySelector(".piecard-sub");
  if (sub) sub.textContent = `${p}/${t} passed`;
}

function updatePies(progress) {
  const counts = progress && progress.counts ? progress.counts : {};
  const system = progress?.eventSections?.system?.counts || {};
  const driver = progress?.eventSections?.driver?.counts || {};
  const devices = Array.isArray(progress?.devices) ? progress.devices : [];

  const projectCard = ensurePieCard({ key: "project", title: "Project Completion", testId: "commission-pie-project", color: "#7c3aed" });
  setPieCardProgress(projectCard, { passed: counts.pass || 0, total: counts.totalTargets || 0 });

  const systemCard = ensurePieCard({
    key: "system-events",
    title: "System Events Completion",
    testId: "commission-pie-system-events",
    color: "#177bb5",
  });
  setPieCardProgress(systemCard, { passed: system.pass || 0, total: system.totalTargets || 0 });

  const driverCard = ensurePieCard({
    key: "driver-events",
    title: "Driver Events Completion",
    testId: "commission-pie-driver-events",
    color: "#16a34a",
  });
  setPieCardProgress(driverCard, { passed: driver.pass || 0, total: driver.totalTargets || 0 });

  const seen = new Set();
  for (const d of devices) {
    if (!d || typeof d !== "object") continue;
    const deviceId = String(d.deviceId ?? "");
    if (!deviceId) continue;
    const totalTargets = Number(d?.counts?.totalTargets || 0);
    if (totalTargets <= 0) continue;
    const displayName = String(d.displayName || `Device ${deviceId}`);
    const key = `device-${deviceId}`;
    const card = ensurePieCard({
      key,
      title: displayName,
      testId: `commission-pie-device-${deviceId}`,
      color: "#f59e0b",
    });
    seen.add(`commissionPie-${key}`);
    setPieCardProgress(card, { passed: d?.counts?.pass || 0, total: totalTargets });
  }

  const pies = document.getElementById("commissionPies");
  if (pies) {
    for (const child of Array.from(pies.children)) {
      const id = child && child.id ? String(child.id) : "";
      if (!id.startsWith("commissionPie-device-")) continue;
      if (!seen.has(id)) child.remove();
    }
  }
}

function normalizeEventMessage(ev) {
  const payload = ev && typeof ev === "object" ? ev : {};
  const data = payload?.data && typeof payload.data === "object" ? payload.data : payload;
  const refs = data?.refs && typeof data.refs === "object" ? data.refs : {};

  const recordedAtUtc = String(data?.recordedAtUtc || data?.tsUtc || "");
  return {
    tsUtc: formatTimestampUtc(recordedAtUtc),
    tsUtcFull: recordedAtUtc,
    device: String(refs?.deviceName || ""),
    page: String(refs?.pageName || ""),
    button: String(refs?.buttonName || ""),
    testTarget: String(data?.targetName || ""),
    status: String(data?.outcome || data?.currentOutcome || ""),
    targetKey: String(data?.targetKey || ""),
  };
}

function appendActivityRow(msg) {
  const body = $("commissionActivityBody");
  const empty = document.getElementById("commissionActivityEmpty");
  if (empty) empty.remove();

  const tr = document.createElement("tr");
  const tdTime = document.createElement("td");
  const tdDevice = document.createElement("td");
  const tdPage = document.createElement("td");
  const tdButton = document.createElement("td");
  const tdTarget = document.createElement("td");
  const tdStatus = document.createElement("td");

  tdTime.className = "mono";
  tdDevice.className = "mono";
  tdPage.className = "mono";
  tdButton.className = "mono";
  tdTarget.className = "mono";
  tdStatus.className = "mono status-cell";

  tdTime.textContent = msg.tsUtc || "";
  tdTime.title = String(msg.tsUtcFull || msg.tsUtc || "");
  tdDevice.textContent = msg.device || "";
  tdPage.textContent = msg.page || "";
  tdButton.textContent = msg.button || "";
  tdTarget.textContent = msg.testTarget || msg.targetKey || "";
  const st = String(msg.status || "").trim().toUpperCase();
  tdStatus.textContent = st;
  tdStatus.dataset.status = st;

  tr.appendChild(tdTime);
  tr.appendChild(tdDevice);
  tr.appendChild(tdPage);
  tr.appendChild(tdButton);
  tr.appendChild(tdTarget);
  tr.appendChild(tdStatus);

  body.prepend(tr);

  while (body.children.length > 50) {
    body.removeChild(body.lastElementChild);
  }
}

function _cloneValue(value) {
  if (Array.isArray(value)) return value.map((item) => _cloneValue(item));
  if (!value || typeof value !== "object") return value;
  const out = {};
  for (const [k, v] of Object.entries(value)) out[k] = _cloneValue(v);
  return out;
}

function _storeInitialState() {
  return { projects: {} };
}

function _ensureProjectState(root, projectId) {
  const pid = String(projectId || "").trim();
  if (!pid) return null;
  if (!root.projects[pid]) {
    root.projects[pid] = {
      projectId: pid,
      progress: null,
      rollups: null,
      activities: [],
      fails: [],
      activeUpload: null,
      lastEventType: "",
      lastRecordedAtUtc: "",
    };
  }
  return root.projects[pid];
}

function _asEventActivity(payload) {
  return {
    type: "test_result",
    projectId: String(payload?.projectId || ""),
    recordedAtUtc: String(payload?.recordedAtUtc || payload?.tsUtc || ""),
    targetKey: String(payload?.targetKey || payload?.data?.targetKey || ""),
    outcome: String(payload?.outcome || payload?.currentOutcome || payload?.data?.outcome || ""),
    targetName: String(payload?.targetName || payload?.data?.targetName || ""),
    kind: String(payload?.kind || payload?.targetKind || payload?.data?.kind || payload?.data?.targetKind || ""),
    refs: _cloneValue(payload?.refs && typeof payload.refs === "object" ? payload.refs : payload?.data?.refs && typeof payload.data.refs === "object" ? payload.data.refs : {}),
    failNote: payload?.failNote == null ? null : String(payload.failNote),
  };
}

function _upsertFailRecord(fails, payload) {
  const targetKey = String(payload?.targetKey || payload?.data?.targetKey || "").trim();
  if (!targetKey) return fails;
  const outcome = String(payload?.outcome || payload?.currentOutcome || payload?.data?.outcome || "").trim().toUpperCase();
  const existing = Array.isArray(fails) ? fails.slice() : [];
  const idx = existing.findIndex((row) => String(row?.targetKey || "") === targetKey);
  if (outcome === "PASS") {
    if (idx >= 0) existing.splice(idx, 1);
    return existing;
  }
  if (outcome !== "FAIL") return existing;

  const refs = payload?.refs && typeof payload.refs === "object" ? payload.refs : payload?.data?.refs && typeof payload.data.refs === "object" ? payload.data.refs : {};
  const prev = idx >= 0 ? existing[idx] : null;
  const next = {
    targetKey,
    currentOutcome: "FAIL",
    lastTestedAtUtc: String(payload?.recordedAtUtc || payload?.tsUtc || payload?.lastTestedAtUtc || ""),
    lastFailNote: payload?.failNote == null ? String(prev?.lastFailNote || "") : String(payload.failNote || ""),
    tag: String(prev?.tag || "NOT_STARTED"),
    deviceName: String(refs?.deviceName || prev?.deviceName || ""),
    pageName: String(refs?.pageName || prev?.pageName || ""),
    buttonName: String(refs?.buttonName || prev?.buttonName || ""),
    scope: String(refs?.scope || prev?.scope || ""),
    targetName: String(payload?.targetName || prev?.targetName || ""),
    resolvedData: refs?.resolvedData == null ? prev?.resolvedData : refs.resolvedData,
  };
  if (idx >= 0) existing[idx] = next;
  else existing.unshift(next);
  return existing;
}

function reduceProjectStore(prevState, payload) {
  const state = prevState && typeof prevState === "object" ? _cloneValue(prevState) : _storeInitialState();
  const t = String(payload?.type || "").trim();
  if (!t || t === "keepalive") return state;

  const projectId = String(payload?.projectId || "").trim();
  if (!projectId) return state;

  const project = _ensureProjectState(state, projectId);
  if (!project) return state;

  project.lastEventType = t;
  project.lastRecordedAtUtc = String(payload?.recordedAtUtc || payload?.tsUtc || "");

  if (t === "commissioning_snapshot") {
    project.progress = payload?.progress ? _cloneValue(payload.progress) : null;
    project.rollups = payload?.rollups ? _cloneValue(payload.rollups) : null;
    project.activities = Array.isArray(payload?.activities) ? _cloneValue(payload.activities).slice(0, 50) : [];
    project.fails = Array.isArray(payload?.fails) ? _cloneValue(payload.fails) : [];
    project.activeUpload = payload?.activeUpload ? _cloneValue(payload.activeUpload) : null;
    return state;
  }

  if (t === "generation") {
    project.activeUpload = payload?.activeUpload
      ? _cloneValue(payload.activeUpload)
      : {
          uploadId: payload?.uploadId || null,
          projectId,
          originalFilename: payload?.originalFilename || "",
          storagePath: "",
          uploadedAtUtc: "",
        };
    return state;
  }

  if (t === "fail_tag_updated") {
    const targetKey = String(payload?.targetKey || "").trim();
    const tag = String(payload?.tag || "").trim().toUpperCase();
    project.fails = project.fails.map((row) => (String(row?.targetKey || "") === targetKey ? { ...row, tag: tag || row?.tag } : row));
    return state;
  }

  if (t === "test_result" || t === "test_result.recorded") {
    if (payload?.progress) project.progress = _cloneValue(payload.progress);
    if (payload?.rollups) project.rollups = _cloneValue(payload.rollups);
    const activity = _asEventActivity(payload);
    project.activities = [activity, ...project.activities].slice(0, 50);
    project.fails = _upsertFailRecord(project.fails, payload);
    return state;
  }

  return state;
}

function ensureSharedProjectStore() {
  if (window.__sentinelProjectStore) return window.__sentinelProjectStore;
  let state = _storeInitialState();
  const listeners = new Set();

  window.__sentinelProjectStore = {
    getState() {
      return _cloneValue(state);
    },
    dispatch(payload) {
      state = reduceProjectStore(state, payload);
      for (const listener of Array.from(listeners)) {
        try {
          listener(state, payload);
        } catch (_e) {}
      }
    },
    subscribe(listener) {
      if (typeof listener !== "function") return () => {};
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
  return window.__sentinelProjectStore;
}

function ensureSharedProjectWsManager() {
  if (window.__sentinelProjectWsManager) return window.__sentinelProjectWsManager;
  const sharedStore = ensureSharedProjectStore();

  let ws = null;
  let wsProjectId = "";
  let wsReconnectTimer = null;
  let wsReconnectDelayMs = 500;
  let wsConnSeq = 0;
  let wsState = "closed";
  let wsIntentionalClose = false;
  let idleCloseTimer = null;
  let activeProjectId = "";
  const consumers = new Map();
  const recentByProject = new Map();
  const RECENT_MAX = 100;
  const syncByProject = new Map();

  function syncStateFor(projectId) {
    const pid = String(projectId || "").trim();
    if (!pid) return { lastAppliedSeq: 0, syncInFlight: false };
    if (!syncByProject.has(pid)) syncByProject.set(pid, { lastAppliedSeq: 0, syncInFlight: false });
    return syncByProject.get(pid);
  }

  function desiredProjectId() {
    const hasActiveConsumer = Array.from(consumers.values()).some((consumer) => !!consumer && !!consumer.active);
    if (!hasActiveConsumer) return "";
    return String(activeProjectId || "").trim();
  }

  function fanOut(payload) {
    const activeProjectId = String(wsProjectId || "").trim();
    const payloadProjectId = String(payload?.projectId || "").trim();
    const cacheProjectId = payloadProjectId || activeProjectId;
    if (cacheProjectId) {
      const existing = recentByProject.get(cacheProjectId) || [];
      const next = existing.concat([payload]).slice(-RECENT_MAX);
      recentByProject.set(cacheProjectId, next);
    }
    for (const consumer of consumers.values()) {
      if (!consumer || typeof consumer.onMessage !== "function") continue;
      if (!consumer.active) continue;
      try {
        consumer.onMessage(payload);
      } catch (e) {
        logProjectWs("consumer:onMessage-failed", String(e?.message || e || ""));
      }
    }
  }

  function sendSyncRequest(projectId) {
    const pid = String(projectId || "").trim();
    if (!pid) return;
    if (!ws || ws.readyState !== 1 || String(wsProjectId || "").trim() !== pid) return;
    const sync = syncStateFor(pid);
    if (sync.syncInFlight) return;
    sync.syncInFlight = true;
    try {
      ws.send(
        JSON.stringify({
          type: "sync.request",
          projectId: pid,
          lastAppliedSeq: Number(sync.lastAppliedSeq || 0),
        })
      );
      logProjectWs("sync.request", { projectId: pid, lastAppliedSeq: Number(sync.lastAppliedSeq || 0) });
    } catch (_e) {}
  }

  function maybeRequestSyncOnOpen(projectId) {
    const pid = String(projectId || "").trim();
    if (!pid) return;
    const sync = syncStateFor(pid);
    // Fresh connect gets authoritative snapshot from server subscribe path.
    // Request replay only when we already have prior sequence state.
    if (Number(sync.lastAppliedSeq || 0) <= 0) {
      sync.syncInFlight = false;
      return;
    }
    sendSyncRequest(pid);
  }

  function applySequencedEvent(payload) {
    const pid = String(payload?.projectId || wsProjectId || "").trim();
    const t = String(payload?.type || "").trim();
    const seq = Number(payload?.seq || 0);
    const isSnapshot = t === "commissioning_snapshot" || t === "testing_snapshot";
    const sync = syncStateFor(pid);
    if (seq <= 0) {
      sharedStore.dispatch(payload);
      fanOut(payload);
      return;
    }
    if (seq <= Number(sync.lastAppliedSeq || 0)) return;
    if (!isSnapshot && seq > Number(sync.lastAppliedSeq || 0) + 1) {
      sendSyncRequest(pid);
      return;
    }
    sync.lastAppliedSeq = seq;
    sync.syncInFlight = false;
    sharedStore.dispatch(payload);
    fanOut(payload);
  }

  function dispatchIncoming(payload) {
    if (!payload || typeof payload !== "object") return;
    const t = String(payload?.type || "").trim();
    if (t === "keepalive") return;
    if (t === "replay.batch") {
      const pid = String(payload?.projectId || wsProjectId || "").trim();
      const sync = syncStateFor(pid);
      sync.syncInFlight = false;
      const events = Array.isArray(payload?.events) ? payload.events : [];
      for (const ev of events) applySequencedEvent(ev);
      return;
    }
    applySequencedEvent(payload);
  }

  function dispatchIncomingRaw(raw) {
    try {
      const payload = JSON.parse(String(raw || "{}"));
      dispatchIncoming(payload);
    } catch (e) {
      logProjectWs("recv:json-parse-failed", String(e?.message || e || ""));
    }
  }

  function clearReconnectTimer() {
    if (!wsReconnectTimer) return;
    clearTimeout(wsReconnectTimer);
    wsReconnectTimer = null;
  }

  function clearIdleCloseTimer() {
    if (!idleCloseTimer) return;
    clearTimeout(idleCloseTimer);
    idleCloseTimer = null;
  }

  function closeSocket(intentional) {
    clearReconnectTimer();
    if (!ws) {
      wsState = "closed";
      wsProjectId = "";
      return;
    }
    wsIntentionalClose = !!intentional;
    try {
      ws.close();
    } catch (e) {
      logProjectWs("close:socket-throw", String(e?.message || e || ""));
    }
  }

  function scheduleReconnect() {
    clearReconnectTimer();
    wsReconnectTimer = setTimeout(() => {
      wsReconnectTimer = null;
      connectIfNeeded(desiredProjectId());
    }, Math.min(5000, Math.max(250, wsReconnectDelayMs)));
    wsReconnectDelayMs = Math.min(5000, wsReconnectDelayMs * 2);
  }

  function connectIfNeeded(projectId) {
    const pid = String(projectId || "").trim();
    if (!pid) {
      logProjectWs("connect:missing-project-id");
      return;
    }
    if (ws && wsProjectId === pid && (wsState === "connecting" || wsState === "open")) return;

    closeSocket(true);
    clearIdleCloseTimer();

    const url = wsUrl(api(`/commissioning/projects/${encodeURIComponent(pid)}/ws`));
    const connId = ++wsConnSeq;
    wsState = "connecting";
    wsProjectId = pid;
    logProjectWs("conn-id", connId);
    logProjectWs("connect", url);
    ws = new WebSocket(url);

    ws.onopen = () => {
      if (connId !== wsConnSeq) {
        logProjectWs("open:stale-conn", connId);
        return;
      }
      wsState = "open";
      wsReconnectDelayMs = 500;
      logProjectWs("open", wsProjectId);
      maybeRequestSyncOnOpen(wsProjectId);
    };
    ws.onclose = () => {
      if (connId !== wsConnSeq) {
        logProjectWs("close:stale-conn", connId);
        return;
      }
      const intentional = wsIntentionalClose;
      wsIntentionalClose = false;
      const closingProjectId = String(wsProjectId || "").trim();
      ws = null;
      wsProjectId = "";
      wsState = "closed";
      const sync = syncStateFor(closingProjectId);
      sync.syncInFlight = false;
      logProjectWs("close", intentional ? "intentional" : "unexpected");
      if (!intentional && desiredProjectId()) scheduleReconnect();
    };
    ws.onerror = () => {
      if (connId !== wsConnSeq) {
        logProjectWs("error:stale-conn", connId);
        return;
      }
      logProjectWs("error");
      try {
        if (ws) ws.close();
      } catch (e) {
        logProjectWs("error:close-throw", String(e?.message || e || ""));
      }
    };
    ws.onmessage = (evt) => {
      if (connId !== wsConnSeq) {
        logProjectWs("recv:stale-conn", connId);
        return;
      }
      dispatchIncomingRaw(evt.data);
    };
  }

  function reconcile() {
    const pid = desiredProjectId();
    if (pid) {
      clearIdleCloseTimer();
      connectIfNeeded(pid);
      return;
    }
    if (idleCloseTimer) return;
    idleCloseTimer = setTimeout(() => {
      idleCloseTimer = null;
      if (!desiredProjectId()) closeSocket(true);
    }, 300);
  }

  window.__sentinelProjectWsManager = {
    dispatchIncoming,
    setActiveProject(projectId) {
      const pid = String(projectId || "").trim();
      if (pid === activeProjectId) return;
      activeProjectId = pid;
      reconcile();
    },
    setConsumer(id, state) {
      const key = String(id || "").trim();
      if (!key) {
        logProjectWs("consumer:set-missing-id");
        return;
      }
      const prev = consumers.get(key) || {};
      const next = {
        ...prev,
        ...state,
        active: state && Object.prototype.hasOwnProperty.call(state, "active") ? !!state.active : !!prev.active,
      };
      consumers.set(key, next);
      const pid = desiredProjectId();
      const shouldReplay = !!next.active && !prev.active;
      if (shouldReplay && typeof next.onMessage === "function" && pid) {
        const cached = recentByProject.get(pid) || [];
        for (const payload of cached) {
          try {
            next.onMessage(payload);
          } catch (e) {
            logProjectWs("consumer:replay-failed", String(e?.message || e || ""));
          }
        }
      }
      reconcile();
    },
  };
  return window.__sentinelProjectWsManager;
}

const sharedProjectWsManager = ensureSharedProjectWsManager();
const sharedProjectStore = ensureSharedProjectStore();
let commissionStoreUnsubscribe = null;

function syncAfterReconnect(projectId) {
  const pid = String(projectId || "").trim();
  if (!pid) return;
  logCommissionWs("reconnect-sync", pid);
}

function ensureCommissionHeader() {
  const div = document.getElementById("commissionSelection");
  if (div) div.remove();
}

function selectedOptionText(selectId) {
  const sel = document.getElementById(selectId);
  const opt = sel && sel.selectedOptions && sel.selectedOptions[0] ? sel.selectedOptions[0] : null;
  return opt ? String(opt.textContent || "").trim() : "";
}

function updateSelectedNames() {
  ensureCommissionHeader();
}

function setActivityRows(rows) {
  const body = $("commissionActivityBody");
  body.innerHTML = "";
  const items = Array.isArray(rows) ? rows : [];
  if (!items.length) {
    const empty = document.getElementById("commissionActivityEmpty");
    if (!empty) {
      const msg = document.createElement("div");
      msg.className = "activity-empty";
      msg.id = "commissionActivityEmpty";
      msg.textContent = "No activity yet.";
      $("commissionActivity").appendChild(msg);
    }
    return;
  }
  const empty = document.getElementById("commissionActivityEmpty");
  if (empty) empty.remove();
  const capped = items.slice(0, 50);
  for (let idx = capped.length - 1; idx >= 0; idx--) {
    const norm = normalizeEventMessage(capped[idx]);
    appendActivityRow(norm);
  }
  logCommissionWs("snapshot:activities-applied", capped.length);
}

function getProjectStoreSlice(projectId) {
  const pid = String(projectId || "").trim();
  if (!pid) return null;
  const state = sharedProjectStore.getState();
  const projects = state && state.projects && typeof state.projects === "object" ? state.projects : {};
  return projects[pid] || null;
}

function renderCommissionFromStore(projectId) {
  const slice = getProjectStoreSlice(projectId);
  if (!slice) {
    setActivityRows([]);
    updatePies(null);
    return;
  }
  const activities = Array.isArray(slice.activities) ? slice.activities : [];
  const progress = slice.progress || null;
  setActivityRows(activities);
  updatePies(progress);
}

function noopCommissionSocketConsumer() {
  // Store subscription is the canonical UI render path.
}

function handleCommissionStoreChange() {
  if (!isCommissionVisible()) return;
  renderCommissionFromStore(currentProjectId());
}

function ensureCommissionStoreSubscription() {
  if (commissionStoreUnsubscribe) return;
  commissionStoreUnsubscribe = sharedProjectStore.subscribe(() => {
    handleCommissionStoreChange();
  });
}

function startWs(projectId) {
  const pid = String(projectId || "").trim();
  if (!pid) {
    logCommissionWs("start:missing-project-id");
    return;
  }
  sharedProjectWsManager.setConsumer("commission", {
    active: true,
    onMessage: noopCommissionSocketConsumer,
  });
  syncAfterReconnect(pid);
}

function stopWs(reason) {
  sharedProjectWsManager.setConsumer("commission", {
    active: false,
    onMessage: noopCommissionSocketConsumer,
  });
  logCommissionWs("close", String(reason || "manual"));
}

async function refreshCommission() {
  if (isCommissioningHydrating()) return;
  const projectId = currentProjectId();
  updateSelectedNames();
  if (!projectId) {
    logCommissionWs("refresh:missing-project-id");
    return;
  }
  startWs(projectId);
  renderCommissionFromStore(projectId);
  await refreshCommissionTopboxTitle(projectId);
}

function runCommissionTab() {
  ensureCommissionStoreSubscription();
  const tabCommission = document.getElementById("tab-commission");
  if (tabCommission) tabCommission.addEventListener("click", () => void refreshCommission());

  const clientSelect = document.getElementById("clientSelect");
  if (clientSelect) clientSelect.addEventListener("change", () => void refreshCommissionTopboxTitle(currentProjectId()));

  const projectSelect = document.getElementById("projectSelect");
  if (projectSelect) {
    projectSelect.addEventListener("change", () => {
      if (isCommissioningHydrating()) {
        updateSelectedNames();
        return;
      }
      const nextProjectId = String(currentProjectId() || "").trim();
      if (nextProjectId) startWs(nextProjectId);
      else stopWs("missing-project");
      updateSelectedNames();
      if (isCommissionVisible()) void refreshCommission();
      if (!isCommissionVisible()) renderCommissionFromStore(nextProjectId);
    });
  }

  const refreshProgressBtn = document.getElementById("refreshProgressBtn");
  if (refreshProgressBtn) refreshProgressBtn.style.display = "none";

  const empty = document.createElement("div");
  empty.className = "activity-empty";
  empty.id = "commissionActivityEmpty";
  empty.textContent = "No activity yet.";
  $("commissionActivity").appendChild(empty);

  updateSelectedNames();
  const initialProjectId = String(currentProjectId() || "").trim();
  if (initialProjectId && !isCommissioningHydrating()) startWs(initialProjectId);
  if (typeof window !== "undefined" && window.addEventListener) {
    window.addEventListener("sentinel:commissioning-hydrated", () => {
      const pid = String(currentProjectId() || "").trim();
      if (pid) startWs(pid);
    });
  }
}

runCommissionTab();
