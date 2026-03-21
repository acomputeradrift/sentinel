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
    throw new Error(typeof body === "string" ? body : JSON.stringify(body));
  }
  if (ct.includes("application/json")) return res.json();
  return res.text();
}

function setStatus(el, msg) {
  el.textContent = msg || "";
}

function setSelectOptions(selectEl, items, getValue, getLabel) {
  selectEl.innerHTML = "";
  for (const item of items) {
    const opt = document.createElement("option");
    opt.value = getValue(item);
    opt.textContent = getLabel(item);
    selectEl.appendChild(opt);
  }
}

async function refreshClients() {
  const clients = await jsonFetch(api("/commissioning/clients"));
  setSelectOptions($("clientSelect"), clients, (c) => c.clientId, (c) => c.name);
  $("clientSelect").dispatchEvent(new Event("change"));
  return clients;
}

async function refreshProjects() {
  const clientId = $("clientSelect").value;
  if (!clientId) {
    setSelectOptions($("projectSelect"), [], () => "", () => "");
    return [];
  }
  const projects = await jsonFetch(api(`/commissioning/clients/${encodeURIComponent(clientId)}/projects`));
  setSelectOptions($("projectSelect"), projects, (p) => p.projectId, (p) => p.name);
  return projects;
}

function currentProjectId() {
  return $("projectSelect").value;
}

async function createClient() {
  const name = $("newClientName").value.trim();
  if (!name) return;
  const client = await jsonFetch(api("/commissioning/clients"), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ name }),
  });
  await refreshClients();
  $("clientSelect").value = client.clientId;
  await refreshProjects();
  setStatus($("clientStatus"), `Created client: ${client.name}`);
}

async function createProject() {
  const clientId = $("clientSelect").value;
  const name = $("newProjectName").value.trim();
  if (!clientId || !name) return;
  const proj = await jsonFetch(api(`/commissioning/clients/${encodeURIComponent(clientId)}/projects`), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ name }),
  });
  await refreshProjects();
  $("projectSelect").value = proj.projectId;
  setStatus($("projectStatus"), `Created project: ${proj.name}`);
}

async function uploadApex() {
  const projectId = currentProjectId();
  const file = $("apexFile").files && $("apexFile").files[0];
  if (!projectId || !file) return;
  const fd = new FormData();
  fd.append("apex", file, file.name);
  const upload = await jsonFetch(api(`/commissioning/projects/${encodeURIComponent(projectId)}/uploads`), {
    method: "POST",
    body: fd,
  });
  setStatus($("uploadStatus"), `Uploaded: ${upload.uploadId} (${upload.originalFilename})`);
}

async function regenerate() {
  const projectId = currentProjectId();
  if (!projectId) return;
  const out = await jsonFetch(api(`/commissioning/projects/${encodeURIComponent(projectId)}/regenerate`), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ uploadId: null }),
  });
  const genId = out?.generationRun?.generationRunId || "(missing)";
  setStatus($("regenStatus"), `Regenerated: ${genId}`);
}

async function createTechLink() {
  const projectId = currentProjectId();
  const label = $("techLabel").value.trim() || null;
  if (!projectId) return;
  const out = await jsonFetch(api(`/commissioning/projects/${encodeURIComponent(projectId)}/tech-links`), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ label }),
  });
  $("techUrl").textContent = out.techUrl || "";
}

async function refreshProgress() {
  const projectId = currentProjectId();
  if (!projectId) return;
  const out = await jsonFetch(api(`/commissioning/projects/${encodeURIComponent(projectId)}/progress`));
  const pct = Math.round(((out?.counts?.percentComplete || 0) * 100) * 10) / 10;
  $("progress").textContent = `${pct}% complete\n\n` + JSON.stringify(out, null, 2);
}

async function run() {
  const safe = async (fn, statusEl) => {
    try {
      setStatus(statusEl, "");
      await fn();
    } catch (e) {
      setStatus(statusEl, String(e?.message || e));
    }
  };

  $("refreshClientsBtn").addEventListener("click", () => safe(refreshClients, $("clientStatus")));
  $("refreshProjectsBtn").addEventListener("click", () => safe(refreshProjects, $("projectStatus")));
  $("clientSelect").addEventListener("change", () => safe(refreshProjects, $("projectStatus")));

  $("createClientBtn").addEventListener("click", () => safe(createClient, $("clientStatus")));
  $("createProjectBtn").addEventListener("click", () => safe(createProject, $("projectStatus")));
  $("uploadBtn").addEventListener("click", () => safe(uploadApex, $("uploadStatus")));
  $("regenerateBtn").addEventListener("click", () => safe(regenerate, $("regenStatus")));
  $("createTechLinkBtn").addEventListener("click", () => safe(createTechLink, $("projectStatus")));
  $("refreshProgressBtn").addEventListener("click", () => safe(refreshProgress, $("projectStatus")));

  await safe(refreshClients, $("clientStatus"));
}

run();

