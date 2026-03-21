function $(id) {
  const el = document.getElementById(id);
  if (!el) throw new Error(`Missing element: ${id}`);
  return el;
}

function api(path) {
  return `/api/v1${path}`;
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

function normalizeEventMessage(ev) {
  const payload = ev && typeof ev === "object" ? ev : {};
  const data = payload?.data && typeof payload.data === "object" ? payload.data : payload;
  const refs = data?.refs && typeof data.refs === "object" ? data.refs : {};

  return {
    tsUtc: String(data?.recordedAtUtc || data?.tsUtc || ""),
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
  tdStatus.className = "mono";

  tdTime.textContent = msg.tsUtc || "";
  tdDevice.textContent = msg.device || "";
  tdPage.textContent = msg.page || "";
  tdButton.textContent = msg.button || "";
  tdTarget.textContent = msg.testTarget || msg.targetKey || "";
  tdStatus.textContent = msg.status || "";

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

function stopSse() {
  if (sse) {
    try {
      sse.close();
    } catch (_e) {}
  }
  sse = null;
  sseProjectId = null;
}

function startSse(projectId) {
  if (!projectId) return;
  if (sse && sseProjectId === projectId) return;
  stopSse();

  const url = api(`/commissioning/projects/${encodeURIComponent(projectId)}/events`);
  sse = new EventSource(url);
  sseProjectId = projectId;

  const handle = (e) => {
    try {
      const payload = JSON.parse(String(e.data || "{}"));
      appendActivityRow(normalizeEventMessage(payload));
    } catch (_err) {
      appendActivityRow({ tsUtc: "", device: "", page: "", button: "", testTarget: "", status: "", targetKey: String(e.data || "") });
    }
  };
  sse.addEventListener("test_result", handle);
  sse.onmessage = handle;
}

async function refreshCommission() {
  const projectId = currentProjectId();
  if (!projectId) return;
  const progress = await jsonFetch(api(`/commissioning/projects/${encodeURIComponent(projectId)}/progress`));
  updateKpis(progress);
  startSse(projectId);
}

function runCommissionTab() {
  const tabCommission = document.getElementById("tab-commission");
  if (tabCommission) tabCommission.addEventListener("click", () => void refreshCommission());
  const tabManage = document.getElementById("tab-manage");
  if (tabManage) tabManage.addEventListener("click", () => stopSse());
  const tabDiagnostics = document.getElementById("tab-diagnostics");
  if (tabDiagnostics) tabDiagnostics.addEventListener("click", () => stopSse());

  const projectSelect = document.getElementById("projectSelect");
  if (projectSelect) {
    projectSelect.addEventListener("change", () => {
      stopSse();
      if (isCommissionVisible()) void refreshCommission();
    });
  }

  const refreshProgressBtn = document.getElementById("refreshProgressBtn");
  if (refreshProgressBtn) {
    refreshProgressBtn.addEventListener("click", () => {
      void refreshCommission();
    });
  }

  const empty = document.createElement("div");
  empty.className = "activity-empty";
  empty.id = "commissionActivityEmpty";
  empty.textContent = "No activity yet.";
  $("commissionActivity").appendChild(empty);
}

runCommissionTab();
