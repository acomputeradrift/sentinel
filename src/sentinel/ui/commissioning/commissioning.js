function $(id) {
  const el = document.getElementById(id);
  if (!el) throw new Error(`Missing element: ${id}`);
  return el;
}

function api(path) {
  return `/api/v1${path}`;
}

function setActiveTab(tabName) {
  const tabs = ["manage", "commission", "diagnostics"];
  for (const t of tabs) {
    const btn = document.getElementById(`tab-${t}`);
    const panel = document.getElementById(`panel-${t}`);
    if (!btn || !panel) continue;
    const active = t === tabName;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-selected", active ? "true" : "false");
    panel.hidden = !active;
  }
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
    $("projectSelect").dispatchEvent(new Event("change"));
    return [];
  }
  const projects = await jsonFetch(api(`/commissioning/clients/${encodeURIComponent(clientId)}/projects`));
  setSelectOptions($("projectSelect"), projects, (p) => p.projectId, (p) => p.name);
  $("projectSelect").dispatchEvent(new Event("change"));
  return projects;
}

function currentProjectId() {
  return $("projectSelect").value;
}

const state = {
  lastUploadIdByProject: {},
  generationReadyByProject: {},
  lastUploadFilenameByProject: {},
  techLinksByProject: {},
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

function updateTechLinkEnabled() {
  const projectId = currentProjectId();
  const ready = projectId ? !!state.generationReadyByProject[projectId] : false;
  $("createTechLinkBtn").disabled = !projectId || !ready;
}

function techLinksForProject(projectId) {
  return state.techLinksByProject[projectId] || [];
}

function renderTechLinks() {
  const body = $("techLinksBody");
  const empty = $("techLinksEmpty");
  const table = body.closest("table");
  body.innerHTML = "";

  const projectId = currentProjectId();
  if (!projectId) {
    empty.textContent = "Select a project to manage tech links.";
    empty.style.display = "";
    if (table) table.style.display = "none";
    return;
  }

  const items = techLinksForProject(projectId);
  if (table) table.style.display = "";
  if (!items.length) {
    empty.textContent = "No active tech links for this project.";
    empty.style.display = "";
    return;
  }

  empty.style.display = "none";
  for (const link of items) {
    const tr = document.createElement("tr");

    const tdLabel = document.createElement("td");
    tdLabel.textContent = link.label || "(no label)";

    const tdCreated = document.createElement("td");
    tdCreated.textContent = link.createdAtUtc || "";

    const tdUrl = document.createElement("td");
    const url = document.createElement("span");
    url.className = "mono";
    url.textContent = link.techUrl || "";
    tdUrl.appendChild(url);

    const tdActions = document.createElement("td");
    const revoke = document.createElement("button");
    revoke.type = "button";
    revoke.className = "danger";
    revoke.textContent = "Revoke";
    revoke.addEventListener("click", () => {
      const projectIdNow = currentProjectId();
      if (!projectIdNow) return;
      const statusEl = document.getElementById("techLinkStatus");
      const set = (msg) => statusEl && (statusEl.textContent = msg || "");
      set("");
      jsonFetch(api(`/commissioning/projects/${encodeURIComponent(projectIdNow)}/tech-links/${encodeURIComponent(link.techLinkId)}/rotate`), {
        method: "POST",
      })
        .then(() => {
          state.techLinksByProject[projectIdNow] = techLinksForProject(projectIdNow).filter((x) => x.techLinkId !== link.techLinkId);
          if ($("techUrl").textContent === (link.techUrl || "")) $("techUrl").textContent = "";
          renderTechLinks();
          set("Revoked (rotated token).");
        })
        .catch((e) => set(String(e?.message || e)));
    });
    tdActions.appendChild(revoke);

    tr.appendChild(tdLabel);
    tr.appendChild(tdCreated);
    tr.appendChild(tdUrl);
    tr.appendChild(tdActions);
    body.appendChild(tr);
  }
}

function _stripExtension(filename) {
  const s = String(filename || "").trim();
  const idx = s.lastIndexOf(".");
  return idx > 0 ? s.slice(0, idx) : s;
}

function _normalizedBaseTokens(filename) {
  let s = _stripExtension(filename).toLowerCase();
  s = s.replace(/[_-]+/g, " ");
  // Remove common version tokens: v55.2, ver 55.2, version 55.2, rev 3, build 102, b102
  s = s.replace(/\b(v|ver|version)\s*\d+(?:[._-]\d+){0,4}\b/g, " ");
  s = s.replace(/\b(r|rev|revision|build|b)\s*\d+(?:[._-]\d+)?\b/g, " ");
  // Remove standalone numeric tokens (dates/build numbers) to reduce false warnings on version bumps.
  s = s.replace(/\b\d+(?:[._-]\d+)*\b/g, " ");
  s = s.replace(/[^\p{L}\p{N}]+/gu, " ");
  s = s.replace(/\s+/g, " ").trim();
  const tokens = s.split(" ").filter((t) => t && t.length >= 2);
  return tokens;
}

function _baseSimilarity(a, b) {
  const ta = _normalizedBaseTokens(a);
  const tb = _normalizedBaseTokens(b);
  if (!ta.length || !tb.length) return 0;
  const setA = new Set(ta);
  const setB = new Set(tb);
  let inter = 0;
  for (const t of setA) if (setB.has(t)) inter += 1;
  const denom = Math.max(setA.size, setB.size) || 1;
  return inter / denom;
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
  state.generationReadyByProject[proj.projectId] = false;
  updateRegenerateEnabled();
  updateTechLinkEnabled();
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
    state.generationReadyByProject[projectId] = false;
    const prevName = state.lastUploadFilenameByProject[projectId];
    const nextName = upload.originalFilename;
    state.lastUploadFilenameByProject[projectId] = nextName;
    updateRegenerateEnabled();
    updateTechLinkEnabled();
    setProgress($("uploadProgress"), 100);
    setStatus($("uploadProgressLabel"), "Done");
    let msg = `Uploaded: ${upload.uploadId} (${upload.originalFilename})`;
    if (prevName && nextName) {
      const sim = _baseSimilarity(prevName, nextName);
      if (sim < 0.6) {
        msg += `\nWARNING: This upload name looks different than the previous file for this project.\nPrevious: ${prevName}\nNew: ${nextName}`;
      }
    }
    setStatus($("uploadStatus"), msg);
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
  state.generationReadyByProject[projectId] = false;
  updateTechLinkEnabled();
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
    const genId = out?.generationRun?.generationRunId;
    const status = out?.status;
    if (genId) {
      setStatus($("regenStatus"), `Regenerated: ${genId}`);
    } else if (status) {
      setStatus($("regenStatus"), `Regenerated: ${status}`);
    } else {
      setStatus($("regenStatus"), "Regenerated.");
    }
    state.generationReadyByProject[projectId] = true;
    updateTechLinkEnabled();
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
  const createdAtUtc = new Date().toISOString();
  state.techLinksByProject[projectId] = [
    { techLinkId: out.techLinkId, label: label || "", createdAtUtc, techUrl: out.techUrl || "" },
    ...techLinksForProject(projectId),
  ];
  renderTechLinks();
  const statusEl = document.getElementById("techLinkStatus");
  if (statusEl) statusEl.textContent = "Created tech link.";
}

async function run() {
  const safe = async (fn, statusEl) => {
    try {
      setStatus(statusEl, "");
      await fn();
    } catch (e) {
      setStatus(statusEl, String(e?.message || e));
      updateRegenerateEnabled();
      updateTechLinkEnabled();
    }
  };

  $("clientSelect").addEventListener("change", () => safe(refreshProjects, $("projectStatus")));
  $("projectSelect").addEventListener("change", () =>
    safe(async () => {
      const projectId = currentProjectId();
      if (projectId) state.generationReadyByProject[projectId] = false;
      updateRegenerateEnabled();
      updateTechLinkEnabled();
      renderTechLinks();
    }, $("projectStatus"))
  );

  $("tab-manage").addEventListener("click", () => setActiveTab("manage"));
  $("tab-commission").addEventListener("click", () => setActiveTab("commission"));
  $("tab-diagnostics").addEventListener("click", () => setActiveTab("diagnostics"));

  $("createClientBtn").addEventListener("click", () => safe(createClient, $("clientStatus")));
  $("createProjectBtn").addEventListener("click", () => safe(createProject, $("projectStatus")));
  $("uploadBtn").addEventListener("click", () => safe(uploadApex, $("uploadStatus")));
  $("regenerateBtn").addEventListener("click", () => safe(regenerate, $("regenStatus")));
  $("createTechLinkBtn").addEventListener("click", () => safe(createTechLink, $("techLinkStatus")));

  await safe(refreshClients, $("clientStatus"));
  setProgressHidden($("uploadProgress"), true);
  setProgressHidden($("regenProgress"), true);
  updateRegenerateEnabled();
  updateTechLinkEnabled();
  renderTechLinks();
  setActiveTab("manage");
}

run();

