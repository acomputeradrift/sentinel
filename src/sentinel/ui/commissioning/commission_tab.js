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
  try {
    if (typeof console !== "undefined" && console.log) {
      console.log("[project-ws]", action, detail == null ? "" : detail);
    }
  } catch (_e) {}
}

function logCommissionWs(action, detail) {
  try {
    if (typeof console !== "undefined" && console.log) {
      console.log("[commission-ws]", action, detail == null ? "" : detail);
    }
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

function ensureSharedProjectWsManager() {
  if (window.__sentinelProjectWsManager) return window.__sentinelProjectWsManager;

  let ws = null;
  let wsProjectId = "";
  let wsReconnectTimer = null;
  let wsReconnectDelayMs = 500;
  let wsConnSeq = 0;
  let wsState = "closed";
  let wsIntentionalClose = false;
  let idleCloseTimer = null;
  const consumers = new Map();
  const recentByProject = new Map();
  const RECENT_MAX = 100;

  function desiredProjectId() {
    for (const consumer of consumers.values()) {
      if (!consumer || !consumer.active) continue;
      const pid = String(consumer.projectId || "").trim();
      if (pid) return pid;
    }
    return "";
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
      const consumerProjectId = String(consumer.projectId || "").trim();
      if (!consumerProjectId) continue;
      if (activeProjectId && consumerProjectId !== activeProjectId) continue;
      if (payloadProjectId && consumerProjectId !== payloadProjectId) continue;
      try {
        consumer.onMessage(payload);
      } catch (e) {
        logProjectWs("consumer:onMessage-failed", String(e?.message || e || ""));
      }
    }
  }

  function dispatchIncoming(payload) {
    if (!payload || typeof payload !== "object") return;
    fanOut(payload);
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
    };
    ws.onclose = () => {
      if (connId !== wsConnSeq) {
        logProjectWs("close:stale-conn", connId);
        return;
      }
      const intentional = wsIntentionalClose;
      wsIntentionalClose = false;
      ws = null;
      wsProjectId = "";
      wsState = "closed";
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
        projectId: String(state?.projectId ?? prev.projectId ?? "").trim(),
        active: state && Object.prototype.hasOwnProperty.call(state, "active") ? !!state.active : !!prev.active,
      };
      consumers.set(key, next);
      const shouldReplay = !!next.active && (!prev.active || String(prev.projectId || "").trim() !== next.projectId);
      if (shouldReplay && typeof next.onMessage === "function" && next.projectId) {
        const cached = recentByProject.get(next.projectId) || [];
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

function handleCommissionWsPayload(payload) {
  try {
    const t = String(payload?.type || "").trim();
    logCommissionWs("recv", t || "(unknown)");
    if (t === "keepalive") return;
    if (t === "commissioning_snapshot") {
      const progress = payload?.progress || null;
      const activities = Array.isArray(payload?.activities) ? payload.activities : [];
      setActivityRows(activities);
      if (progress) updatePies(progress);
      const counts = progress?.counts || {};
      logCommissionWs("snapshot:applied", {
        activities: activities.length,
        pass: Number(counts.pass || 0),
        fail: Number(counts.fail || 0),
      });
      return;
    }
    if (t === "test_result" || t === "test_result.recorded") {
      const norm = normalizeEventMessage(payload);
      logCommissionWs("normalize", {
        hasDevice: !!norm.device,
        hasPage: !!norm.page,
        hasButton: !!norm.button,
        hasTarget: !!norm.testTarget,
        hasKey: !!norm.targetKey,
        status: norm.status,
      });
      appendActivityRow(norm);
      const progress = payload?.progress || payload?.data?.progress || null;
      if (progress) updatePies(progress);
    }
  } catch (e) {
    logCommissionWs("payload:handle-failed", String(e?.message || e || ""));
  }
}

function startWs(projectId) {
  const pid = String(projectId || "").trim();
  if (!pid) {
    logCommissionWs("start:missing-project-id");
    return;
  }
  sharedProjectWsManager.setConsumer("commission", {
    active: true,
    projectId: pid,
    onMessage: handleCommissionWsPayload,
  });
  syncAfterReconnect(pid);
}

function stopWs() {
  sharedProjectWsManager.setConsumer("commission", {
    active: false,
    projectId: String(currentProjectId() || "").trim(),
    onMessage: handleCommissionWsPayload,
  });
}

async function refreshCommission() {
  const projectId = currentProjectId();
  updateSelectedNames();
  if (!projectId) {
    logCommissionWs("refresh:missing-project-id");
    return;
  }
  startWs(projectId);
  await refreshCommissionTopboxTitle(projectId);
}

function runCommissionTab() {
  const tabCommission = document.getElementById("tab-commission");
  if (tabCommission) tabCommission.addEventListener("click", () => void refreshCommission());
  const tabManage = document.getElementById("tab-manage");
  if (tabManage)
    tabManage.addEventListener("click", () => {
      stopWs();
    });
  const tabDiagnostics = document.getElementById("tab-diagnostics");
  if (tabDiagnostics)
    tabDiagnostics.addEventListener("click", () => {
      stopWs();
    });

  const clientSelect = document.getElementById("clientSelect");
  if (clientSelect) clientSelect.addEventListener("change", () => void refreshCommissionTopboxTitle(currentProjectId()));

  const projectSelect = document.getElementById("projectSelect");
  if (projectSelect) {
    projectSelect.addEventListener("change", () => {
      stopWs();
      updateSelectedNames();
      if (isCommissionVisible()) void refreshCommission();
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
}

runCommissionTab();
