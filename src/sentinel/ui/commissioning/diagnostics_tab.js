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

const diagAuto = {
  source: null,
  projectId: null,
  refreshTimer: null,
};

function scheduleDiagnosticsRefresh(delayMs = 150) {
  if (diagAuto.refreshTimer) return;
  diagAuto.refreshTimer = setTimeout(() => {
    diagAuto.refreshTimer = null;
    setDiagStatus("");
    refreshDiagnostics().catch((e) => setDiagStatus(String(e?.message || e)));
  }, Math.max(0, Number(delayMs) || 0));
}

function disconnectDiagnosticsSse() {
  if (diagAuto.source) {
    try {
      diagAuto.source.close();
    } catch (_e) {}
  }
  diagAuto.source = null;
  diagAuto.projectId = null;
}

function connectDiagnosticsSse(projectId) {
  const pid = String(projectId || "").trim();
  if (!pid) {
    disconnectDiagnosticsSse();
    return;
  }
  if (diagAuto.source && diagAuto.projectId === pid) return;

  disconnectDiagnosticsSse();
  diagAuto.projectId = pid;
  const url = diagApi(`/commissioning/projects/${encodeURIComponent(pid)}/events`);
  const es = new EventSource(url);
  es.addEventListener("test_result", () => scheduleDiagnosticsRefresh());
  es.addEventListener("result_saved", () => scheduleDiagnosticsRefresh());
  es.onmessage = () => scheduleDiagnosticsRefresh();
  diagAuto.source = es;
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

async function fetchRollups(projectId) {
  try {
    return await diagJsonFetch(diagApi(`/commissioning/projects/${encodeURIComponent(projectId)}/rollups`));
  } catch (_e) {
    return null;
  }
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
  const rows = Array.isArray(fails) ? fails : [];
  rows.sort((a, b) => String(b?.lastTestedAtUtc || "").localeCompare(String(a?.lastTestedAtUtc || "")));

  for (const rec of rows) {
    const targetKey = String(rec?.targetKey || "");
    const ident = parseIdentity(targetKey);
    const tag = tagDisplayFromEnum(rec?.tag || "NOT_STARTED");
    const at = formatUtcTimestamp(rec?.lastTestedAtUtc);
    const resolved = rec?.resolvedData;
    const note = String((resolved == null ? "" : resolved) || rec?.lastFailNote || "");

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

    const tdButton = document.createElement("td");
    tdButton.textContent = String(rec?.buttonName || (ident.button ? `b${ident.button}` : ""));

    const tdScope = document.createElement("td");
    tdScope.textContent = String(rec?.scope || "");

    const tdTarget = document.createElement("td");
    tdTarget.textContent = normalizeTargetLabel(rec?.targetName || ident.testTarget || "");

    const tdResolved = document.createElement("td");
    tdResolved.className = "diag-muted";
    tdResolved.textContent = note || "";

    tr.appendChild(tdTag);
    tr.appendChild(tdAt);
    tr.appendChild(tdDevice);
    tr.appendChild(tdPage);
    tr.appendChild(tdButton);
    tr.appendChild(tdScope);
    tr.appendChild(tdTarget);
    tr.appendChild(tdResolved);
    tbody.appendChild(tr);
  }
}

async function refreshDiagnostics() {
  updateDiagnosticsTitle();
  const pie = _ensurePieDom();
  const projectId = currentDiagProjectId();
  if (!projectId) {
    const host = document.getElementById("diagnosticsSummary");
    if (host) host.textContent = "";
    const legacy = document.getElementById("diagnosticsFailTypeBreakdown");
    if (legacy) legacy.textContent = "";
    diag$("diagnosticsTaskBody").innerHTML = "";
    return;
  }

  const [progress, fails, rollups] = await Promise.all([
    diagJsonFetch(diagApi(`/commissioning/projects/${encodeURIComponent(projectId)}/progress`)),
    diagJsonFetch(diagApi(`/commissioning/projects/${encodeURIComponent(projectId)}/fails`)),
    fetchRollups(projectId),
  ]);

  if (pie) {
    const totalTargets = totalTargetsFrom(progress, rollups);
    const firstTimeFailTargets = firstTimeFailTargetsFromRollups(rollups);
    const okTargets = Math.max(0, totalTargets - firstTimeFailTargets);
    const failPct = totalTargets ? Math.round((firstTimeFailTargets / totalTargets) * 1000) / 10 : 0;
    renderPie(
      pie.failureRate.svg,
      pie.failureRate.legend,
      [
        { label: "First-time fail", value: firstTimeFailTargets, color: "#ef4444" },
        { label: "Other", value: okTargets, color: "#177bb5" },
      ],
      `${failPct}%`
    );

    const typeItems = failureTypesFrom(rollups, fails)
      .filter(([k, n]) => String(k || "") && Number(n) > 0)
      .sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0])));
    const pal = _palette();
    const top = typeItems.slice(0, 6);
    const otherCount = typeItems.slice(6).reduce((acc, [, n]) => acc + Number(n || 0), 0);
    const slices = top.map(([label, n], idx) => ({ label, value: n, color: pal[(idx + 2) % pal.length] }));
    if (otherCount > 0) slices.push({ label: "other", value: otherCount, color: "#6b7280" });
    renderPie(pie.failureTypes.svg, pie.failureTypes.legend, slices, "");

    const rows = Array.isArray(fails) ? fails : [];
    const done = rows.filter((r) => tagDoneFromEnum(r?.tag)).length;
    const totalTasks = rows.length;
    const todo = Math.max(0, totalTasks - done);
    const donePct = totalTasks ? Math.round((done / totalTasks) * 1000) / 10 : 0;
    renderPie(
      pie.taskCompletion.svg,
      pie.taskCompletion.legend,
      [
        { label: "Done", value: done, color: "#10b981" },
        { label: "Not done", value: todo, color: "#f59e0b" },
      ],
      totalTasks ? `${donePct}%` : ""
    );
  }

  renderTaskList(projectId, fails);
}

function initDiagnosticsTab() {
  const refreshBtn = document.getElementById("refreshDiagnosticsBtn");
  if (refreshBtn) {
    refreshBtn.style.display = "none";
  }

  const projectSelect = document.getElementById("projectSelect");
  if (projectSelect) {
    projectSelect.addEventListener("change", () => {
      const projectId = currentDiagProjectId();
      connectDiagnosticsSse(projectId);
      updateDiagnosticsTitle();
      scheduleDiagnosticsRefresh(0);
    });
    const initialProjectId = currentDiagProjectId();
    connectDiagnosticsSse(initialProjectId);
    updateDiagnosticsTitle();
    scheduleDiagnosticsRefresh(0);
  }
}

initDiagnosticsTab();
