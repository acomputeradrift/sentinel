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

function setSelectedTab(tab) {
  const mainBtn = $("tabMainBtn");
  const comBtn = $("tabCommissionBtn");
  const main = $("tabMain");
  const commission = $("tabCommission");

  const isCommission = tab === "commission";
  mainBtn.setAttribute("aria-selected", isCommission ? "false" : "true");
  comBtn.setAttribute("aria-selected", isCommission ? "true" : "false");

  if (isCommission) {
    main.setAttribute("hidden", "hidden");
    commission.removeAttribute("hidden");
  } else {
    commission.setAttribute("hidden", "hidden");
    main.removeAttribute("hidden");
  }
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
  const tsUtc = String(ev?.tsUtc || "");
  const type = String(ev?.type || "");
  const data = ev?.data && typeof ev.data === "object" ? ev.data : {};

  const targetKey = String(data.targetKey || ev?.targetKey || "");
  const outcome = String(data.outcome || data.currentOutcome || "");

  const identity = targetKey || "(unknown target)";
  const detail = outcome ? `outcome=${outcome}` : JSON.stringify(data);
  return { tsUtc, type, identity, detail };
}

function appendActivityRow(msg) {
  const body = $("commissionActivityBody");
  const empty = document.getElementById("commissionActivityEmpty");
  if (empty) empty.remove();

  const tr = document.createElement("tr");
  const tdTime = document.createElement("td");
  const tdType = document.createElement("td");
  const tdIdentity = document.createElement("td");
  const tdDetail = document.createElement("td");

  tdTime.className = "mono";
  tdType.className = "mono";
  tdIdentity.className = "mono";
  tdDetail.className = "mono";

  tdTime.textContent = msg.tsUtc || "";
  tdType.textContent = msg.type || "";
  tdIdentity.textContent = msg.identity || "";
  tdDetail.textContent = msg.detail || "";

  tr.appendChild(tdTime);
  tr.appendChild(tdType);
  tr.appendChild(tdIdentity);
  tr.appendChild(tdDetail);

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

  sse.onmessage = (e) => {
    try {
      const payload = JSON.parse(String(e.data || "{}"));
      appendActivityRow(normalizeEventMessage(payload));
    } catch (_err) {
      appendActivityRow({ tsUtc: "", type: "event.parseError", identity: "", detail: String(e.data || "") });
    }
  };
}

async function refreshCommission() {
  const projectId = currentProjectId();
  if (!projectId) return;
  const progress = await jsonFetch(api(`/commissioning/projects/${encodeURIComponent(projectId)}/progress`));
  updateKpis(progress);
  startSse(projectId);
}

function runCommissionTab() {
  $("tabMainBtn").addEventListener("click", () => setSelectedTab("main"));
  $("tabCommissionBtn").addEventListener("click", () => {
    setSelectedTab("commission");
    void refreshCommission();
  });

  const projectSelect = document.getElementById("projectSelect");
  if (projectSelect) {
    projectSelect.addEventListener("change", () => {
      stopSse();
      void refreshCommission();
    });
  }

  const refreshProgressBtn = document.getElementById("refreshProgressBtn");
  if (refreshProgressBtn) {
    refreshProgressBtn.addEventListener("click", () => {
      void refreshCommission();
    });
  }

  setSelectedTab("main");

  const empty = document.createElement("div");
  empty.className = "activity-empty";
  empty.id = "commissionActivityEmpty";
  empty.textContent = "No activity yet.";
  $("commissionActivity").appendChild(empty);
}

runCommissionTab();
