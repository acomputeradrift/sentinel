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
  h2.textContent = `Diagnostics${suffix}`;
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

function renderSummary(progress, fails) {
  const counts = progress?.counts || {};
  const tested = Number(counts.testedTargets || 0);
  const fail = Number(counts.fail || 0);
  const total = Number(counts.totalTargets || 0);
  const currentFails = Array.isArray(fails) ? fails.length : 0;
  const failRate = tested ? Math.round((fail / tested) * 1000) / 10 : 0;
  const completeness = Math.round((Number(counts.percentComplete || 0) * 100) * 10) / 10;

  const lines = [];
  lines.push(`Completion: ${completeness}% (${tested}/${total} tested)`);
  lines.push(`Fail rate: ${failRate}% (${fail}/${tested || 0} of tested)`);
  lines.push(`Current fails: ${currentFails}`);
  diag$("diagnosticsSummary").textContent = lines.join("\n");
}

function renderFailTypeBreakdown(fails) {
  const rows = Array.isArray(fails) ? fails : [];
  const counts = new Map();
  for (const rec of rows) {
    const label = normalizeTargetLabel(rec?.targetName || _targetNameFromTargetKey(rec?.targetKey || ""));
    counts.set(label, (counts.get(label) || 0) + 1);
  }
  const items = Array.from(counts.entries()).sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0])));
  const lines = items.length ? items.map(([label, n]) => `${label}: ${n}`).join("\n") : "No current failures.";
  diag$("diagnosticsFailTypeBreakdown").textContent = lines;
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
  const projectId = currentDiagProjectId();
  if (!projectId) {
    diag$("diagnosticsSummary").textContent = "";
    diag$("diagnosticsFailTypeBreakdown").textContent = "";
    diag$("diagnosticsTaskBody").innerHTML = "";
    return;
  }

  const [progress, fails] = await Promise.all([
    diagJsonFetch(diagApi(`/commissioning/projects/${encodeURIComponent(projectId)}/progress`)),
    diagJsonFetch(diagApi(`/commissioning/projects/${encodeURIComponent(projectId)}/fails`)),
  ]);

  renderSummary(progress, fails);
  renderFailTypeBreakdown(fails);
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
