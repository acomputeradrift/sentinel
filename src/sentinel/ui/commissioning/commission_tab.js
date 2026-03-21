function $(id) {
  const el = document.getElementById(id);
  if (!el) throw new Error(`Missing element: ${id}`);
  return el;
}

function api(path) {
  return `/api/v1${path}`;
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

async function jsonFetch(url, options) {
  const res = await fetch(url, options);
  const ct = res.headers.get("content-type") || "";
  if (!res.ok) {
    const body = ct.includes("application/json") ? await res.json() : await res.text();
    if (body && typeof body === "object" && body.error && body.error.message) {
      throw new Error(String(body.error.message));
    }
    throw new Error(typeof body === "string" ? body : JSON.stringify(body));
  }
  if (ct.includes("application/json")) return res.json();
  return res.text();
}

function currentProjectId() {
  const sel = document.getElementById("projectSelect");
  return sel ? sel.value : "";
}

function isCommissionVisible() {
  const panel = document.getElementById("panel-commission");
  return !!panel && !panel.hidden;
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

function updateKpis(progress) {
  const counts = progress && progress.counts ? progress.counts : {};
  const total = Number(counts.totalTargets || 0);
  const tested = Number(counts.testedTargets || 0);
  const untested = Number(counts.untested || 0);

  const completePct = total > 0 ? tested / total : 0;
  const untestedPct = total > 0 ? untested / total : 0;

  applyStyleVars($("commissionKpiCompleteRing"), pctStyle(completePct));
  $("commissionKpiCompleteValue").textContent = `${Math.round(completePct * 100)}%`;
  $("commissionKpiCompleteSub").textContent = `${tested}/${total} tested`;

  applyStyleVars($("commissionKpiTestedRing"), pctStyle(completePct));
  $("commissionKpiTestedValue").textContent = String(tested);
  $("commissionKpiTestedSub").textContent = "tested targets";

  applyStyleVars($("commissionKpiUntestedRing"), pctStyle(untestedPct));
  $("commissionKpiUntestedValue").textContent = String(untested);
  $("commissionKpiUntestedSub").textContent = "untested targets";
}

function ensureCommissionPies() {
  const panel = document.getElementById("panel-commission");
  if (!panel) return null;
  const shell = panel.querySelector(".commission-shell");
  if (!shell) return null;

  // Hide legacy ring KPI row; replaced by pies.
  const legacy = shell.querySelector(".commission-kpis");
  if (legacy) legacy.classList.add("commission-kpis--hidden");

  let pies = document.getElementById("commissionPies");
  if (pies) return pies;

  pies = document.createElement("div");
  pies.className = "commission-pies";
  pies.id = "commissionPies";
  pies.dataset.testid = "commission-pies";

  const selection = document.getElementById("commissionSelection");
  if (selection && selection.parentElement === shell) {
    selection.insertAdjacentElement("afterend", pies);
  } else {
    shell.prepend(pies);
  }

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
    const displayName = String(d.displayName || `Device ${deviceId}`);
    const key = `device-${deviceId}`;
    const card = ensurePieCard({
      key,
      title: displayName,
      testId: `commission-pie-device-${deviceId}`,
      color: "#f59e0b",
    });
    seen.add(`commissionPie-${key}`);
    setPieCardProgress(card, { passed: d?.counts?.pass || 0, total: d?.counts?.totalTargets || 0 });
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

let sse = null;
let sseProjectId = null;
let lastSseErrorAtMs = 0;
let progressRefreshTimer = null;

function ensureCommissionHeader() {
  const panel = document.getElementById("panel-commission");
  if (!panel) return;
  const shell = panel.querySelector(".commission-shell");
  if (!shell) return;
  if (document.getElementById("commissionSelection")) return;

  const div = document.createElement("div");
  div.className = "commission-selection";
  div.id = "commissionSelection";
  div.innerHTML = `
    <div class="commission-selection-title">Selected</div>
    <div class="commission-selection-row">
      <div class="commission-selection-item">
        <div class="commission-selection-label">Client</div>
        <div class="commission-selection-value mono" data-testid="commission-selected-client" id="commissionSelectedClientName"></div>
      </div>
      <div class="commission-selection-item">
        <div class="commission-selection-label">Project</div>
        <div class="commission-selection-value mono" data-testid="commission-selected-project" id="commissionSelectedProjectName"></div>
      </div>
    </div>
  `.trim();

  shell.prepend(div);
}

function selectedOptionText(selectId) {
  const sel = document.getElementById(selectId);
  const opt = sel && sel.selectedOptions && sel.selectedOptions[0] ? sel.selectedOptions[0] : null;
  return opt ? String(opt.textContent || "").trim() : "";
}

function updateSelectedNames() {
  ensureCommissionHeader();
  const clientNameEl = document.getElementById("commissionSelectedClientName");
  const projectNameEl = document.getElementById("commissionSelectedProjectName");
  if (!clientNameEl || !projectNameEl) return;

  const clientName = selectedOptionText("clientSelect");
  const projectName = selectedOptionText("projectSelect");

  clientNameEl.textContent = clientName || "TODO: select a client";
  projectNameEl.textContent = projectName || "TODO: select a project";
}

function stopSse() {
  if (sse) {
    try {
      sse.close();
    } catch (_e) {}
  }
  sse = null;
  sseProjectId = null;
  lastSseErrorAtMs = 0;
}

function scheduleProgressRefresh() {
  const projectId = currentProjectId();
  if (!projectId) return;
  if (progressRefreshTimer) return;

  progressRefreshTimer = setTimeout(async () => {
    progressRefreshTimer = null;
    try {
      const progress = await jsonFetch(api(`/commissioning/projects/${encodeURIComponent(projectId)}/progress`));
      updatePies(progress);
      updateKpis(progress);
    } catch (_e) {}
  }, 750);
}

function startSse(projectId) {
  if (!projectId) return;
  if (sse && sseProjectId === projectId) return;
  stopSse();

  const url = api(`/commissioning/projects/${encodeURIComponent(projectId)}/events`);
  sse = new EventSource(url);
  sseProjectId = projectId;

  const handleTestResult = (e) => {
    try {
      const payload = JSON.parse(String(e.data || "{}"));
      appendActivityRow(normalizeEventMessage(payload));
      scheduleProgressRefresh();
    } catch (_err) {
      appendActivityRow({ tsUtc: "", device: "", page: "", button: "", testTarget: "", status: "", targetKey: String(e.data || "") });
    }
  };

  sse.addEventListener("test_result", handleTestResult);

  sse.addEventListener("error", () => {
    const now = Date.now();
    if (now - lastSseErrorAtMs < 10_000) return;
    lastSseErrorAtMs = now;
    appendActivityRow({
      tsUtc: formatTimestampUtc(new Date().toISOString()),
      device: "",
      page: "",
      button: "",
      testTarget: "",
      status: "SSE_ERROR",
      targetKey: "",
    });
  });
}

async function refreshCommission() {
  const projectId = currentProjectId();
  updateSelectedNames();
  if (!projectId) return;
  startSse(projectId);

  try {
    const progress = await jsonFetch(api(`/commissioning/projects/${encodeURIComponent(projectId)}/progress`));
    updatePies(progress);
    updateKpis(progress);
  } catch (_e) {
    updatePies({
      counts: { totalTargets: 0, pass: 0 },
      eventSections: { system: { counts: { totalTargets: 0, pass: 0 } }, driver: { counts: { totalTargets: 0, pass: 0 } } },
      devices: [],
    });
    updateKpis({ counts: { totalTargets: 0, testedTargets: 0, untested: 0 } });
  }
}

function runCommissionTab() {
  const tabCommission = document.getElementById("tab-commission");
  if (tabCommission) tabCommission.addEventListener("click", () => void refreshCommission());
  const tabManage = document.getElementById("tab-manage");
  if (tabManage) tabManage.addEventListener("click", () => stopSse());
  const tabDiagnostics = document.getElementById("tab-diagnostics");
  if (tabDiagnostics) tabDiagnostics.addEventListener("click", () => stopSse());

  const clientSelect = document.getElementById("clientSelect");
  if (clientSelect) clientSelect.addEventListener("change", () => updateSelectedNames());

  const projectSelect = document.getElementById("projectSelect");
  if (projectSelect) {
    projectSelect.addEventListener("change", () => {
      stopSse();
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
