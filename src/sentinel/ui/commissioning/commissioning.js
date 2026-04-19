function $(id) {
  const el = document.getElementById(id);
  if (!el) throw new Error(`Missing element: ${id}`);
  return el;
}

function api(path) {
  return `/api/v1${path}`;
}

function wsUrl(path) {
  const proto = window.location && window.location.protocol === "https:" ? "wss" : "ws";
  const host = window.location && window.location.host ? window.location.host : "localhost";
  const base = `${proto}://${host}${path}`;
  return withCommissioningKeyQuery(base);
}

function commissioningAuthHeaders() {
  const h = {};
  try {
    const k = window.localStorage.getItem("sentinel.commissioning.apiKey");
    if (k) h["X-Sentinel-Commissioning-Key"] = k;
  } catch (_e) {}
  return h;
}

function withCommissioningKeyQuery(url) {
  try {
    const k = window.localStorage.getItem("sentinel.commissioning.apiKey");
    if (!k) return url;
    const sep = url.indexOf("?") >= 0 ? "&" : "?";
    return `${url}${sep}commissioningKey=${encodeURIComponent(k)}`;
  } catch (_e) {
    return url;
  }
}

function ensureWsConsoleLogger() {
  if (window.__sentinelWsLog) return window.__sentinelWsLog;
  window.__sentinelWsLog = function wsLog(code, label, scope, detail) {
    try {
      if (typeof console === "undefined" || !console.log) return;
      const prefix = `${String(code || "WS-INFO-000")} ${String(label || "EVENT")} [${String(scope || "ws")}]`;
      console.log(prefix, detail == null ? "" : detail);
    } catch (_e) {}
  };
  return window.__sentinelWsLog;
}
ensureWsConsoleLogger();
window.__sentinelCommissioningHydrating = true;

const LAST_CLIENT_KEY = "sentinel.commissioning.lastClientId";
const LAST_PROJECT_BY_CLIENT_KEY = "sentinel.commissioning.lastProjectByClient";

/** Sentinel option values (not real API ids) — open create dialogs when chosen. */
const OPTION_NEW_CLIENT = "__new_client__";
const OPTION_NEW_PROJECT = "__new_project__";

function _safeStorageGet(key) {
  try {
    if (!window || !window.localStorage) return "";
    return String(window.localStorage.getItem(String(key || "")) || "");
  } catch (_e) {
    return "";
  }
}

function _safeStorageSet(key, value) {
  try {
    if (!window || !window.localStorage) return;
    window.localStorage.setItem(String(key || ""), String(value == null ? "" : value));
  } catch (_e) {}
}

function _safeStorageGetJsonObject(key) {
  const raw = _safeStorageGet(key).trim();
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch (_e) {
    return {};
  }
}

function _safeStorageSetJsonObject(key, obj) {
  try {
    _safeStorageSet(key, JSON.stringify(obj && typeof obj === "object" ? obj : {}));
  } catch (_e) {}
}

function setActiveTab(tabName) {
  const tabs = ["commission", "diagnostics", "file", "tech-links", "reports", "clear-tests"];
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
  if (!el) return;
  el.textContent = msg || "";
}

function setSelectOptions(selectEl, items, getValue, getLabel) {
  selectEl.innerHTML = "";
  const ph = document.createElement("option");
  ph.value = "";
  ph.textContent = selectEl.id === "projectSelect" ? "Select project…" : "Select client…";
  selectEl.appendChild(ph);
  for (const item of items) {
    const opt = document.createElement("option");
    opt.value = getValue(item);
    opt.textContent = getLabel(item);
    selectEl.appendChild(opt);
  }
}

function appendSelectNewOption(selectEl, value, label) {
  const opt = document.createElement("option");
  opt.value = value;
  opt.textContent = label;
  selectEl.appendChild(opt);
}

function parseHashRoute() {
  try {
    const raw = window.location.hash.replace(/^#/, "");
    const params = new URLSearchParams(raw);
    return {
      clientId: String(params.get("c") || "").trim(),
      projectId: String(params.get("p") || "").trim(),
    };
  } catch (_e) {
    return { clientId: "", projectId: "" };
  }
}

function writeHashRoute(clientId, projectId) {
  const next = new URLSearchParams();
  const c = String(clientId || "").trim();
  const p = String(projectId || "").trim();
  if (c) next.set("c", c);
  if (p) next.set("p", p);
  const frag = next.toString() ? `#${next.toString()}` : "";
  const url = `${window.location.pathname}${window.location.search}${frag}`;
  if (`${window.location.pathname}${window.location.search}${window.location.hash}` !== url) {
    history.replaceState(null, "", url);
  }
}

function resetProjectDetailsUi() {
  setStatus($("uploadStatus"), "");
  setStatus($("uploadProgressLabel"), "");
  setStatus($("techLinkStatus"), "");
  $("techLabel").value = "";
  const fin = $("apexFile");
  if (fin) fin.value = "";
  setProgressHidden($("uploadProgressRow"), true);
}

function currentClientId() {
  const v = String($("clientSelect").value || "").trim();
  if (!v || v === OPTION_NEW_CLIENT) return "";
  return v;
}

function updateManageVisibility() {
  const hasClient = !!currentClientId();
  const hasProject = !!currentProjectId();
  $("manageProjectDetails").hidden = !hasProject;
  const techBody = document.getElementById("techLinksPanelBody");
  if (techBody) techBody.hidden = !hasProject;
  const fh = document.getElementById("fileHintNoProject");
  if (fh) fh.hidden = hasProject;
  const th = document.getElementById("techHintNoProject");
  if (th) th.hidden = hasProject;
  if (!hasProject) resetProjectDetailsUi();
}

async function refreshClients() {
  const prevClientId = String($("clientSelect").value || "").trim();
  const rememberedClientId = _safeStorageGet(LAST_CLIENT_KEY).trim();
  const hashRoute = parseHashRoute();
  const clients = await jsonFetch(api("/commissioning/clients"));
  setSelectOptions($("clientSelect"), clients, (c) => c.clientId, (c) => c.name);
  appendSelectNewOption($("clientSelect"), OPTION_NEW_CLIENT, "+ New client…");
  const clientIds = new Set((Array.isArray(clients) ? clients : []).map((c) => String(c?.clientId || "").trim()).filter(Boolean));
  const hashClient = String(hashRoute.clientId || "").trim();
  let nextClientId = "";
  if (hashClient && clientIds.has(hashClient)) nextClientId = hashClient;
  else if (rememberedClientId && clientIds.has(rememberedClientId)) nextClientId = rememberedClientId;
  else if (prevClientId && clientIds.has(prevClientId)) nextClientId = prevClientId;
  $("clientSelect").value = nextClientId;
  $("clientSelect").dispatchEvent(new Event("change"));
  updateManageVisibility();
  return clients;
}

async function refreshProjects() {
  const clientId = currentClientId();
  const requestSeq = ++state.refreshProjectsRequestSeq;
  if (!clientId) {
    if (requestSeq !== state.refreshProjectsRequestSeq) return [];
    setSelectOptions($("projectSelect"), [], () => "", () => "");
    $("projectSelect").value = "";
    $("projectSelect").dispatchEvent(new Event("change"));
    writeHashRoute("", "");
    updateManageVisibility();
    return [];
  }
  const prevSelectedProjectId = String($("projectSelect").value || "").trim();
  const projects = await jsonFetch(api(`/commissioning/clients/${encodeURIComponent(clientId)}/projects`));
  if (requestSeq !== state.refreshProjectsRequestSeq) return projects;
  setSelectOptions($("projectSelect"), projects, (p) => p.projectId, (p) => p.name);
  appendSelectNewOption($("projectSelect"), OPTION_NEW_PROJECT, "+ New project…");
  const persistedByClient = _safeStorageGetJsonObject(LAST_PROJECT_BY_CLIENT_KEY);
  const rememberedProjectId = String((persistedByClient && persistedByClient[clientId]) || state.selectedProjectIdByClient[clientId] || "").trim();
  const projectIds = new Set((Array.isArray(projects) ? projects : []).map((p) => String(p?.projectId || "").trim()).filter(Boolean));
  const hashProject = String(parseHashRoute().projectId || "").trim();
  let nextProjectId = "";
  if (hashProject && projectIds.has(hashProject)) nextProjectId = hashProject;
  else if (rememberedProjectId && projectIds.has(rememberedProjectId)) nextProjectId = rememberedProjectId;
  else if (prevSelectedProjectId && projectIds.has(prevSelectedProjectId)) nextProjectId = prevSelectedProjectId;
  $("projectSelect").value = nextProjectId;
  $("projectSelect").dispatchEvent(new Event("change"));
  writeHashRoute(clientId, nextProjectId);
  updateManageVisibility();
  return projects;
}

function currentProjectId() {
  const v = String($("projectSelect").value || "").trim();
  if (!v || v === OPTION_NEW_PROJECT) return "";
  return v;
}

const state = {
  lastUploadIdByProject: {},
  generationReadyByProject: {},
  activeUploadByProject: {},
  techLinksByProject: {},
  selectedProjectIdByClient: {},
  uploadInFlightByProject: {},
  uploadFinalizeTimerByProject: {},
  refreshProjectsRequestSeq: 0,
  lastValidClientId: "",
  lastValidProjectId: "",
};

function setProgressHidden(el, hidden) {
  el.style.display = hidden ? "none" : "";
}

function setProgress(el, pct) {
  if (pct == null) {
    el.removeAttribute("value");
    return;
  }
  const n = Number(pct);
  if (!Number.isFinite(n)) return;
  el.value = Math.max(0, Math.min(100, n));
}

function updateTechLinkEnabled() {
  const projectId = currentProjectId();
  const ready = projectId ? !!state.generationReadyByProject[projectId] : false;
  $("createTechLinkBtn").disabled = !projectId || !ready;
}

function techLinksForProject(projectId) {
  return state.techLinksByProject[projectId] || [];
}

function formatUtc(ts) {
  const raw = String(ts || "").trim();
  if (!raw) return "";
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return raw;
  return d.toISOString().replace("T", " ").replace(/\.\d+Z$/, "Z");
}

function setLastGeneratedLabel() {
  const el = document.getElementById("lastGeneratedLabel");
  if (!el) return;
  const projectId = currentProjectId();
  if (!projectId) {
    el.textContent = "None";
    setFileUploadedAtLabel();
    return;
  }
  const activeUpload = state.activeUploadByProject[projectId] || null;
  const name = activeUpload && activeUpload.originalFilename ? String(activeUpload.originalFilename).trim() : "";
  el.textContent = name || "None";
  setFileUploadedAtLabel();
}

function setFileUploadedAtLabel() {
  const el = document.getElementById("fileUploadedAt");
  if (!el) return;
  const projectId = currentProjectId();
  const activeUpload = projectId ? state.activeUploadByProject[projectId] : null;
  const raw = activeUpload && activeUpload.uploadedAtUtc ? String(activeUpload.uploadedAtUtc).trim() : "";
  if (!raw) {
    el.textContent = "";
    el.hidden = true;
    return;
  }
  const formatted = formatUtc(raw);
  el.textContent = formatted ? `Uploaded: ${formatted}` : "";
  el.hidden = !formatted;
}

function setPanelContext() {
  const ids = ["panelContextClient", "panelContextProject", "panelContextClient2", "panelContextProject2"];
  for (const id of ids) {
    const el = document.getElementById(id);
    if (!el) continue;
    const sub = el.closest(".panel-context-sub");
    if (sub) sub.remove();
  }
}

function buildPayloadTechUrl(rawUrl) {
  const s = String(rawUrl || "").trim();
  if (!s) return "";
  if (!/^\/testing\/[^/?#]+/i.test(s)) return s;
  try {
    const u = new URL(s, window.location.origin);
    u.searchParams.set("runtime", "shell");
    return `${u.pathname}${u.search}${u.hash}`;
  } catch (_e) {
    return s.includes("?") ? `${s}&runtime=shell` : `${s}?runtime=shell`;
  }
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

    const tdLink = document.createElement("td");
    tdLink.className = "mono tech-link-url-cell";
    tdLink.setAttribute("data-testid", "tech-url");
    const linkText = String(link.techUrl || "").trim();
    tdLink.textContent = linkText;
    tdLink.title = linkText;

    const tdCreated = document.createElement("td");
    tdCreated.textContent = formatUtc(link.createdAtUtc || "");

    const tdActions = document.createElement("td");
    tdActions.className = "tech-link-actions";
    const open = document.createElement("button");
    open.type = "button";
    open.className = "tech-link-action-btn";
    open.textContent = "Open";
    open.addEventListener("click", () => {
      const url = String(link.techUrl || "").trim();
      if (!url) return;
      window.open(url, "_blank", "noopener");
    });
    tdActions.appendChild(open);

    const revoke = document.createElement("button");
    revoke.type = "button";
    revoke.className = "danger tech-link-action-btn";
    revoke.textContent = "Revoke";
    revoke.addEventListener("click", () => {
      const projectIdNow = currentProjectId();
      if (!projectIdNow) return;
      const statusEl = document.getElementById("techLinkStatus");
      const set = (msg) => statusEl && (statusEl.textContent = msg || "");
      set("");
      const revokeUrl = api(`/commissioning/projects/${encodeURIComponent(projectIdNow)}/tech-links/${encodeURIComponent(link.techLinkId)}/revoke`);
      jsonFetch(revokeUrl, { method: "POST" })
        .catch(() =>
          jsonFetch(api(`/commissioning/projects/${encodeURIComponent(projectIdNow)}/tech-links/${encodeURIComponent(link.techLinkId)}/rotate`), {
            method: "POST",
          })
        )
        .then(() => {
          state.techLinksByProject[projectIdNow] = techLinksForProject(projectIdNow).filter((x) => x.techLinkId !== link.techLinkId);
          renderTechLinks();
          set("Revoked.");
        })
        .catch((e) => set(String(e?.message || e)));
    });
    tdActions.appendChild(revoke);

    tr.appendChild(tdLabel);
    tr.appendChild(tdLink);
    tr.appendChild(tdCreated);
    tr.appendChild(tdActions);
    body.appendChild(tr);
  }
}

async function loadTechLinks() {
  const projectId = currentProjectId();
  if (!projectId) return;
  try {
    const rows = await jsonFetch(api(`/commissioning/projects/${encodeURIComponent(projectId)}/tech-links`));
    if (!Array.isArray(rows)) return;
    state.techLinksByProject[projectId] = rows
      .filter((r) => r && (r.active === undefined || !!r.active))
      .map((r) => ({
        techLinkId: r.techLinkId,
        label: r.label || "",
        createdAtUtc: r.createdAtUtc || "",
        techUrl: buildPayloadTechUrl(r.techUrl || ""),
      }));
    renderTechLinks();
  } catch (_e) {
    // Server may not support listing yet; fall back to in-memory UI list.
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

function _setGenerationPhaseUi(projectId, phaseRaw, percentRaw) {
  const pid = String(projectId || "").trim();
  if (!pid || pid !== String(currentProjectId() || "").trim()) return;
  const phase = String(phaseRaw || "").trim().toLowerCase();
  if (!state.uploadInFlightByProject[pid] && phase !== "ready") return;
  const pct = Number(percentRaw);
  const hasPct = Number.isFinite(pct);

  if (phase === "extracting") {
    setProgressHidden($("uploadProgressRow"), false);
    if (hasPct) setProgress($("uploadProgress"), pct);
    setStatus($("uploadProgressLabel"), "Extracting...");
    return;
  }
  if (phase === "generating") {
    setProgressHidden($("uploadProgressRow"), false);
    if (hasPct) setProgress($("uploadProgress"), pct);
    setStatus($("uploadProgressLabel"), "Generating...");
    return;
  }
  if (phase === "ready") {
    setProgressHidden($("uploadProgressRow"), false);
    setProgress($("uploadProgress"), 100);
    setStatus($("uploadProgressLabel"), "Generating...");
  }
}

function openModalNewClient() {
  const dlg = document.getElementById("modalNewClient");
  const name = document.getElementById("modalNewClientName");
  const st = document.getElementById("modalNewClientStatus");
  if (st) st.textContent = "";
  if (name) name.value = "";
  if (dlg && typeof dlg.showModal === "function") {
    dlg.showModal();
    setTimeout(() => {
      if (name) name.focus();
    }, 0);
  }
}

function openModalNewProject() {
  const dlg = document.getElementById("modalNewProject");
  const name = document.getElementById("modalNewProjectName");
  const st = document.getElementById("modalNewProjectStatus");
  if (st) st.textContent = "";
  if (name) name.value = "";
  if (dlg && typeof dlg.showModal === "function") {
    dlg.showModal();
    setTimeout(() => {
      if (name) name.focus();
    }, 0);
  }
}

async function createClient() {
  const nameEl = document.getElementById("modalNewClientName");
  const statusEl = document.getElementById("modalNewClientStatus");
  const dlg = document.getElementById("modalNewClient");
  const name = nameEl ? String(nameEl.value || "").trim() : "";
  if (!name) {
    if (statusEl) statusEl.textContent = "Name is required.";
    return;
  }
  if (statusEl) statusEl.textContent = "";
  const client = await jsonFetch(api("/commissioning/clients"), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (nameEl) nameEl.value = "";
  if (dlg && typeof dlg.close === "function") dlg.close();
  await refreshClients();
  $("clientSelect").value = client.clientId;
  state.lastValidClientId = client.clientId;
  $("clientSelect").dispatchEvent(new Event("change"));
  await refreshProjects();
}

async function createProject() {
  const clientId = currentClientId();
  const nameEl = document.getElementById("modalNewProjectName");
  const statusEl = document.getElementById("modalNewProjectStatus");
  const dlg = document.getElementById("modalNewProject");
  const name = nameEl ? String(nameEl.value || "").trim() : "";
  if (!clientId) {
    if (statusEl) statusEl.textContent = "Select a client first.";
    return;
  }
  if (!name) {
    if (statusEl) statusEl.textContent = "Name is required.";
    return;
  }
  if (statusEl) statusEl.textContent = "";
  const proj = await jsonFetch(api(`/commissioning/clients/${encodeURIComponent(clientId)}/projects`), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (nameEl) nameEl.value = "";
  if (dlg && typeof dlg.close === "function") dlg.close();
  await refreshProjects();
  $("projectSelect").value = proj.projectId;
  state.lastValidProjectId = proj.projectId;
  $("projectSelect").dispatchEvent(new Event("change"));
  state.generationReadyByProject[proj.projectId] = false;
  updateTechLinkEnabled();
}

function _xhrPostFormData(url, fd, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    if (xhr.upload && typeof onProgress === "function") {
      xhr.upload.onprogress = (evt) => {
        if (!evt.lengthComputable) return;
        onProgress(evt.loaded, evt.total);
      };
    }
    xhr.onerror = () => reject(new Error("Request failed."));
    xhr.onload = () => {
      const ct = xhr.getResponseHeader("content-type") || "";
      const ok = xhr.status >= 200 && xhr.status < 300;
      if (!ok) {
        try {
          if (ct.includes("application/json")) {
            const body = JSON.parse(xhr.responseText || "{}");
            if (body && typeof body === "object" && body.error && body.error.message) return reject(new Error(String(body.error.message)));
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
}

async function uploadAndRegenerate() {
  const projectId = currentProjectId();
  const file = $("apexFile").files && $("apexFile").files[0];
  if (!projectId || !file) return;

  const uploadBtn = $("uploadBtn");
  uploadBtn.disabled = true;
  if (state.uploadFinalizeTimerByProject[projectId]) {
    clearTimeout(state.uploadFinalizeTimerByProject[projectId]);
    delete state.uploadFinalizeTimerByProject[projectId];
  }
  setStatus($("uploadStatus"), "");
  setProgressHidden($("uploadProgressRow"), false);
  setProgress($("uploadProgress"), 0);
  setStatus($("uploadProgressLabel"), "Uploading...");

  const fd = new FormData();
  fd.append("apex", file, file.name);

  try {
    state.generationReadyByProject[projectId] = false;
    state.uploadInFlightByProject[projectId] = true;
    updateTechLinkEnabled();

    // Preferred server endpoint: upload + extract + generate in one step.
    // Assumption: server supports multipart upload with `apex` form part.
    const combinedUrl = api(`/commissioning/projects/${encodeURIComponent(projectId)}/upload-and-regenerate`);
    let combined;
    try {
      let uploadPhaseComplete = false;
      combined = await _xhrPostFormData(combinedUrl, fd, (loaded, total) => {
        const pct = (loaded / total) * 100;
        if (!uploadPhaseComplete && pct >= 100) {
          uploadPhaseComplete = true;
          setStatus($("uploadProgressLabel"), "Extracting...");
          setProgress($("uploadProgress"), 0);
          return;
        }
        if (!uploadPhaseComplete) {
          setProgress($("uploadProgress"), pct);
          setStatus($("uploadProgressLabel"), "Uploading...");
        }
      });
    } catch (e) {
      // Back-compat fallback: upload then regenerate.
      setStatus($("uploadProgressLabel"), "Uploading...");
      const upload = await _xhrPostFormData(api(`/commissioning/projects/${encodeURIComponent(projectId)}/uploads`), fd, (loaded, total) => {
        const pct = (loaded / total) * 100;
        setProgress($("uploadProgress"), pct);
        setStatus($("uploadProgressLabel"), "Uploading...");
      });
      state.lastUploadIdByProject[projectId] = upload.uploadId;
      setProgress($("uploadProgress"), 0);
      setStatus($("uploadProgressLabel"), "Extracting...");
      const regenOut = await jsonFetch(api(`/commissioning/projects/${encodeURIComponent(projectId)}/regenerate`), {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ uploadId: upload.uploadId }),
      });
      combined = { upload, regeneration: regenOut };
    }

    const uploadObj = combined?.upload || combined?.uploadResult || combined;
    const uploadId = uploadObj?.uploadId || state.lastUploadIdByProject[projectId] || null;
    if (uploadId) state.lastUploadIdByProject[projectId] = uploadId;
    state.generationReadyByProject[projectId] = false;
    const prevName = state.activeUploadByProject[projectId]?.originalFilename || "";
    const nextName = String((uploadObj?.originalFilename || file.name) || "");

    setProgress($("uploadProgress"), 100);
    const activeFromApi = combined?.activeUpload && typeof combined.activeUpload === "object" ? combined.activeUpload : null;
    const uploadedAtUtc =
      String(activeFromApi?.uploadedAtUtc || "").trim() || new Date().toISOString();
    state.activeUploadByProject[projectId] = {
      uploadId: uploadId || null,
      originalFilename: nextName,
      storagePath: String(activeFromApi?.storagePath || uploadObj?.storagePath || ""),
      uploadedAtUtc,
    };
    setLastGeneratedLabel();
    let msg = "";
    if (prevName && nextName) {
      const sim = _baseSimilarity(prevName, nextName);
      if (sim < 0.6) {
        msg = `WARNING: This upload name looks different than the previous file for this project.\nPrevious: ${prevName}\nNew: ${nextName}`;
      }
    }
    const statusLine = msg || (uploadId ? String(uploadId) : "");
    setStatus($("uploadStatus"), statusLine);
    state.generationReadyByProject[projectId] = true;
    updateTechLinkEnabled();
    const fin = $("apexFile");
    if (fin) fin.value = "";
  } finally {
    const finalizeUi = () => {
      state.uploadInFlightByProject[projectId] = false;
      setProgressHidden($("uploadProgressRow"), true);
      setStatus($("uploadProgressLabel"), "");
      delete state.uploadFinalizeTimerByProject[projectId];
    };
    if (state.generationReadyByProject[projectId]) {
      state.uploadFinalizeTimerByProject[projectId] = setTimeout(finalizeUi, 1200);
    } else {
      finalizeUi();
    }
    uploadBtn.disabled = false;
  }
}

function stopManageWs() {
  const manager = window.__sentinelProjectWsManager;
  if (!manager || typeof manager.setConsumer !== "function") return;
  manager.setConsumer("manage", {
    active: false,
    onMessage: noopManageSocketConsumer,
  });
}

let manageStoreUnsubscribe = null;

function getSharedProjectStore() {
  return window.__sentinelProjectStore || null;
}

function applyActiveUpload(projectId, activeUpload) {
  const pid = String(projectId || "").trim();
  if (!pid) return;
  if (activeUpload && typeof activeUpload === "object") {
    state.activeUploadByProject[pid] = {
      uploadId: activeUpload.uploadId || null,
      originalFilename: activeUpload.originalFilename || "",
      storagePath: activeUpload.storagePath || "",
      uploadedAtUtc: activeUpload.uploadedAtUtc || "",
    };
  } else {
    state.activeUploadByProject[pid] = null;
  }
  if (pid === currentProjectId()) setLastGeneratedLabel();
}

function syncManageFromStore(projectId) {
  const pid = String(projectId || currentProjectId() || "").trim();
  if (!pid) return;
  const store = getSharedProjectStore();
  if (!store || typeof store.getState !== "function") return;
  const root = store.getState();
  const projects = root && root.projects && typeof root.projects === "object" ? root.projects : {};
  const slice = projects[pid] || null;
  const activeUpload = slice?.activeUpload || null;
  applyActiveUpload(pid, activeUpload);
  state.generationReadyByProject[pid] = !!activeUpload;
  updateTechLinkEnabled();
}

function ensureManageStoreSubscription() {
  if (manageStoreUnsubscribe) return;
  const store = getSharedProjectStore();
  if (!store || typeof store.subscribe !== "function") {
    setTimeout(ensureManageStoreSubscription, 0);
    return;
  }
  manageStoreUnsubscribe = store.subscribe(() => {
    syncManageFromStore(currentProjectId());
  });
  syncManageFromStore(currentProjectId());
}

function noopManageSocketConsumer(payload) {
  const t = String(payload?.type || "").trim();
  if (t !== "generation_phase") return;
  const projectId = String(payload?.projectId || currentProjectId() || "").trim();
  _setGenerationPhaseUi(projectId, payload?.status, payload?.percent);
}

function startManageWs(projectId) {
  const pid = String(projectId || "").trim();
  if (!pid) {
    stopManageWs();
    return;
  }
  const manager = window.__sentinelProjectWsManager;
  if (!manager || typeof manager.setConsumer !== "function") {
    setTimeout(() => startManageWs(pid), 0);
    return;
  }
  manager.setConsumer("manage", {
    active: true,
    onMessage: noopManageSocketConsumer,
  });
}

function setActiveProjectWsContext(projectId) {
  const manager = window.__sentinelProjectWsManager;
  if (!manager || typeof manager.setActiveProject !== "function") return;
  manager.setActiveProject(String(projectId || "").trim());
}

async function createTechLink() {
  const projectId = currentProjectId();
  const label = $("techLabel").value.trim();
  if (!projectId) return;
  const statusEl = document.getElementById("techLinkStatus");
  if (!label) {
    if (statusEl) statusEl.textContent = "Tech label is required.";
    return;
  }
  const out = await jsonFetch(api(`/commissioning/projects/${encodeURIComponent(projectId)}/tech-links`), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ label }),
  });
  const payloadTechUrl = buildPayloadTechUrl(out.techUrl || "");
  const createdAtUtc = new Date().toISOString();
  state.techLinksByProject[projectId] = [
    { techLinkId: out.techLinkId, label: label, createdAtUtc, techUrl: payloadTechUrl },
    ...techLinksForProject(projectId),
  ];
  renderTechLinks();
  if (statusEl) statusEl.textContent = "";
}

async function clearTestsForProject() {
  const projectId = String(currentProjectId() || "").trim();
  if (!projectId) return;
  const out = await jsonFetch(api(`/commissioning/projects/${encodeURIComponent(projectId)}/clear-tests`), {
    method: "POST",
  });
  const store = window.__sentinelProjectStore;
  if (out && typeof out === "object" && store && typeof store.dispatch === "function") {
    store.dispatch(out);
  }
  const uploadStatus = document.getElementById("uploadStatus");
  if (uploadStatus) uploadStatus.textContent = "Cleared tests for this project.";
}

async function run() {
  window.__sentinelCommissioningHydrating = true;
  const modalClientStatusEl = document.getElementById("modalNewClientStatus");
  const modalProjectStatusEl = document.getElementById("modalNewProjectStatus");

  const safe = async (fn, statusEl) => {
    try {
      if (statusEl) setStatus(statusEl, "");
      await fn();
    } catch (e) {
      const msg = String(e?.message || e);
      if (statusEl) setStatus(statusEl, msg);
      else console.error("[commissioning]", msg);
      updateTechLinkEnabled();
    }
  };

  ensureManageStoreSubscription();

  $("clientSelect").addEventListener("change", () => {
    const raw = String($("clientSelect").value || "").trim();
    if (raw === OPTION_NEW_CLIENT) {
      $("clientSelect").value = state.lastValidClientId || "";
      openModalNewClient();
      return;
    }
    state.lastValidClientId = raw;
    void safe(async () => {
      const clientId = currentClientId();
      _safeStorageSet(LAST_CLIENT_KEY, clientId);
      writeHashRoute(clientId, "");
      await refreshProjects();
      setPanelContext();
      setLastGeneratedLabel();
      updateManageVisibility();
    }, null);
  });
  $("projectSelect").addEventListener("change", () => {
    const raw = String($("projectSelect").value || "").trim();
    if (raw === OPTION_NEW_PROJECT) {
      $("projectSelect").value = state.lastValidProjectId || "";
      openModalNewProject();
      return;
    }
    state.lastValidProjectId = raw;
    void safe(async () => {
      const projectId = currentProjectId();
      const clientId = currentClientId();
      if (clientId) {
        state.selectedProjectIdByClient[clientId] = projectId;
        const persistedByClient = _safeStorageGetJsonObject(LAST_PROJECT_BY_CLIENT_KEY);
        persistedByClient[clientId] = String(projectId || "");
        _safeStorageSetJsonObject(LAST_PROJECT_BY_CLIENT_KEY, persistedByClient);
      }
      writeHashRoute(clientId, projectId);
      if (window.__sentinelCommissioningHydrating) {
        setPanelContext();
        setLastGeneratedLabel();
        updateManageVisibility();
        updateTechLinkEnabled();
        renderTechLinks();
        return;
      }
      setActiveProjectWsContext(projectId);
      if (projectId) state.generationReadyByProject[projectId] = false;
      updateTechLinkEnabled();
      renderTechLinks();
      setPanelContext();
      setLastGeneratedLabel();
      updateManageVisibility();
      startManageWs(projectId);
      syncManageFromStore(projectId);
      await loadTechLinks();
    }, null);
  });

  $("tab-commission").addEventListener("click", () => setActiveTab("commission"));
  $("tab-diagnostics").addEventListener("click", () => setActiveTab("diagnostics"));
  $("tab-file").addEventListener("click", () => setActiveTab("file"));
  $("tab-tech-links").addEventListener("click", () => setActiveTab("tech-links"));
  $("tab-reports").addEventListener("click", () => setActiveTab("reports"));
  $("tab-clear-tests").addEventListener("click", () => setActiveTab("clear-tests"));
  const clearTestsBtn = document.getElementById("clearTestsBtn");
  if (clearTestsBtn) clearTestsBtn.addEventListener("click", () => safe(clearTestsForProject, $("uploadStatus")));

  window.addEventListener("hashchange", () => {
    void safe(refreshClients, null);
  });

  const modalNewClientCancel = document.getElementById("modalNewClientCancel");
  const modalNewClientSubmit = document.getElementById("modalNewClientSubmit");
  const modalNewProjectCancel = document.getElementById("modalNewProjectCancel");
  const modalNewProjectSubmit = document.getElementById("modalNewProjectSubmit");
  const modalNewClientEl = document.getElementById("modalNewClient");
  const modalNewProjectEl = document.getElementById("modalNewProject");
  if (modalNewClientCancel && modalNewClientEl) {
    modalNewClientCancel.addEventListener("click", () => {
      modalNewClientEl.close();
    });
  }
  if (modalNewProjectCancel && modalNewProjectEl) {
    modalNewProjectCancel.addEventListener("click", () => {
      modalNewProjectEl.close();
    });
  }
  if (modalNewClientSubmit) modalNewClientSubmit.addEventListener("click", () => safe(createClient, modalClientStatusEl));
  if (modalNewProjectSubmit) modalNewProjectSubmit.addEventListener("click", () => safe(createProject, modalProjectStatusEl));
  const modalNewClientNameEl = document.getElementById("modalNewClientName");
  const modalNewProjectNameEl = document.getElementById("modalNewProjectName");
  if (modalNewClientNameEl && modalNewClientSubmit) {
    modalNewClientNameEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        modalNewClientSubmit.click();
      }
    });
  }
  if (modalNewProjectNameEl && modalNewProjectSubmit) {
    modalNewProjectNameEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        modalNewProjectSubmit.click();
      }
    });
  }
  $("uploadBtn").addEventListener("click", () => safe(uploadAndRegenerate, $("uploadStatus")));
  $("createTechLinkBtn").addEventListener("click", () => safe(createTechLink, $("techLinkStatus")));

  await safe(refreshClients, null);
  state.lastValidClientId = currentClientId();
  state.lastValidProjectId = currentProjectId();
  setProgressHidden($("uploadProgressRow"), true);
  updateTechLinkEnabled();
  renderTechLinks();
  setPanelContext();
  setActiveProjectWsContext(currentProjectId());
  startManageWs(currentProjectId());
  syncManageFromStore(currentProjectId());
  setLastGeneratedLabel();
  updateManageVisibility();
  window.__sentinelCommissioningHydrating = false;
  try {
    window.dispatchEvent(new Event("sentinel:commissioning-hydrated"));
  } catch (_e) {}
  setActiveTab("commission");
}

run();

