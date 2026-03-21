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
  if (name === "Macro") return "macro";
  if (name === "MacroSteps") return "macro step";
  if (name === "PageLink") return "pageLink";
  if (name.startsWith("Var.")) return `variable - ${name.slice(4)}`;
  return name;
}

function parseIdentity(targetKey) {
  const raw = String(targetKey || "").trim();
  const parts = raw ? raw.split(":") : [];
  const kind = parts[0] || "";
  if (kind === "event" && parts.length >= 3) {
    return { scope: "EVENT", device: "", page: "", button: "", testTarget: targetLabelFromTargetKey(raw) };
  }
  if (kind === "btn" && parts.length >= 5) {
    return { scope: "BUTTON", device: parts[1] || "", page: parts[2] || "", button: parts[3] || "", testTarget: targetLabelFromTargetKey(raw) };
  }
  if (kind === "vpbtn" && parts.length >= 7) {
    return { scope: "VIEWPORT_BUTTON", device: parts[1] || "", page: parts[2] || "", button: parts[5] || "", testTarget: targetLabelFromTargetKey(raw) };
  }
  return { scope: "", device: "", page: "", button: "", testTarget: targetLabelFromTargetKey(raw) };
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
    const key = String(rec?.targetKey || "");
    const label = targetLabelFromTargetKey(key);
    counts.set(label, (counts.get(label) || 0) + 1);
  }
  const items = Array.from(counts.entries()).sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0])));
  const lines = items.length ? items.map(([label, n]) => `${label}: ${n}`).join("\n") : "No current failures.";
  diag$("diagnosticsFailTypeBreakdown").textContent = lines;
}

async function updateFailTag(projectId, targetKey, tag) {
  await diagJsonFetch(diagApi(`/commissioning/projects/${encodeURIComponent(projectId)}/fails/tag`), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ targetKey, tag }),
  });
}

function tagOptions() {
  return ["Not Started", "In Progress", "Done"];
}

function renderTaskList(projectId, fails) {
  const tbody = diag$("diagnosticsTaskBody");
  tbody.innerHTML = "";
  const rows = Array.isArray(fails) ? fails : [];
  rows.sort((a, b) => String(b?.lastTestedAtUtc || "").localeCompare(String(a?.lastTestedAtUtc || "")));

  for (const rec of rows) {
    const targetKey = String(rec?.targetKey || "");
    const ident = parseIdentity(targetKey);
    const tag = String(rec?.tag || "Not Started");
    const at = String(rec?.lastTestedAtUtc || "");
    const note = String(rec?.resolvedData || rec?.lastFailNote || "");

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
      const next = sel.value;
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
    tdAt.className = "mono";
    tdAt.textContent = at || "";

    const tdDevice = document.createElement("td");
    tdDevice.textContent = ident.device ? `d${ident.device}` : "";

    const tdPage = document.createElement("td");
    tdPage.textContent = ident.page ? `p${ident.page}` : "";

    const tdButton = document.createElement("td");
    tdButton.textContent = ident.button ? `b${ident.button}` : "";

    const tdScope = document.createElement("td");
    tdScope.textContent = ident.scope || "";

    const tdTarget = document.createElement("td");
    tdTarget.textContent = ident.testTarget || "";

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
    refreshBtn.addEventListener("click", () => {
      setDiagStatus("");
      refreshDiagnostics().catch((e) => setDiagStatus(String(e?.message || e)));
    });
  }

  const projectSelect = document.getElementById("projectSelect");
  if (projectSelect) {
    projectSelect.addEventListener("change", () => {
      setDiagStatus("");
      refreshDiagnostics().catch((e) => setDiagStatus(String(e?.message || e)));
    });
  }
}

initDiagnosticsTab();
