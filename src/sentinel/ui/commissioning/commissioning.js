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
  return `${proto}://${host}${path}`;
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
  if (!el) return;
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

function resetProjectDetailsUi() {
  setStatus($("uploadStatus"), "");
  setStatus($("uploadProgressLabel"), "");
  setStatus($("techLinkStatus"), "");
  $("techUrl").textContent = "";
  $("techLabel").value = "";
  setProgressHidden($("uploadProgressRow"), true);
}

function updateManageVisibility() {
  const hasClient = !!$("clientSelect").value;
  const hasProject = !!$("projectSelect").value;
  $("manageProjectCard").hidden = !hasClient;
  $("manageProjectDetails").hidden = !hasProject;
  if (!hasProject) resetProjectDetailsUi();
}

async function refreshClients() {
  const prevClientId = String($("clientSelect").value || "").trim();
  const rememberedClientId = _safeStorageGet(LAST_CLIENT_KEY).trim();
  const clients = await jsonFetch(api("/commissioning/clients"));
  setSelectOptions($("clientSelect"), clients, (c) => c.clientId, (c) => c.name);
  const clientIds = new Set((Array.isArray(clients) ? clients : []).map((c) => String(c?.clientId || "").trim()).filter(Boolean));
  const nextClientId = clientIds.has(rememberedClientId)
    ? rememberedClientId
    : clientIds.has(prevClientId)
      ? prevClientId
      : "";
  if (nextClientId) $("clientSelect").value = nextClientId;
  $("clientSelect").dispatchEvent(new Event("change"));
  updateManageVisibility();
  return clients;
}

async function refreshProjects() {
  const clientId = $("clientSelect").value;
  const requestSeq = ++state.refreshProjectsRequestSeq;
  if (!clientId) {
    if (requestSeq !== state.refreshProjectsRequestSeq) return [];
    setSelectOptions($("projectSelect"), [], () => "", () => "");
    $("projectSelect").dispatchEvent(new Event("change"));
    updateManageVisibility();
    return [];
  }
  const prevSelectedProjectId = String($("projectSelect").value || "").trim();
  const projects = await jsonFetch(api(`/commissioning/clients/${encodeURIComponent(clientId)}/projects`));
  if (requestSeq !== state.refreshProjectsRequestSeq) return projects;
  setSelectOptions($("projectSelect"), projects, (p) => p.projectId, (p) => p.name);
  const liveSelectedProjectId = String($("projectSelect").value || "").trim();
  const persistedByClient = _safeStorageGetJsonObject(LAST_PROJECT_BY_CLIENT_KEY);
  const rememberedProjectId = String((persistedByClient && persistedByClient[clientId]) || state.selectedProjectIdByClient[clientId] || "").trim();
  const projectIds = new Set((Array.isArray(projects) ? projects : []).map((p) => String(p?.projectId || "").trim()).filter(Boolean));
  const nextProjectId = projectIds.has(rememberedProjectId)
    ? rememberedProjectId
    : projectIds.has(liveSelectedProjectId)
      ? liveSelectedProjectId
      : projectIds.has(prevSelectedProjectId)
      ? prevSelectedProjectId
      : "";
  if (nextProjectId) $("projectSelect").value = nextProjectId;
  $("projectSelect").dispatchEvent(new Event("change"));
  updateManageVisibility();
  return projects;
}

function currentProjectId() {
  return $("projectSelect").value;
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
    return;
  }
  const activeUpload = state.activeUploadByProject[projectId] || null;
  const name = activeUpload && activeUpload.originalFilename ? String(activeUpload.originalFilename).trim() : "";
  el.textContent = name || "None";
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
    u.searchParams.set("runtime", "payload");
    return `${u.pathname}${u.search}${u.hash}`;
  } catch (_e) {
    return s.includes("?") ? `${s}&runtime=payload` : `${s}?runtime=payload`;
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
  $("clientSelect").dispatchEvent(new Event("change"));
  await refreshProjects();
  $("newClientName").value = "";
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
  $("projectSelect").dispatchEvent(new Event("change"));
  state.generationReadyByProject[proj.projectId] = false;
  updateTechLinkEnabled();
  $("newProjectName").value = "";
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
    let msg = uploadId ? `Uploaded: ${uploadId} (${nextName})` : `Uploaded: ${nextName}`;
    if (prevName && nextName) {
      const sim = _baseSimilarity(prevName, nextName);
      if (sim < 0.6) {
        msg += `\nWARNING: This upload name looks different than the previous file for this project.\nPrevious: ${prevName}\nNew: ${nextName}`;
      }
    }
    setStatus($("uploadStatus"), msg);
    state.generationReadyByProject[projectId] = true;
    updateTechLinkEnabled();
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
  const label = $("techLabel").value.trim() || null;
  if (!projectId) return;
  const out = await jsonFetch(api(`/commissioning/projects/${encodeURIComponent(projectId)}/tech-links`), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ label }),
  });
  const payloadTechUrl = buildPayloadTechUrl(out.techUrl || "");
  $("techUrl").textContent = payloadTechUrl || "";
  const createdAtUtc = new Date().toISOString();
  state.techLinksByProject[projectId] = [
    { techLinkId: out.techLinkId, label: label || "", createdAtUtc, techUrl: payloadTechUrl },
    ...techLinksForProject(projectId),
  ];
  renderTechLinks();
  const statusEl = document.getElementById("techLinkStatus");
  if (statusEl) statusEl.textContent = "Created tech link.";
}

async function run() {
  window.__sentinelCommissioningHydrating = true;
  const clientStatusEl = document.getElementById("clientStatus");
  const projectStatusEl = document.getElementById("projectStatus");

  const safe = async (fn, statusEl) => {
    try {
      setStatus(statusEl, "");
      await fn();
    } catch (e) {
      setStatus(statusEl, String(e?.message || e));
      updateTechLinkEnabled();
    }
  };

  ensureManageStoreSubscription();

  $("clientSelect").addEventListener("change", () =>
    safe(async () => {
      const clientId = String($("clientSelect").value || "").trim();
      _safeStorageSet(LAST_CLIENT_KEY, clientId);
      await refreshProjects();
      setPanelContext();
      setLastGeneratedLabel();
      updateManageVisibility();
    }, projectStatusEl)
  );
  $("projectSelect").addEventListener("change", () =>
    safe(async () => {
      const projectId = currentProjectId();
      const clientId = String($("clientSelect").value || "").trim();
      if (clientId) {
        state.selectedProjectIdByClient[clientId] = projectId;
        const persistedByClient = _safeStorageGetJsonObject(LAST_PROJECT_BY_CLIENT_KEY);
        persistedByClient[clientId] = String(projectId || "");
        _safeStorageSetJsonObject(LAST_PROJECT_BY_CLIENT_KEY, persistedByClient);
      }
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
    }, projectStatusEl)
  );

  $("tab-manage").addEventListener("click", () => setActiveTab("manage"));
  $("tab-commission").addEventListener("click", () => setActiveTab("commission"));
  $("tab-diagnostics").addEventListener("click", () => setActiveTab("diagnostics"));

  $("createClientBtn").addEventListener("click", () => safe(createClient, clientStatusEl));
  $("createProjectBtn").addEventListener("click", () => safe(createProject, projectStatusEl));
  $("uploadBtn").addEventListener("click", () => safe(uploadAndRegenerate, $("uploadStatus")));
  $("createTechLinkBtn").addEventListener("click", () => safe(createTechLink, $("techLinkStatus")));

  await safe(refreshClients, clientStatusEl);
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
  setActiveTab("manage");
}

run();

