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

async function run() {
  try {
    await loadAllTechLinks();
  } catch (e) {
    setStatus($("allTechLinkStatus"), String(e?.message || e));
  }
}

run();
