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

const state = {
  allTechLinks: [],
  clients: [],
};

function groupLinksByUser(links) {
  const groups = [];
  const byKey = new Map();
  for (const link of links) {
    const key = String(link.ownerUserId || link.ownerName || "unknown");
    const label = String(link.ownerName || link.ownerUserId || "Unknown user").trim() || "Unknown user";
    if (!byKey.has(key)) {
      const group = { key, label, links: [] };
      byKey.set(key, group);
      groups.push(group);
    }
    byKey.get(key).links.push(link);
  }
  return groups;
}

function renderAllTechLinks() {
  const host = $("allTechLinksByUser");
  const empty = $("allTechLinksEmpty");
  host.innerHTML = "";
  const groups = groupLinksByUser(state.allTechLinks);
  empty.style.display = groups.length ? "none" : "";
  for (const group of groups) {
    const section = document.createElement("section");
    section.className = "user-group";
    const heading = document.createElement("h3");
    heading.setAttribute("data-testid", "tech-link-user");
    heading.textContent = group.label;
    section.appendChild(heading);

    const wrap = document.createElement("div");
    wrap.className = "table-wrap";
    const table = document.createElement("table");
    table.className = "mini-table";
    table.setAttribute("aria-label", `Active tech links for ${group.label}`);
    const thead = document.createElement("thead");
    thead.innerHTML =
      "<tr><th>Client</th><th>Project</th><th>Technician</th><th>Link</th><th>Issued (UTC)</th><th></th></tr>";
    table.appendChild(thead);
    const body = document.createElement("tbody");
    for (const link of group.links) {
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
    table.appendChild(body);
    wrap.appendChild(table);
    section.appendChild(wrap);
    host.appendChild(section);
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
}

function appendManagedRow(parent, options) {
  const block = document.createElement("div");
  if (options.blockClass) block.className = options.blockClass;
  const row = document.createElement("div");
  row.className = "row";
  const field = document.createElement("label");
  field.className = "field grow";
  const span = document.createElement("span");
  span.textContent = options.label;
  const input = document.createElement("input");
  input.type = "text";
  input.value = options.name || "";
  field.appendChild(span);
  field.appendChild(input);
  const save = document.createElement("button");
  save.type = "button";
  save.textContent = "Save";
  save.addEventListener("click", () => {
    void options.onSave(input.value);
  });
  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "danger";
  remove.textContent = "Delete";
  const confirm = document.createElement("div");
  confirm.className = "confirm-row";
  confirm.hidden = true;
  const confirmField = document.createElement("label");
  confirmField.className = "field grow";
  const confirmSpan = document.createElement("span");
  confirmSpan.textContent = options.confirmLabel;
  const confirmInput = document.createElement("input");
  confirmInput.type = "text";
  confirmInput.value = "";
  confirmInput.setAttribute("autocomplete", "off");
  confirmField.appendChild(confirmSpan);
  confirmField.appendChild(confirmInput);
  const confirmButton = document.createElement("button");
  confirmButton.type = "button";
  confirmButton.className = "danger";
  confirmButton.textContent = "Confirm delete";
  confirmButton.addEventListener("click", () => {
    void options.onDelete(confirmInput.value);
  });
  confirm.appendChild(confirmField);
  confirm.appendChild(confirmButton);
  remove.addEventListener("click", () => {
    confirm.hidden = false;
    confirmInput.focus();
  });
  row.appendChild(field);
  row.appendChild(save);
  row.appendChild(remove);
  block.appendChild(row);
  block.appendChild(confirm);
  parent.appendChild(block);
}

async function runManagedAction(action) {
  try {
    setStatus($("clientsProjectsStatus"), "");
    await action();
  } catch (e) {
    setStatus($("clientsProjectsStatus"), String(e?.message || e));
  }
}

function renderClientsAndProjects() {
  const host = $("clientsProjectsList");
  const empty = $("clientsProjectsEmpty");
  host.innerHTML = "";
  const clients = state.clients;
  empty.style.display = clients.length ? "none" : "";
  for (const client of clients) {
    const section = document.createElement("section");
    section.className = "client-block";
    appendManagedRow(section, {
      label: "Client",
      name: client.name || "",
      confirmLabel: "Type the client name to delete",
      onSave: (name) =>
        runManagedAction(() => saveClientName(client.clientId, name)),
      onDelete: (confirmName) =>
        runManagedAction(() => deleteClientByName(client.clientId, confirmName)),
    });
    const projects = document.createElement("div");
    projects.className = "project-block";
    for (const project of client.projects || []) {
      appendManagedRow(projects, {
        label: "Project",
        name: project.name || "",
        confirmLabel: "Type the project name to delete",
        onSave: (name) =>
          runManagedAction(() => saveProjectName(project.projectId, name)),
        onDelete: (confirmName) =>
          runManagedAction(() => deleteProjectByName(project.projectId, confirmName)),
      });
    }
    section.appendChild(projects);
    host.appendChild(section);
  }
}

async function loadClientsAndProjects() {
  const rows = await jsonFetch(api("/commissioning/clients"));
  const clients = Array.isArray(rows) ? rows : [];
  const detailed = [];
  for (const client of clients) {
    const projects = await jsonFetch(
      api(`/commissioning/clients/${encodeURIComponent(client.clientId)}/projects`)
    );
    detailed.push({
      clientId: client.clientId,
      name: client.name || "",
      projects: Array.isArray(projects) ? projects : [],
    });
  }
  state.clients = detailed;
  renderClientsAndProjects();
}

async function saveClientName(clientId, name) {
  await jsonFetch(api(`/commissioning/clients/${encodeURIComponent(clientId)}`), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  await loadClientsAndProjects();
}

async function saveProjectName(projectId, name) {
  await jsonFetch(api(`/commissioning/projects/${encodeURIComponent(projectId)}`), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  await loadClientsAndProjects();
}

async function deleteClientByName(clientId, confirmName) {
  await jsonFetch(api(`/commissioning/clients/${encodeURIComponent(clientId)}`), {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirmName }),
  });
  await loadClientsAndProjects();
  await loadAllTechLinks();
}

async function deleteProjectByName(projectId, confirmName) {
  await jsonFetch(api(`/commissioning/projects/${encodeURIComponent(projectId)}`), {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirmName }),
  });
  await loadClientsAndProjects();
  await loadAllTechLinks();
}

async function run() {
  try {
    await loadAllTechLinks();
  } catch (e) {
    setStatus($("allTechLinkStatus"), String(e?.message || e));
  }
  try {
    await loadClientsAndProjects();
  } catch (e) {
    setStatus($("clientsProjectsStatus"), String(e?.message || e));
  }
}

run();
