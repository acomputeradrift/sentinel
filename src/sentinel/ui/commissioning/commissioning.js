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

const state = {
  lastUploadIdByProject: {},
};

function setProgressHidden(el, hidden) {
  el.style.display = hidden ? "none" : "";
}

function setProgress(el, pct) {
  if (pct == null) {
    el.removeAttribute("value");
    return;
  }
  el.value = Math.max(0, Math.min(100, pct));
}

function updateRegenerateEnabled() {
  const projectId = currentProjectId();
  const uploadId = projectId ? state.lastUploadIdByProject[projectId] : null;
  $("regenerateBtn").disabled = !projectId || !uploadId;
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
  updateRegenerateEnabled();
  setStatus($("projectStatus"), `Created project: ${proj.name}`);
}

async function uploadApex() {
  const projectId = currentProjectId();
  const file = $("apexFile").files && $("apexFile").files[0];
  if (!projectId || !file) return;

  const uploadBtn = $("uploadBtn");
  uploadBtn.disabled = true;
  setStatus($("uploadStatus"), "");
  setProgressHidden($("uploadProgress"), false);
  setProgress($("uploadProgress"), 0);
  setStatus($("uploadProgressLabel"), "Uploading...");

  const fd = new FormData();
  fd.append("apex", file, file.name);

  try {
    const upload = await new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", api(`/commissioning/projects/${encodeURIComponent(projectId)}/uploads`));
      xhr.upload.onprogress = (evt) => {
        if (!evt.lengthComputable) return;
        const pct = (evt.loaded / evt.total) * 100;
        setProgress($("uploadProgress"), pct);
        setStatus($("uploadProgressLabel"), `${Math.round(pct)}%`);
      };
      xhr.onerror = () => reject(new Error("Upload failed."));
      xhr.onload = () => {
        const ct = xhr.getResponseHeader("content-type") || "";
        if (xhr.status < 200 || xhr.status >= 300) {
          try {
            if (ct.includes("application/json")) {
              const body = JSON.parse(xhr.responseText || "{}");
              if (body && body.error && body.error.message) return reject(new Error(String(body.error.message)));
              return reject(new Error(JSON.stringify(body)));
            }
          } catch (_e) {}
          return reject(new Error(xhr.responseText || `HTTP ${xhr.status}`));
        }
        try {
          resolve(ct.includes("application/json") ? JSON.parse(xhr.responseText || "{}") : xhr.responseText);
        } catch (e) {
          reject(e);
        }
      };
      xhr.send(fd);
    });

    state.lastUploadIdByProject[projectId] = upload.uploadId;
    updateRegenerateEnabled();
    setProgress($("uploadProgress"), 100);
    setStatus($("uploadProgressLabel"), "Done");
    setStatus($("uploadStatus"), `Uploaded: ${upload.uploadId} (${upload.originalFilename})`);
  } finally {
    uploadBtn.disabled = false;
  }
}

async function regenerate() {
  const projectId = currentProjectId();
  if (!projectId) return;
  const uploadId = state.lastUploadIdByProject[projectId];
  if (!uploadId) {
    throw new Error("Upload an .apex first (no uploadId available).");
  }
  const regenBtn = $("regenerateBtn");
  regenBtn.disabled = true;
  setStatus($("regenStatus"), "");
  setProgressHidden($("regenProgress"), false);
  setProgress($("regenProgress"), null);
  setStatus($("regenProgressLabel"), "Regenerating...");
  try {
    const out = await jsonFetch(api(`/commissioning/projects/${encodeURIComponent(projectId)}/regenerate`), {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ uploadId }),
    });
    const genId = out?.generationRun?.generationRunId || "(missing)";
    setStatus($("regenStatus"), `Regenerated: ${genId}`);
  } finally {
    setProgressHidden($("regenProgress"), true);
    setStatus($("regenProgressLabel"), "");
    regenBtn.disabled = false;
    updateRegenerateEnabled();
  }
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
      updateRegenerateEnabled();
    }
  };

  $("refreshClientsBtn").addEventListener("click", () => safe(refreshClients, $("clientStatus")));
  $("refreshProjectsBtn").addEventListener("click", () => safe(refreshProjects, $("projectStatus")));
  $("clientSelect").addEventListener("change", () => safe(refreshProjects, $("projectStatus")));
  $("projectSelect").addEventListener("change", () => safe(updateRegenerateEnabled, $("projectStatus")));

  $("createClientBtn").addEventListener("click", () => safe(createClient, $("clientStatus")));
  $("createProjectBtn").addEventListener("click", () => safe(createProject, $("projectStatus")));
  $("uploadBtn").addEventListener("click", () => safe(uploadApex, $("uploadStatus")));
  $("regenerateBtn").addEventListener("click", () => safe(regenerate, $("regenStatus")));
  $("createTechLinkBtn").addEventListener("click", () => safe(createTechLink, $("projectStatus")));
  $("refreshProgressBtn").addEventListener("click", () => safe(refreshProgress, $("projectStatus")));

  await safe(refreshClients, $("clientStatus"));
  setProgressHidden($("uploadProgress"), true);
  setProgressHidden($("regenProgress"), true);
  updateRegenerateEnabled();
}

run();

