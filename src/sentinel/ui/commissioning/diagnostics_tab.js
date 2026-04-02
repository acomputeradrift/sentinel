function diag$(id) {
  const el = document.getElementById(id);
  if (!el) throw new Error(`Missing element: ${id}`);
  return el;
}

function diagApi(path) {
  if (typeof api === "function") return api(path);
  return `/api/v1${path}`;
}

async function diagJsonFetch(url, options) {
  if (typeof jsonFetch === "function") return jsonFetch(url, options);
  const res = await fetch(url, options);
  const ct = res.headers.get("content-type") || "";
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  if (ct.includes("application/json")) return res.json();
  return res.text();
}

function currentDiagProjectId() {
  if (typeof currentProjectId === "function") return currentProjectId();
  const sel = document.getElementById("projectSelect");
  return sel ? sel.value : "";
}

function setDiagStatus(msg) {
  const el = document.getElementById("diagnosticsStatus");
  if (el) el.textContent = msg || "";
}

function _selectedText(selectId) {
  const sel = document.getElementById(selectId);
  const opt = sel && sel.selectedOptions && sel.selectedOptions[0];
  return opt ? String(opt.textContent || "").trim() : "";
}

function updateDiagnosticsTitle() {
  const card = document.getElementById("diagnosticsCard");
  if (!card) return;
  const h2 = card.querySelector("h2");
  if (!h2) return;
  const clientName = _selectedText("clientSelect");
  const projectName = _selectedText("projectSelect");
  const suffix = clientName || projectName ? ` — ${clientName || "(client)"} / ${projectName || "(project)"}` : "";
  h2.textContent = "Diagnostics";

  let line = document.getElementById("diagnosticsClientProjectLine");
  if (!line) {
    line = document.createElement("div");
    line.id = "diagnosticsClientProjectLine";
    line.className = "diag-client-project";
    h2.insertAdjacentElement("afterend", line);
  }
  line.textContent = clientName || projectName ? `${clientName || "(client)"} / ${projectName || "(project)"}` : "";
}

function isDiagnosticsVisible() {
  const panel = document.getElementById("panel-diagnostics");
  return !!panel && !panel.hidden;
}

function isCommissioningHydrating() {
  return !!window.__sentinelCommissioningHydrating;
}

function diagWsUrl(path) {
  const proto = window.location && window.location.protocol === "https:" ? "wss" : "ws";
  const host = window.location && window.location.host ? window.location.host : "localhost";
  return `${proto}://${host}${path}`;
}

function diagWsUrlCandidates(path) {
  const host = window.location && window.location.host ? window.location.host : "localhost";
  const primaryProto = window.location && window.location.protocol === "https:" ? "wss" : "ws";
  const primary = `${primaryProto}://${host}${path}`;
  const fallbackProto = primaryProto === "wss" ? "ws" : "wss";
  const fallback = `${fallbackProto}://${host}${path}`;
  return primaryProto === fallbackProto ? [primary] : [primary, fallback];
}

function logDiagnosticsWs(action, detail) {
  const a = String(action || "").trim();
  let code = "WS-INFO-170";
  let label = "DIAGNOSTICS_EVENT";
  if (a === "connect") {
    code = "WS-INFO-110";
    label = "SOCKET_REUSED";
  } else if (a === "conn-id") {
    code = "WS-INFO-103";
    label = "CONNECT_ATTEMPT";
  } else if (a === "close") {
    code = "WS-INFO-151";
    label = "CONSUMER_CLOSE";
  } else if (a === "snapshot:applied") {
    code = "WS-INFO-140";
    label = "SNAPSHOT_APPLIED";
  } else if (a === "connect:missing-project-id") {
    code = "WS-WARN-201";
    label = "MISSING_PROJECT";
  }
  try {
    const logger = window.__sentinelWsLog;
    if (typeof logger === "function") {
      logger(code, label, "diagnostics-ws", { action: a, detail: detail == null ? "" : detail });
      return;
    }
  } catch (_e) {}
  try {
    if (typeof console !== "undefined" && console.log) console.log(`[diagnostics-ws] ${a}`, detail == null ? "" : detail);
  } catch (_e) {}
}

const diagRt = {
  projectId: null,
  connSeq: 0,
  tasksByKey: new Map(),
  rowByKey: new Map(),
  rollups: null,
  progress: null,
  pies: null,
};
let diagStoreUnsubscribe = null;

function getSharedProjectWsManager() {
  if (window.__sentinelProjectWsManager) return window.__sentinelProjectWsManager;
  throw new Error("Shared project websocket manager not found.");
}

function getSharedProjectStore() {
  if (window.__sentinelProjectStore) return window.__sentinelProjectStore;
  throw new Error("Shared project store not found.");
}

function disconnectDiagnosticsWs(reason) {
  const hadProject = !!String(diagRt.projectId || "").trim();
  getSharedProjectWsManager().setConsumer("diagnostics", {
    active: false,
    onMessage: noopDiagnosticsSocketConsumer,
  });
  diagRt.projectId = null;
  if (hadProject || String(reason || "") !== "missing-project") {
    logDiagnosticsWs("close", String(reason || "manual"));
  }
}

function connectDiagnosticsWs(projectId) {
  if (isCommissioningHydrating()) return;
  const pid = String(projectId || "").trim();
  if (!pid) {
    logDiagnosticsWs("connect:missing-project-id");
    disconnectDiagnosticsWs("missing-project");
    return;
  }
  if (diagRt.projectId === pid) return;
  diagRt.projectId = pid;
  logDiagnosticsWs("conn-id", ++diagRt.connSeq);
  logDiagnosticsWs("url", { protocol: window.location && window.location.protocol, host: window.location && window.location.host });
  logDiagnosticsWs("connect", diagWsUrl(diagApi(`/commissioning/projects/${encodeURIComponent(pid)}/ws`)));
  getSharedProjectWsManager().setConsumer("diagnostics", {
    active: true,
    onMessage: noopDiagnosticsSocketConsumer,
  });
}

function _targetNameFromTargetKey(targetKey) {
  const raw = String(targetKey || "").trim();
  if (!raw) return "";
  const parts = raw.split(":");
  const kind = parts[0] || "";
  if (kind === "event" && parts.length >= 3) return parts.slice(2).join(":");
  if (kind === "btn" && parts.length >= 5) return parts.slice(4).join(":");
  if (kind === "vpbtn" && parts.length >= 7) return parts.slice(6).join(":");
  return raw;
}

function targetLabelFromTargetKey(targetKey) {
  const name = _targetNameFromTargetKey(targetKey);
  return normalizeTargetLabel(name);
}

function parseIdentity(targetKey) {
  const raw = String(targetKey || "").trim();
  const parts = raw ? raw.split(":") : [];
  const kind = parts[0] || "";
  if (kind === "event" && parts.length >= 3) {
    return { device: "", page: "", button: "", testTarget: targetLabelFromTargetKey(raw) };
  }
  if (kind === "btn" && parts.length >= 5) {
    return { device: parts[1] || "", page: parts[2] || "", button: parts[3] || "", testTarget: targetLabelFromTargetKey(raw) };
  }
  if (kind === "vpbtn" && parts.length >= 7) {
    return { device: parts[1] || "", page: parts[2] || "", button: parts[5] || "", testTarget: targetLabelFromTargetKey(raw) };
  }
  return { device: "", page: "", button: "", testTarget: targetLabelFromTargetKey(raw) };
}

function normalizeTargetLabel(targetName) {
  const raw = String(targetName || "").trim();
  if (!raw) return "";
  const lower = raw.toLowerCase();
  if (lower === "macro") return "macro";
  if (lower === "macrosteps" || lower === "macro steps" || lower === "macro step" || lower === "macro-step") return "macro step";
  if (lower === "pagelink" || lower === "page link") return "pageLink";
  if (lower === "text" || lower === "texts") return "text";
  if (lower === "command" || lower === "commands") return "command";
  if (lower.startsWith("variable - ")) return `variable - ${lower.slice("variable - ".length)}`;
  if (lower.startsWith("var.")) return `variable - ${lower.slice(4)}`;
  return lower;
}

function _isTruePageLinkTarget(targetName, targetKey) {
  const name = normalizeTargetLabel(targetName);
  if (name === "pagelink" || name === "pageLink") return true;
  const raw = String(targetKey || "").trim();
  return raw.endsWith(":PageLink");
}

function _scopePartsFromTt2TargetKey(targetKey) {
  const raw = String(targetKey || "").trim();
  if (!raw.startsWith("tt2:")) return null;
  const parts = raw.split(":");
  if (parts.length < 5) return null;
  return {
    scopeType: String(parts[2] || "").toUpperCase(),
    effectiveRoomId: Number(parts[3]),
    effectiveSourceId: Number(parts[4]),
  };
}

function formatEffectiveScope(taskLike) {
  const task = taskLike && typeof taskLike === "object" ? taskLike : {};
  const targetName = String(task.targetName || "");
  const targetKey = String(task.targetKey || "");
  if (_isTruePageLinkTarget(targetName, targetKey)) return "Global";

  let scopeType = String(task.scopeType || "").trim().toUpperCase();
  let roomId = task.effectiveRoomId;
  let sourceId = task.effectiveSourceId;
  const roomName = String(task.effectiveRoomName || "").trim();
  const sourceName = String(task.effectiveSourceName || "").trim();
  if (!scopeType || roomId == null || sourceId == null) {
    const parsed = _scopePartsFromTt2TargetKey(targetKey);
    if (parsed) {
      if (!scopeType) scopeType = parsed.scopeType;
      if (roomId == null) roomId = parsed.effectiveRoomId;
      if (sourceId == null) sourceId = parsed.effectiveSourceId;
    }
  }

  if (scopeType !== "GLOBAL" && scopeType !== "ROOM") return String(task.scope || "");
  const roomLabel = scopeType === "GLOBAL" ? "Global" : (roomName || `Room ${roomId}`);
  if (sourceName) return `${roomLabel} -> ${sourceName}`;
  if (sourceId == null || Number.isNaN(Number(sourceId))) return roomLabel;
  return `${roomLabel} -> ${Number(sourceId)}`;
}

function formatViewport(taskLike) {
  const task = taskLike && typeof taskLike === "object" ? taskLike : {};
  const explicit = String(task.viewport || "").trim();
  if (explicit) return explicit;
  const frameIndexRti = task.frameIndexRti;
  if (frameIndexRti != null && Number.isFinite(Number(frameIndexRti))) return `Frame ${Number(frameIndexRti) + 1}`;
  const raw = String(task.targetKey || "").trim();
  const parts = raw ? raw.split(":") : [];
  if ((parts[0] || "") === "vpbtn" && parts.length >= 7) {
    const frame = Number(parts[4]);
    if (Number.isFinite(frame)) return `Frame ${frame + 1}`;
  }
  return "No";
}

function formatUtcTimestamp(ts) {
  const raw = String(ts || "").trim();
  if (!raw) return "";
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return raw;
  const pad2 = (n) => String(n).padStart(2, "0");
  const yyyy = d.getUTCFullYear();
  const mm = pad2(d.getUTCMonth() + 1);
  const dd = pad2(d.getUTCDate());
  const hh = pad2(d.getUTCHours());
  const mi = pad2(d.getUTCMinutes());
  const ss = pad2(d.getUTCSeconds());
  return `${yyyy}-${mm}-${dd} ${hh}:${mi}:${ss}Z`;
}

function _ensurePieDom() {
  const host = document.getElementById("diagnosticsSummary");
  if (!host) return null;

  host.textContent = "";
  host.classList.add("diag-pies-host");

  const wrapper = document.createElement("div");
  wrapper.className = "diag-pies";
  wrapper.setAttribute("data-testid", "diagnostics-pies");

  const makeCard = (title, testid) => {
    const card = document.createElement("div");
    card.className = "diag-pie-card";
    card.setAttribute("data-testid", testid);

    const t = document.createElement("div");
    t.className = "diag-pie-title";
    t.textContent = title;

    const svgWrap = document.createElement("div");
    svgWrap.className = "diag-pie-svgwrap";

    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 120 120");
    svg.setAttribute("width", "120");
    svg.setAttribute("height", "120");
    svg.classList.add("diag-pie");

    const legend = document.createElement("div");
    legend.className = "diag-pie-legend";

    svgWrap.appendChild(svg);
    card.appendChild(t);
    card.appendChild(svgWrap);
    card.appendChild(legend);

    return { card, svg, legend };
  };

  const failureRate = makeCard("Failure Rate", "diagnostics-pie-failure-rate");
  const failureTypes = makeCard("Failure Types", "diagnostics-pie-failure-types");
  const taskCompletion = makeCard("Task Completion", "diagnostics-pie-task-completion");

  wrapper.appendChild(failureRate.card);
  wrapper.appendChild(failureTypes.card);
  wrapper.appendChild(taskCompletion.card);
  host.appendChild(wrapper);

  const legacy = document.getElementById("diagnosticsFailTypeBreakdown");
  if (legacy) legacy.textContent = "";

  return { failureRate, failureTypes, taskCompletion };
}

function _palette() {
  return ["#177bb5", "#0f5d8a", "#33a1de", "#7cc4ea", "#6b7280", "#ef4444", "#f59e0b", "#10b981", "#8b5cf6"];
}

function _piePath(cx, cy, r, startAngle, endAngle) {
  const polar = (angle) => {
    const a = (angle - 90) * (Math.PI / 180);
    return { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) };
  };
  const p1 = polar(endAngle);
  const p0 = polar(startAngle);
  const large = endAngle - startAngle <= 180 ? "0" : "1";
  return `M ${cx} ${cy} L ${p0.x} ${p0.y} A ${r} ${r} 0 ${large} 1 ${p1.x} ${p1.y} Z`;
}

function renderPie(svg, legendEl, slices, centerLabel) {
  while (svg.firstChild) svg.removeChild(svg.firstChild);
  legendEl.innerHTML = "";

  const total = slices.reduce((a, s) => a + (Number(s.value) || 0), 0);
  const safeTotal = total || 1;

  const bg = document.createElementNS("http://www.w3.org/2000/svg", "circle");
  bg.setAttribute("cx", "60");
  bg.setAttribute("cy", "60");
  bg.setAttribute("r", "52");
  bg.setAttribute("fill", "#e7eef5");
  svg.appendChild(bg);

  let angle = 0;
  for (const s of slices) {
    const v = Number(s.value) || 0;
    if (v <= 0) continue;
    const span = (v / safeTotal) * 360;
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", _piePath(60, 60, 52, angle, angle + span));
    path.setAttribute("fill", String(s.color || "#177bb5"));
    svg.appendChild(path);
    angle += span;

    const row = document.createElement("div");
    row.className = "diag-legend-row";
    const sw = document.createElement("span");
    sw.className = "diag-legend-swatch";
    sw.style.background = String(s.color || "#177bb5");
    const txt = document.createElement("span");
    txt.className = "diag-legend-text";
    const pctTxt = Math.round((v / safeTotal) * 1000) / 10;
    txt.textContent = `${String(s.label)} (${v}, ${pctTxt}%)`;
    row.appendChild(sw);
    row.appendChild(txt);
    legendEl.appendChild(row);
  }

  const hole = document.createElementNS("http://www.w3.org/2000/svg", "circle");
  hole.setAttribute("cx", "60");
  hole.setAttribute("cy", "60");
  hole.setAttribute("r", "30");
  hole.setAttribute("fill", "#ffffff");
  svg.appendChild(hole);

  if (centerLabel) {
    const t = document.createElementNS("http://www.w3.org/2000/svg", "text");
    t.setAttribute("x", "60");
    t.setAttribute("y", "64");
    t.setAttribute("text-anchor", "middle");
    t.setAttribute("font-size", "12");
    t.setAttribute("font-weight", "700");
    t.setAttribute("fill", "#173246");
    t.textContent = centerLabel;
    svg.appendChild(t);
  }
}

async function updateFailTag(projectId, targetKey, tag) {
  await diagJsonFetch(diagApi(`/commissioning/projects/${encodeURIComponent(projectId)}/fail-tags`), {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ targetKey, tag }),
  });
}

function tagOptions() {
  return ["Not Started", "In Progress", "Done"];
}

function tagEnumFromDisplay(label) {
  const s = String(label || "").trim().toLowerCase();
  if (s === "in progress") return "IN_PROGRESS";
  if (s === "done") return "DONE";
  return "NOT_STARTED";
}

function tagDisplayFromEnum(tagEnum) {
  const s = String(tagEnum || "").trim().toUpperCase();
  if (s === "IN_PROGRESS") return "In Progress";
  if (s === "DONE") return "Done";
  return "Not Started";
}

function tagDoneFromEnum(tagEnum) {
  return String(tagEnum || "").trim().toUpperCase() === "DONE";
}

function firstTimeFailTargetsFromRollups(rollups) {
  const candidates = [
    rollups?.counts?.firstTimeFailTargets,
    rollups?.firstTimeFailTargets,
    rollups?.failureRate?.firstTimeFailTargets,
  ];
  for (const c of candidates) {
    const n = Number(c);
    if (!Number.isNaN(n) && Number.isFinite(n)) return n;
  }
  return 0;
}

function totalTargetsFrom(progress, rollups) {
  const a = Number(rollups?.counts?.totalTargets);
  if (!Number.isNaN(a) && Number.isFinite(a)) return a;
  const b = Number(progress?.counts?.totalTargets);
  if (!Number.isNaN(b) && Number.isFinite(b)) return b;
  return 0;
}

function failureTypesFrom(rollups, fails) {
  const by = rollups?.currentFailures?.byTargetName || rollups?.currentFailures?.byTargetType || null;
  if (by && typeof by === "object" && !Array.isArray(by)) {
    const items = [];
    for (const [k, v] of Object.entries(by)) {
      const n = Number(v);
      if (!Number.isNaN(n) && n > 0) items.push([normalizeTargetLabel(k), n]);
    }
    return items;
  }

  const rows = Array.isArray(fails) ? fails : [];
  const counts = new Map();
  for (const rec of rows) {
    const label = normalizeTargetLabel(rec?.targetName || _targetNameFromTargetKey(rec?.targetKey || ""));
    counts.set(label, (counts.get(label) || 0) + 1);
  }
  return Array.from(counts.entries());
}

function renderTaskList(projectId, fails) {
  const tbody = diag$("diagnosticsTaskBody");
  tbody.innerHTML = "";
  diagRt.tasksByKey.clear();
  diagRt.rowByKey.clear();
  const rows = Array.isArray(fails) ? fails : [];
  rows.sort((a, b) => String(b?.lastTestedAtUtc || "").localeCompare(String(a?.lastTestedAtUtc || "")));

  for (const rec of rows) {
    const targetKey = String(rec?.targetKey || "");
    const ident = parseIdentity(targetKey);
    const tag = tagDisplayFromEnum(rec?.tag || "NOT_STARTED");
    const at = formatUtcTimestamp(rec?.lastTestedAtUtc);
    const note = String(rec?.lastFailNote || "");

    const tr = document.createElement("tr");

    const tdTag = document.createElement("td");
    const sel = document.createElement("select");
    sel.className = "diag-tag";
    for (const optVal of tagOptions()) {
      const opt = document.createElement("option");
      opt.value = optVal;
      opt.textContent = optVal;
    sel.appendChild(opt);
    }
    sel.value = tagOptions().includes(tag) ? tag : "Not Started";
    sel.addEventListener("change", async () => {
      const next = tagEnumFromDisplay(sel.value);
      try {
        await updateFailTag(projectId, targetKey, next);
        setDiagStatus("");
        const task = diagRt.tasksByKey.get(targetKey);
        if (task) task.tag = next;
        updateTaskCompletionPie();
      } catch (e) {
        sel.value = tagOptions().includes(tag) ? tag : "Not Started";
        setDiagStatus(String(e?.message || e));
      }
    });
    tdTag.appendChild(sel);

    const tdAt = document.createElement("td");
    tdAt.className = "mono diag-ts";
    tdAt.textContent = at || "";

    const tdDevice = document.createElement("td");
    tdDevice.textContent = String(rec?.deviceName || (ident.device ? `d${ident.device}` : ""));

    const tdPage = document.createElement("td");
    tdPage.textContent = String(rec?.pageName || (ident.page ? `p${ident.page}` : ""));

    const tdLayer = document.createElement("td");
    tdLayer.textContent = String(rec?.layerName || "");

    const tdViewport = document.createElement("td");
    tdViewport.textContent = formatViewport({
      targetKey,
      viewport: rec?.viewport,
      frameIndexRti: rec?.frameIndexRti,
    });

    const tdButton = document.createElement("td");
    tdButton.textContent = String(rec?.buttonName || (ident.button ? `b${ident.button}` : ""));

    const tdTarget = document.createElement("td");
    tdTarget.textContent = normalizeTargetLabel(rec?.targetName || ident.testTarget || "");

    const tdScope = document.createElement("td");
    tdScope.textContent = formatEffectiveScope({
      targetKey,
      targetName: String(rec?.targetName || ident.testTarget || ""),
      scopeType: rec?.scopeType,
      effectiveRoomId: rec?.effectiveRoomId,
      effectiveSourceId: rec?.effectiveSourceId,
      effectiveRoomName: rec?.effectiveRoomName,
      effectiveSourceName: rec?.effectiveSourceName,
    });

    const tdResolved = document.createElement("td");
    tdResolved.className = "diag-muted";
    tdResolved.textContent = note || "";

    tr.appendChild(tdTag);
    tr.appendChild(tdAt);
    tr.appendChild(tdDevice);
    tr.appendChild(tdPage);
    tr.appendChild(tdLayer);
    tr.appendChild(tdViewport);
    tr.appendChild(tdButton);
    tr.appendChild(tdTarget);
    tr.appendChild(tdResolved);
    tr.appendChild(tdScope);
    tbody.appendChild(tr);

    diagRt.tasksByKey.set(targetKey, {
      targetKey,
      tag: tagEnumFromDisplay(tag),
      lastTestedAtUtc: String(rec?.lastTestedAtUtc || ""),
      deviceName: String(rec?.deviceName || ""),
      pageName: String(rec?.pageName || ""),
      layerName: String(rec?.layerName || ""),
      viewport: String(rec?.viewport || ""),
      frameIndexRti: rec?.frameIndexRti,
      buttonName: String(rec?.buttonName || ""),
      targetName: String(rec?.targetName || ""),
      scope: String(rec?.scope || ""),
      scopeType: rec?.scopeType,
      effectiveRoomId: rec?.effectiveRoomId,
      effectiveSourceId: rec?.effectiveSourceId,
      effectiveRoomName: rec?.effectiveRoomName,
      effectiveSourceName: rec?.effectiveSourceName,
      lastFailNote: String(rec?.lastFailNote || ""),
    });
    diagRt.rowByKey.set(targetKey, { tr, sel });
  }
}

function clearDiagnosticsView() {
  const host = document.getElementById("diagnosticsSummary");
  if (host) host.textContent = "";
  const legacy = document.getElementById("diagnosticsFailTypeBreakdown");
  if (legacy) legacy.textContent = "";
  diag$("diagnosticsTaskBody").innerHTML = "";
  diagRt.tasksByKey.clear();
  diagRt.rowByKey.clear();
  diagRt.progress = null;
  diagRt.rollups = null;
  diagRt.pies = null;
}

function applyDiagnosticsSnapshot(snapshot) {
  const projectId = String(snapshot?.projectId || currentDiagProjectId() || "");
  if (!projectId) {
    logDiagnosticsWs("snapshot:missing-project-id");
    return;
  }
  diagRt.pies = _ensurePieDom();
  diagRt.progress = snapshot?.progress || null;
  diagRt.rollups = snapshot?.rollups || null;
  const fails = Array.isArray(snapshot?.fails) ? snapshot.fails : [];
  renderTaskList(projectId, fails);
  updateFailureRatePie();
  updateFailureTypesPie();
  updateTaskCompletionPie();
  const counts = snapshot?.progress?.counts || {};
  logDiagnosticsWs("snapshot:applied", {
    fails: fails.length,
    pass: Number(counts.pass || 0),
    fail: Number(counts.fail || 0),
  });
}

function _snapshotFromStore(projectId) {
  const store = getSharedProjectStore();
  const state = store.getState();
  const projects = state && state.projects && typeof state.projects === "object" ? state.projects : {};
  const slice = projects[String(projectId || "").trim()] || null;
  if (!slice) return null;
  return {
    type: "commissioning_snapshot",
    projectId: String(projectId || ""),
    progress: slice.progress || null,
    rollups: slice.rollups || null,
    fails: Array.isArray(slice.fails) ? slice.fails : [],
    activities: Array.isArray(slice.activities) ? slice.activities : [],
    activeUpload: slice.activeUpload || null,
  };
}

function applyDiagnosticsFromStore(projectId) {
  const pid = String(projectId || currentDiagProjectId() || "").trim();
  if (!pid) {
    clearDiagnosticsView();
    return;
  }
  const snapshot = _snapshotFromStore(pid);
  if (!snapshot) {
    clearDiagnosticsView();
    return;
  }
  applyDiagnosticsSnapshot(snapshot);
}

function ensureDiagnosticsStoreSubscription() {
  if (diagStoreUnsubscribe) return;
  const store = getSharedProjectStore();
  diagStoreUnsubscribe = store.subscribe(() => {
    if (!isDiagnosticsVisible()) return;
    applyDiagnosticsFromStore(currentDiagProjectId());
  });
}

function _ensureDiagPiesCached() {
  if (!diagRt.pies) diagRt.pies = _ensurePieDom();
  return diagRt.pies;
}

function updateFailureRatePie() {
  const pie = _ensureDiagPiesCached();
  if (!pie) return;
  const totalTargets = totalTargetsFrom(diagRt.progress, diagRt.rollups);
  const firstTimeFailTargets = firstTimeFailTargetsFromRollups(diagRt.rollups);
  const okTargets = Math.max(0, totalTargets - firstTimeFailTargets);
  const failPct = totalTargets ? Math.round((firstTimeFailTargets / totalTargets) * 1000) / 10 : 0;
  renderPie(
    pie.failureRate.svg,
    pie.failureRate.legend,
    [
      { label: "First-time fail", value: firstTimeFailTargets, color: "#ef4444" },
      { label: "Other", value: okTargets, color: "#177bb5" },
    ],
    totalTargets ? `${failPct}%` : ""
  );
}

function updateFailureTypesPie() {
  const pie = _ensureDiagPiesCached();
  if (!pie) return;
  const counts = new Map();
  for (const task of diagRt.tasksByKey.values()) {
    const label = normalizeTargetLabel(task?.targetName || _targetNameFromTargetKey(task?.targetKey || ""));
    if (!label) continue;
    counts.set(label, (counts.get(label) || 0) + 1);
  }
  const typeItems = Array.from(counts.entries())
    .filter(([k, n]) => String(k || "") && Number(n) > 0)
    .sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0])));
  const pal = _palette();
  const top = typeItems.slice(0, 6);
  const otherCount = typeItems.slice(6).reduce((acc, [, n]) => acc + Number(n || 0), 0);
  const slices = top.map(([label, n], idx) => ({ label, value: n, color: pal[(idx + 2) % pal.length] }));
  if (otherCount > 0) slices.push({ label: "other", value: otherCount, color: "#6b7280" });
  renderPie(pie.failureTypes.svg, pie.failureTypes.legend, slices, "");
}

function updateTaskCompletionPie() {
  const pie = _ensureDiagPiesCached();
  if (!pie) return;
  const tasks = Array.from(diagRt.tasksByKey.values());
  const done = tasks.filter((t) => tagDoneFromEnum(t?.tag)).length;
  const total = tasks.length;
  const todo = Math.max(0, total - done);
  const donePct = total ? Math.round((done / total) * 1000) / 10 : 0;
  renderPie(
    pie.taskCompletion.svg,
    pie.taskCompletion.legend,
    [
      { label: "Done", value: done, color: "#10b981" },
      { label: "Not done", value: todo, color: "#f59e0b" },
    ],
    total ? `${donePct}%` : ""
  );
}

function _makeTaskRow(projectId, task) {
  const targetKey = String(task?.targetKey || "");
  const ident = parseIdentity(targetKey);

  const tr = document.createElement("tr");

  const tdTag = document.createElement("td");
  const sel = document.createElement("select");
  sel.className = "diag-tag";
  for (const optVal of tagOptions()) {
    const opt = document.createElement("option");
    opt.value = optVal;
    opt.textContent = optVal;
    sel.appendChild(opt);
  }
  sel.value = tagDisplayFromEnum(task?.tag || "NOT_STARTED");
  sel.addEventListener("change", async () => {
    const next = tagEnumFromDisplay(sel.value);
    try {
      await updateFailTag(projectId, targetKey, next);
      const t = diagRt.tasksByKey.get(targetKey);
      if (t) t.tag = next;
      updateTaskCompletionPie();
      setDiagStatus("");
    } catch (e) {
      sel.value = tagDisplayFromEnum(task?.tag || "NOT_STARTED");
      setDiagStatus(String(e?.message || e));
    }
  });
  tdTag.appendChild(sel);

  const tdAt = document.createElement("td");
  tdAt.className = "mono diag-ts";

  const tdDevice = document.createElement("td");
  const tdPage = document.createElement("td");
  const tdLayer = document.createElement("td");
  const tdViewport = document.createElement("td");
  const tdButton = document.createElement("td");
  const tdScope = document.createElement("td");
  const tdTarget = document.createElement("td");
  const tdResolved = document.createElement("td");
  tdResolved.className = "diag-muted";

  tdDevice.textContent = String(task?.deviceName || (ident.device ? `d${ident.device}` : ""));
  tdPage.textContent = String(task?.pageName || (ident.page ? `p${ident.page}` : ""));
  tdLayer.textContent = String(task?.layerName || "");
  tdViewport.textContent = formatViewport(task);
  tdButton.textContent = String(task?.buttonName || (ident.button ? `b${ident.button}` : ""));
  tdScope.textContent = formatEffectiveScope(task);
  tdTarget.textContent = normalizeTargetLabel(task?.targetName || ident.testTarget || "");
  const note = String(task?.lastFailNote || "");
  tdResolved.textContent = note || "";

  tr.appendChild(tdTag);
  tr.appendChild(tdAt);
  tr.appendChild(tdDevice);
  tr.appendChild(tdPage);
  tr.appendChild(tdLayer);
  tr.appendChild(tdViewport);
  tr.appendChild(tdButton);
  tr.appendChild(tdTarget);
  tr.appendChild(tdResolved);
  tr.appendChild(tdScope);

  return { tr, sel, tdAt, tdDevice, tdPage, tdLayer, tdViewport, tdButton, tdScope, tdTarget, tdResolved };
}

function _updateTaskRowDom(row, task) {
  if (!row) return;
  row.tdAt.textContent = formatUtcTimestamp(task?.lastTestedAtUtc) || "";
  row.tdDevice.textContent = String(task?.deviceName || "");
  row.tdPage.textContent = String(task?.pageName || "");
  row.tdLayer.textContent = String(task?.layerName || "");
  row.tdViewport.textContent = formatViewport(task);
  row.tdButton.textContent = String(task?.buttonName || "");
  row.tdScope.textContent = formatEffectiveScope(task);
  row.tdTarget.textContent = normalizeTargetLabel(task?.targetName || "");
  const note = String(task?.lastFailNote || "");
  row.tdResolved.textContent = note || "";
  row.sel.value = tagDisplayFromEnum(task?.tag || "NOT_STARTED");
}

function handleDiagnosticsEvent(payload) {
  const ev = payload && typeof payload === "object" ? payload : {};
  const t = String(ev?.type || "").trim();
  if (!t || t === "keepalive") {
    logDiagnosticsWs("recv:ignored", t || "(empty)");
    return;
  }
  applyDiagnosticsFromStore(currentDiagProjectId());
}

function noopDiagnosticsSocketConsumer() {}

function initDiagnosticsTab() {
  ensureDiagnosticsStoreSubscription();
  const refreshBtn = document.getElementById("refreshDiagnosticsBtn");
  if (refreshBtn) {
    refreshBtn.style.display = "none";
  }

  const tabDiag = document.getElementById("tab-diagnostics");
  if (tabDiag) {
    tabDiag.addEventListener("click", () => {
      if (isCommissioningHydrating()) return;
      const projectId = currentDiagProjectId();
      connectDiagnosticsWs(projectId);
      applyDiagnosticsFromStore(projectId);
      setDiagStatus("");
      updateDiagnosticsTitle();
    });
  }

  const projectSelect = document.getElementById("projectSelect");
  if (projectSelect) {
    projectSelect.addEventListener("change", () => {
      if (isCommissioningHydrating()) {
        updateDiagnosticsTitle();
        return;
      }
      const projectId = currentDiagProjectId();
      connectDiagnosticsWs(projectId);
      if (isDiagnosticsVisible()) applyDiagnosticsFromStore(projectId);
      updateDiagnosticsTitle();
      setDiagStatus("");
      if (!projectId) clearDiagnosticsView();
    });
    const initialProjectId = currentDiagProjectId();
    if (initialProjectId && !isCommissioningHydrating()) connectDiagnosticsWs(initialProjectId);
    if (isDiagnosticsVisible()) applyDiagnosticsFromStore(initialProjectId);
    updateDiagnosticsTitle();
    if (!initialProjectId) clearDiagnosticsView();
  }
  if (typeof window !== "undefined" && window.addEventListener) {
    window.addEventListener("sentinel:commissioning-hydrated", () => {
      const projectId = currentDiagProjectId();
      if (projectId) connectDiagnosticsWs(projectId);
      if (isDiagnosticsVisible()) applyDiagnosticsFromStore(projectId);
    });
  }
}

initDiagnosticsTab();
