function $(id) {
  const el = document.getElementById(id);
  if (!el) throw new Error(`Missing element: ${id}`);
  return el;
}

function api(path) {
  return `/api/v1${path}`;
}

function commissioningAuthHeaders() {
  const h = {};
  try {
    const k = window.localStorage.getItem("sentinel.commissioning.apiKey");
    if (k) h["X-Sentinel-Commissioning-Key"] = k;
  } catch (_e) {}
  return h;
}

async function jsonFetch(url, options) {
  const merged = { ...(options || {}) };
  merged.headers = { ...commissioningAuthHeaders(), ...(merged.headers || {}) };
  const res = await fetch(url, merged);
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

function setStatus(el, msg) {
  if (el) el.textContent = msg || "";
}

function formatUtc(ts) {
  const raw = String(ts || "").trim();
  if (!raw) return "";
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return raw;
  return d.toISOString().replace("T", " ").replace(/\.\d+Z$/, "Z");
}

function shellTechUrl(raw) {
  const s = String(raw || "").trim();
  if (!s) return "";
  return s.includes("?") ? `${s}&runtime=shell` : `${s}?runtime=shell`;
}

const OPTION_NEW_CLIENT = "__new_client__";
const OPTION_NEW_PROJECT = "__new_project__";

const PRESET_INCLUDE = {
  closeout: {
    cover: true,
    progressSummary: true,
    eventSectionCounts: false,
    deviceCounts: true,
    currentTargets: false,
    failDetail: true,
    programmerFields: false,
    fullHistory: false,
    includePriorPasses: false,
    testingTypeLegend: false,
    operatorAppendix: false,
  },
  dealer_punch_list: {
    cover: true,
    progressSummary: false,
    eventSectionCounts: false,
    deviceCounts: false,
    currentTargets: false,
    failDetail: true,
    programmerFields: true,
    fullHistory: false,
    includePriorPasses: false,
    testingTypeLegend: false,
    operatorAppendix: false,
  },
  full_audit: {
    cover: true,
    progressSummary: true,
    eventSectionCounts: true,
    deviceCounts: true,
    currentTargets: true,
    failDetail: true,
    programmerFields: true,
    fullHistory: true,
    includePriorPasses: true,
    testingTypeLegend: true,
    operatorAppendix: false,
  },
};

const INCLUDE_CHECKBOX_IDS = {
  cover: "includeCover",
  progressSummary: "includeProgressSummary",
  eventSectionCounts: "includeEventSectionCounts",
  deviceCounts: "includeDeviceCounts",
  currentTargets: "includeCurrentTargets",
  failDetail: "includeFailDetail",
  programmerFields: "includeProgrammerFields",
  fullHistory: "includeFullHistory",
  includePriorPasses: "includePriorPasses",
  testingTypeLegend: "includeTestingTypeLegend",
  operatorAppendix: "includeOperatorAppendix",
};

const state = {
  clients: [],
  projects: [],
  technicians: [],
  techLinks: [],
  allTechLinks: [],
  reportDevices: [],
};

function currentClientId() {
  const v = String($("clientSelect").value || "").trim();
  if (!v || v === OPTION_NEW_CLIENT) return "";
  return v;
}

function currentProjectId() {
  const v = String($("projectSelect").value || "").trim();
  if (!v || v === OPTION_NEW_PROJECT) return "";
  return v;
}

function currentProject() {
  const projectId = currentProjectId();
  if (!projectId) return null;
  return state.projects.find((p) => String(p.projectId || "") === projectId) || null;
}

function fillSelect(selectEl, items, getValue, getLabel, placeholder, extra) {
  selectEl.innerHTML = "";
  const ph = document.createElement("option");
  ph.value = "";
  ph.textContent = placeholder;
  selectEl.appendChild(ph);
  for (const item of items) {
    const opt = document.createElement("option");
    opt.value = getValue(item);
    opt.textContent = getLabel(item);
    selectEl.appendChild(opt);
  }
  if (extra) {
    const opt = document.createElement("option");
    opt.value = extra.value;
    opt.textContent = extra.label;
    selectEl.appendChild(opt);
  }
}

function renderRoster() {
  const list = $("technicianRoster");
  const names = $("rosterNames");
  list.innerHTML = "";
  names.innerHTML = "";
  for (const tech of state.technicians) {
    const li = document.createElement("li");
    li.textContent = tech.name;
    list.appendChild(li);
    const opt = document.createElement("option");
    opt.value = tech.name;
    names.appendChild(opt);
  }
}

function renderAllTechLinks() {
  const body = $("allTechLinksBody");
  const empty = $("allTechLinksEmpty");
  body.innerHTML = "";
  const items = state.allTechLinks;
  empty.style.display = items.length ? "none" : "";
  for (const link of items) {
    const tr = document.createElement("tr");
    const tdClient = document.createElement("td");
    tdClient.textContent = link.clientName || "";
    const tdProject = document.createElement("td");
    tdProject.textContent = link.projectName || "";
    const tdName = document.createElement("td");
    tdName.textContent = link.name || link.label || "(unnamed)";
    const tdUrl = document.createElement("td");
    tdUrl.className = "mono";
    tdUrl.setAttribute("data-testid", "all-tech-url");
    tdUrl.textContent = String(link.techUrl || "");
    const tdIssued = document.createElement("td");
    tdIssued.textContent = formatUtc(link.issuedAtUtc || link.createdAtUtc || "");
    const tdActions = document.createElement("td");
    tdActions.className = "tech-link-actions";
    const revoke = document.createElement("button");
    revoke.type = "button";
    revoke.className = "danger";
    revoke.textContent = "Revoke";
    revoke.addEventListener("click", () => {
      void revokeAnyLink(link);
    });
    tdActions.appendChild(revoke);
    tr.appendChild(tdClient);
    tr.appendChild(tdProject);
    tr.appendChild(tdName);
    tr.appendChild(tdUrl);
    tr.appendChild(tdIssued);
    tr.appendChild(tdActions);
    body.appendChild(tr);
  }
}

async function loadAllTechLinks() {
  const rows = await jsonFetch(api("/commissioning/tech-links"));
  state.allTechLinks = Array.isArray(rows) ? rows : [];
  renderAllTechLinks();
}

async function revokeAnyLink(link) {
  if (!link?.techLinkId) return;
  await jsonFetch(api(`/commissioning/tech-links/${encodeURIComponent(link.techLinkId)}/revoke`), {
    method: "POST",
  });
  await loadAllTechLinks();
  if (currentProjectId()) await loadTechLinks();
}

function renderTechLinks() {
  const body = $("techLinksBody");
  const empty = $("techLinksEmpty");
  body.innerHTML = "";
  const items = state.techLinks;
  empty.style.display = items.length ? "none" : "";
  for (const link of items) {
    const tr = document.createElement("tr");
    const tdName = document.createElement("td");
    tdName.textContent = link.name || link.label || "(unnamed)";
    const tdUrl = document.createElement("td");
    tdUrl.className = "mono";
    tdUrl.setAttribute("data-testid", "tech-url");
    tdUrl.textContent = String(link.techUrl || "");
    const tdIssued = document.createElement("td");
    tdIssued.textContent = formatUtc(link.issuedAtUtc || link.createdAtUtc || "");
    const tdStatus = document.createElement("td");
    tdStatus.textContent = link.revokedAtUtc ? "Revoked" : "Active";
    const tdActions = document.createElement("td");
    tdActions.className = "tech-link-actions";

    const copy = document.createElement("button");
    copy.type = "button";
    copy.className = "secondary";
    copy.textContent = "Copy";
    copy.addEventListener("click", async () => {
      const url = String(link.techUrl || "").trim();
      if (!url) return;
      try {
        await navigator.clipboard.writeText(url);
        setStatus($("techLinkStatus"), "Copied.");
      } catch (_e) {
        setStatus($("techLinkStatus"), "Copy failed.");
      }
    });

    const open = document.createElement("button");
    open.type = "button";
    open.className = "secondary";
    open.textContent = "Open";
    open.addEventListener("click", () => {
      const url = shellTechUrl(link.techUrl || "");
      if (!url) return;
      window.open(url, "_blank", "noopener");
    });

    const rotate = document.createElement("button");
    rotate.type = "button";
    rotate.className = "secondary";
    rotate.textContent = "Rotate";
    rotate.addEventListener("click", () => {
      void rotateLink(link);
    });

    const revoke = document.createElement("button");
    revoke.type = "button";
    revoke.className = "danger";
    revoke.textContent = "Revoke";
    revoke.addEventListener("click", () => {
      void revokeLink(link);
    });

    tdActions.appendChild(copy);
    tdActions.appendChild(open);
    tdActions.appendChild(rotate);
    tdActions.appendChild(revoke);
    tr.appendChild(tdName);
    tr.appendChild(tdUrl);
    tr.appendChild(tdIssued);
    tr.appendChild(tdStatus);
    tr.appendChild(tdActions);
    body.appendChild(tr);
  }
}

function updateContextVisibility() {
  const clientChoice = String($("clientSelect").value || "");
  const projectChoice = String($("projectSelect").value || "");
  const showNewClient = clientChoice === OPTION_NEW_CLIENT;
  $("newClientRow").hidden = !showNewClient;
  $("newClientSubmit").hidden = !showNewClient;
  const showNewProject = !!currentClientId() && projectChoice === OPTION_NEW_PROJECT;
  $("newProjectRow").hidden = !showNewProject;
  $("newProjectSubmit").hidden = !showNewProject;
  const hasProject = !!currentProjectId();
  $("techLinksBodyWrap").hidden = !hasProject;
  $("techLinksHint").hidden = hasProject;
  $("testPassBodyWrap").hidden = !hasProject;
  $("testPassHint").hidden = hasProject;
  $("reportsBodyWrap").hidden = !hasProject;
  $("reportsHint").hidden = hasProject;
}

async function loadClients() {
  const rows = await jsonFetch(api("/commissioning/clients"));
  state.clients = Array.isArray(rows) ? rows : [];
  fillSelect(
    $("clientSelect"),
    state.clients,
    (c) => c.clientId,
    (c) => c.name,
    "Select client…",
    { value: OPTION_NEW_CLIENT, label: "New client…" }
  );
}

async function loadProjects() {
  const clientId = currentClientId();
  if (!clientId) {
    state.projects = [];
    fillSelect($("projectSelect"), [], (p) => p.projectId, (p) => p.name, "Select project…");
    return;
  }
  const rows = await jsonFetch(api(`/commissioning/clients/${encodeURIComponent(clientId)}/projects`));
  state.projects = Array.isArray(rows) ? rows : [];
  fillSelect(
    $("projectSelect"),
    state.projects,
    (p) => p.projectId,
    (p) => p.name,
    "Select project…",
    { value: OPTION_NEW_PROJECT, label: "New project…" }
  );
}

async function loadTechnicians() {
  const body = await jsonFetch(api("/commissioning/technicians"));
  state.technicians = Array.isArray(body?.technicians) ? body.technicians : [];
  renderRoster();
}

async function loadTechLinks() {
  const projectId = currentProjectId();
  if (!projectId) {
    state.techLinks = [];
    renderTechLinks();
    return;
  }
  const rows = await jsonFetch(api(`/commissioning/projects/${encodeURIComponent(projectId)}/tech-links`));
  state.techLinks = Array.isArray(rows) ? rows : [];
  renderTechLinks();
}

async function createClient() {
  const name = $("newClientName").value.trim();
  if (!name) {
    setStatus($("contextStatus"), "Client name is required.");
    return;
  }
  const created = await jsonFetch(api("/commissioning/clients"), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ name }),
  });
  $("newClientName").value = "";
  await loadClients();
  $("clientSelect").value = created.clientId;
  await loadProjects();
  updateContextVisibility();
  setStatus($("contextStatus"), "");
}

async function createProject() {
  const clientId = currentClientId();
  const name = $("newProjectName").value.trim();
  if (!clientId || !name) {
    setStatus($("contextStatus"), "Project name is required.");
    return;
  }
  const created = await jsonFetch(api(`/commissioning/clients/${encodeURIComponent(clientId)}/projects`), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ name }),
  });
  $("newProjectName").value = "";
  await loadProjects();
  $("projectSelect").value = created.projectId;
  await loadTechLinks();
  await loadReportDevices();
  updateContextVisibility();
  setStatus($("contextStatus"), "");
}

async function createTechnician() {
  const name = $("newTechnicianName").value.trim();
  if (!name) {
    setStatus($("technicianStatus"), "Technician name is required.");
    return;
  }
  await jsonFetch(api("/commissioning/technicians"), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ name }),
  });
  $("newTechnicianName").value = "";
  await loadTechnicians();
  setStatus($("technicianStatus"), "");
}

async function issueOrReuseLink() {
  const projectId = currentProjectId();
  const name = $("techLinkName").value.trim();
  if (!projectId) return;
  if (!name) {
    setStatus($("techLinkStatus"), "Technician name is required.");
    return;
  }
  await jsonFetch(api(`/commissioning/projects/${encodeURIComponent(projectId)}/tech-links`), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ name, label: name }),
  });
  await loadTechLinks();
  await loadTechnicians();
  await loadAllTechLinks();
  setStatus($("techLinkStatus"), "");
}

async function rotateLink(link) {
  const projectId = currentProjectId();
  if (!projectId || !link?.techLinkId) return;
  await jsonFetch(
    api(`/commissioning/projects/${encodeURIComponent(projectId)}/tech-links/${encodeURIComponent(link.techLinkId)}/rotate`),
    { method: "POST" }
  );
  await loadTechLinks();
}

function applyReportPreset() {
  const preset = String($("reportPreset").value || "closeout");
  const include = PRESET_INCLUDE[preset] || PRESET_INCLUDE.closeout;
  for (const [key, id] of Object.entries(INCLUDE_CHECKBOX_IDS)) {
    $(id).checked = !!include[key];
  }
}

function renderReportDevices() {
  const host = $("reportDeviceChecks");
  host.innerHTML = "";
  for (const device of state.reportDevices) {
    const label = document.createElement("label");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = true;
    input.value = String(device.deviceId);
    label.appendChild(input);
    label.appendChild(document.createTextNode(` ${device.displayName || device.deviceId}`));
    host.appendChild(label);
  }
}

async function loadReportDevices() {
  const projectId = currentProjectId();
  if (!projectId) {
    state.reportDevices = [];
    renderReportDevices();
    return;
  }
  try {
    const progress = await jsonFetch(api(`/commissioning/projects/${encodeURIComponent(projectId)}/progress`));
    state.reportDevices = Array.isArray(progress?.devices) ? progress.devices : [];
  } catch (_e) {
    state.reportDevices = [];
  }
  renderReportDevices();
}

function readReportOptions() {
  const include = {};
  for (const [key, id] of Object.entries(INCLUDE_CHECKBOX_IDS)) {
    include[key] = !!$(id).checked;
  }
  const deviceBoxes = Array.from($("reportDeviceChecks").querySelectorAll("input[type=checkbox]"));
  const deviceIds = deviceBoxes.filter((el) => el.checked).map((el) => el.value);
  return {
    preset: String($("reportPreset").value || "closeout"),
    scope: {
      includeSystemEvents: $("scopeSystemEvents").checked,
      includeDriverEvents: $("scopeDriverEvents").checked,
      includeDevices: $("scopeDevices").checked,
      includeDisabledTypes: $("scopeIncludeDisabledTypes").checked,
      deviceIds: deviceIds.length && deviceIds.length !== deviceBoxes.length ? deviceIds : undefined,
    },
    include,
  };
}

async function generateReport() {
  const projectId = currentProjectId();
  if (!projectId) return;
  const payload = readReportOptions();
  const merged = {
    method: "POST",
    headers: { ...commissioningAuthHeaders(), "content-type": "application/json" },
    body: JSON.stringify(payload),
  };
  const res = await fetch(api(`/commissioning/projects/${encodeURIComponent(projectId)}/reports`), merged);
  const ct = res.headers.get("content-type") || "";
  if (!res.ok) {
    const body = ct.includes("application/json") ? await res.json() : await res.text();
    if (body && typeof body === "object" && body.error && body.error.message) {
      throw new Error(String(body.error.message));
    }
    throw new Error(typeof body === "string" ? body : JSON.stringify(body));
  }
  const disposition = res.headers.get("content-disposition") || "";
  const match = disposition.match(/filename="([^"]+)"/);
  const filename = match ? match[1] : "report.pdf";
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
  setStatus($("reportStatus"), "Report downloaded.");
}

async function startNewTestPass() {
  const project = currentProject();
  if (!project) return;
  const confirmName = $("testPassConfirmName").value.trim();
  const reason = $("testPassReason").value.trim();
  if (!confirmName) {
    setStatus($("testPassStatus"), "Type the project name to confirm.");
    return;
  }
  if (confirmName !== String(project.name || "").trim()) {
    setStatus($("testPassStatus"), "Project name does not match.");
    return;
  }
  const body = { confirmName };
  if (reason) body.reason = reason;
  await jsonFetch(api(`/commissioning/projects/${encodeURIComponent(project.projectId)}/test-passes`), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  $("testPassConfirmName").value = "";
  $("testPassReason").value = "";
  setStatus($("testPassStatus"), "New test pass started.");
}

async function revokeLink(link) {
  const projectId = currentProjectId();
  if (!projectId || !link?.techLinkId) return;
  await jsonFetch(
    api(`/commissioning/projects/${encodeURIComponent(projectId)}/tech-links/${encodeURIComponent(link.techLinkId)}/revoke`),
    { method: "POST" }
  );
  await loadTechLinks();
  await loadAllTechLinks();
}

async function onClientChange() {
  updateContextVisibility();
  if (currentClientId()) {
    await loadProjects();
  } else {
    state.projects = [];
    fillSelect($("projectSelect"), [], (p) => p.projectId, (p) => p.name, "Select project…");
  }
  state.techLinks = [];
  renderTechLinks();
  updateContextVisibility();
}

async function onProjectChange() {
  updateContextVisibility();
  await loadTechLinks();
  await loadReportDevices();
}

async function run() {
  $("clientSelect").addEventListener("change", () => {
    void onClientChange();
  });
  $("projectSelect").addEventListener("change", () => {
    void onProjectChange();
  });
  $("newClientSubmit").addEventListener("click", () => {
    void createClient().catch((e) => setStatus($("contextStatus"), String(e?.message || e)));
  });
  $("newProjectSubmit").addEventListener("click", () => {
    void createProject().catch((e) => setStatus($("contextStatus"), String(e?.message || e)));
  });
  $("createTechnicianBtn").addEventListener("click", () => {
    void createTechnician().catch((e) => setStatus($("technicianStatus"), String(e?.message || e)));
  });
  $("issueTechLinkBtn").addEventListener("click", () => {
    void issueOrReuseLink().catch((e) => setStatus($("techLinkStatus"), String(e?.message || e)));
  });
  $("startTestPassBtn").addEventListener("click", () => {
    void startNewTestPass().catch((e) => setStatus($("testPassStatus"), String(e?.message || e)));
  });
  $("reportPreset").addEventListener("change", () => {
    applyReportPreset();
  });
  $("generateReportBtn").addEventListener("click", () => {
    void generateReport().catch((e) => setStatus($("reportStatus"), String(e?.message || e)));
  });
  try {
    await loadClients();
    await loadTechnicians();
    fillSelect($("projectSelect"), [], (p) => p.projectId, (p) => p.name, "Select project…");
    updateContextVisibility();
    applyReportPreset();
    renderTechLinks();
    await loadAllTechLinks();
  } catch (e) {
    setStatus($("contextStatus"), String(e?.message || e));
  }
}

run();
