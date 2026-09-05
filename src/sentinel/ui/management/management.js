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

const state = {
  clients: [],
  projects: [],
  technicians: [],
  techLinks: [],
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
  try {
    await loadClients();
    await loadTechnicians();
    fillSelect($("projectSelect"), [], (p) => p.projectId, (p) => p.name, "Select project…");
    updateContextVisibility();
    renderTechLinks();
  } catch (e) {
    setStatus($("contextStatus"), String(e?.message || e));
  }
}

run();
