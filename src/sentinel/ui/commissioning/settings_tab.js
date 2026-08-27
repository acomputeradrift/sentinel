function settingsApi(path) {
  if (typeof api === "function") return api(path);
  return `/api/v1${path}`;
}

function settingsProjectId() {
  if (typeof currentProjectId === "function") return currentProjectId();
  const sel = document.getElementById("projectSelect");
  return sel ? String(sel.value || "").trim() : "";
}

function isSettingsVisible() {
  const panel = document.getElementById("panel-settings");
  return !!panel && !panel.hidden;
}

function setSettingsStatus(msg) {
  const el = document.getElementById("settingsTypeStatus");
  if (el) el.textContent = msg || "";
}

function familyTitle(family) {
  if (family === "event") return "Event";
  return "Button / control";
}

function renderTestingTypeSettings(payload) {
  const host = document.getElementById("settingsTypeGroups");
  if (!host) return;
  const types = Array.isArray(payload?.types) ? payload.types : [];
  const graphicsIds = new Set(
    (Array.isArray(payload?.graphicsTypeIds) ? payload.graphicsTypeIds : []).map((id) => String(id))
  );
  const byFamily = { button: [], event: [] };
  types.forEach((row) => {
    const family = String(row?.family || "button");
    if (!byFamily[family]) byFamily[family] = [];
    byFamily[family].push(row);
  });

  function checkboxRow(row, extraClass) {
    const id = String(row.id || "");
    const enabled = row.enabled !== false;
    const label = String(row.label || id);
    return (
      '<label class="settings-type-row ' +
      (extraClass || "") +
      '">' +
      '<input type="checkbox" data-testid="settings-type-' +
      id.replace(/[^a-zA-Z0-9_-]/g, "-") +
      '" data-type-id="' +
      id +
      '"' +
      (enabled ? " checked" : "") +
      " />" +
      "<span>" +
      label +
      "</span></label>"
    );
  }

  const graphicsRows = types.filter((row) => graphicsIds.has(String(row.id || "")));
  const graphicsOn = graphicsRows.length ? graphicsRows.every((row) => row.enabled !== false) : true;
  let html = "";
  html += '<div class="settings-type-group" data-family="graphics">';
  html += "<h3>Graphics</h3>";
  html +=
    '<p class="sub">Icons and bitmaps still draw when off; they are not required testing work.</p>';
  html +=
    '<label class="settings-type-row settings-family-row"><input type="checkbox" data-testid="settings-graphics-family" data-family-toggle="graphics"' +
    (graphicsOn ? " checked" : "") +
    " /><span>Require graphics (Bitmap, Icon, Variable - Image)</span></label>";
  html += '<div class="settings-type-list">';
  graphicsRows.forEach((row) => {
    html += checkboxRow(row, "");
  });
  html += "</div></div>";

  ["button", "event"].forEach((family) => {
    const rows = (byFamily[family] || []).filter((row) => {
      if (family !== "button") return true;
      return !graphicsIds.has(String(row.id || ""));
    });
    if (!rows.length) return;
    html += '<div class="settings-type-group" data-family="' + family + '">';
    html += "<h3>" + familyTitle(family) + "</h3>";
    html += '<div class="settings-type-list">';
    rows.forEach((row) => {
      html += checkboxRow(row, "");
    });
    html += "</div></div>";
  });
  host.innerHTML = html;
}

function collectDisabledFromUi() {
  const host = document.getElementById("settingsTypeGroups");
  if (!host) return [];
  const out = [];
  host.querySelectorAll('input[type="checkbox"][data-type-id]').forEach((el) => {
    if (el.checked) return;
    const id = String(el.getAttribute("data-type-id") || "").trim();
    if (id) out.push(id);
  });
  return out;
}

function syncGraphicsFamilyToggle() {
  const host = document.getElementById("settingsTypeGroups");
  if (!host) return;
  const family = host.querySelector('input[data-family-toggle="graphics"]');
  if (!family) return;
  const boxes = Array.from(host.querySelectorAll('input[data-type-id]')).filter((el) => {
    const id = String(el.getAttribute("data-type-id") || "");
    return id === "button:Bitmap" || id === "button:Icon" || id === "button:Variable - Image";
  });
  family.checked = boxes.length > 0 && boxes.every((el) => el.checked);
}

async function saveTestingTypeSettings() {
  const projectId = settingsProjectId();
  if (!projectId) return;
  const disabledTypes = collectDisabledFromUi();
  setSettingsStatus("Saving…");
  try {
    const fetchJson = typeof jsonFetch === "function" ? jsonFetch : null;
    if (!fetchJson) throw new Error("jsonFetch missing");
    const out = await fetchJson(settingsApi(`/commissioning/projects/${encodeURIComponent(projectId)}/testing-types`), {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ disabledTypes }),
    });
    renderTestingTypeSettings(out);
    bindSettingsHandlers();
    setSettingsStatus("");
  } catch (e) {
    setSettingsStatus(String(e && e.message ? e.message : e || "Save failed"));
  }
}

function bindSettingsHandlers() {
  const host = document.getElementById("settingsTypeGroups");
  if (!host) return;
  host.querySelectorAll('input[type="checkbox"][data-type-id]').forEach((el) => {
    el.addEventListener("change", () => {
      syncGraphicsFamilyToggle();
      void saveTestingTypeSettings();
    });
  });
  const family = host.querySelector('input[data-family-toggle="graphics"]');
  if (family) {
    family.addEventListener("change", () => {
      const on = !!family.checked;
      host.querySelectorAll('input[data-type-id]').forEach((el) => {
        const id = String(el.getAttribute("data-type-id") || "");
        if (id === "button:Bitmap" || id === "button:Icon" || id === "button:Variable - Image") {
          el.checked = on;
        }
      });
      void saveTestingTypeSettings();
    });
  }
}

async function loadTestingTypeSettings() {
  const projectId = settingsProjectId();
  const body = document.getElementById("settingsPanelBody");
  if (body) body.hidden = !projectId;
  const hint = document.getElementById("settingsHintNoProject");
  if (hint) hint.hidden = !!projectId;
  if (!projectId) {
    const host = document.getElementById("settingsTypeGroups");
    if (host) host.innerHTML = "";
    setSettingsStatus("");
    return;
  }
  try {
    const fetchJson = typeof jsonFetch === "function" ? jsonFetch : null;
    if (!fetchJson) throw new Error("jsonFetch missing");
    const out = await fetchJson(settingsApi(`/commissioning/projects/${encodeURIComponent(projectId)}/testing-types`));
    renderTestingTypeSettings(out);
    bindSettingsHandlers();
    setSettingsStatus("");
  } catch (e) {
    setSettingsStatus(String(e && e.message ? e.message : e || "Load failed"));
  }
}

window.__sentinelLoadTestingTypeSettings = loadTestingTypeSettings;

(function bindSettingsProjectChange() {
  const projectSelect = document.getElementById("projectSelect");
  if (!projectSelect) return;
  projectSelect.addEventListener("change", () => {
    if (!isSettingsVisible()) return;
    void loadTestingTypeSettings();
  });
})();
