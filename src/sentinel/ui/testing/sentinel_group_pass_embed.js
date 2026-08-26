/**
 * Technician group-pass chrome (project home + device pages).
 * Injected with test-status embed; pages call globalThis.__sentinelGroupPass.attach(...).
 *
 * Grouping model: an ephemeral session set of targetKeys. Fill it by tapping controls,
 * shift-click, rubber-band drag on a device page, and/or structural shortcuts
 * (this page / this device / system events / driver events), then Pass group in one
 * WebSocket batch. Not persisted. Fail stays per-target.
 */
(function (global) {
  "use strict";

  const CONFIRM_AT = 25;
  const DRAG_THRESHOLD_PX = 8;
  const STYLE_ID = "sentinel-group-pass-style";
  const BAR_ID = "sentinelGroupBar";
  const MARQUEE_ID = "sentinelGroupMarquee";

  const CSS = [
    "body{padding-bottom:84px;}",
    "#" + BAR_ID + "{position:fixed;left:12px;right:12px;bottom:12px;z-index:9500;display:flex;flex-wrap:wrap;align-items:center;gap:8px;box-sizing:border-box;padding:10px 12px;border:1px solid #b9cad8;border-radius:16px;background:rgba(247,251,255,.96);box-shadow:0 10px 30px rgba(20,50,75,.16);font-family:Segoe UI,Tahoma,sans-serif;color:#14324b;}",
    "#" + BAR_ID + " button{border:1px solid #a9bccd;background:#f7fbff;border-radius:10px;padding:8px 14px;font-size:13px;line-height:1.1;cursor:pointer;color:#14324b;}",
    "#" + BAR_ID + " button:disabled{opacity:.55;cursor:not-allowed;}",
    "#" + BAR_ID + " button.is-active{background:#29445a;color:#fff;border-color:#29445a;font-weight:700;}",
    "#" + BAR_ID + " button.group-pass{background:#eaf7ef;border-color:#39b54a;color:#1f5d2d;font-weight:700;}",
    "#" + BAR_ID + " .group-count{font-size:13px;font-weight:700;margin-left:auto;}",
    "#" + BAR_ID + " .group-status{width:100%;font-size:12px;line-height:1.25;color:#274258;}",
    "#" + BAR_ID + " .group-status.is-error{color:#8f1f1f;}",
    "body.sentinel-group-mode .btn-wrap.is-group-selected{outline:3px solid #7c3aed;outline-offset:2px;}",
    "#" + MARQUEE_ID + "{position:fixed;z-index:9400;pointer-events:none;box-sizing:border-box;border:1px dashed #7c3aed;background:rgba(124,58,237,.12);}",
    "body.sentinel-group-dragging{user-select:none;}",
  ].join("\n");

  const selected = new Map();
  let groupMode = false;
  let posting = false;
  let opts = null;
  let bar = null;
  let drag = null;
  let swallowClick = false;
  let dragListenersBound = false;

  function injectStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const el = document.createElement("style");
    el.id = STYLE_ID;
    el.textContent = CSS;
    document.head.appendChild(el);
  }

  function payloadsForButton(btn) {
    if (!opts || typeof opts.buildTargetPayload !== "function" || !btn) return [];
    let meta = {};
    try {
      meta = JSON.parse(btn.getAttribute("data-meta") || "{}");
    } catch (_e) {
      meta = {};
    }
    const labels = Array.isArray(meta.targets) ? meta.targets : [];
    const out = [];
    for (let i = 0; i < labels.length; i += 1) {
      const t = opts.buildTargetPayload(btn, meta, labels[i]);
      if (t && t.targetKey) out.push(t);
    }
    return out;
  }

  function wrapForButton(btn) {
    return btn && btn.closest ? btn.closest(".btn-wrap") : null;
  }

  function wrapHasSelected(wrap) {
    if (!wrap) return false;
    const btn = wrap.querySelector(".test-btn");
    const payloads = payloadsForButton(btn);
    for (let i = 0; i < payloads.length; i += 1) {
      if (selected.has(String(payloads[i].targetKey))) return true;
    }
    return false;
  }

  function refreshWrapSelection(root) {
    const scope = root || document;
    scope.querySelectorAll(".btn-wrap").forEach(function (wrap) {
      wrap.classList.toggle("is-group-selected", groupMode && wrapHasSelected(wrap));
    });
  }

  function setStatus(text, isError) {
    if (!bar) return;
    const el = bar.querySelector(".group-status");
    if (!el) return;
    const t = String(text || "").trim();
    el.textContent = t;
    el.classList.toggle("is-error", !!isError && !!t);
    if (t) el.removeAttribute("hidden");
    else el.setAttribute("hidden", "hidden");
  }

  function syncTogglePressed() {
    if (!bar) return;
    const toggle = bar.querySelector("#sentinelGroupToggle");
    if (toggle) toggle.setAttribute("aria-pressed", groupMode ? "true" : "false");
  }

  function updateChrome() {
    if (!bar) return;
    const n = selected.size;
    const toggle = bar.querySelector("#sentinelGroupToggle");
    const tools = bar.querySelector("#sentinelGroupTools");
    const count = bar.querySelector(".group-count");
    const passBtn = bar.querySelector("#sentinelGroupPass");
    if (toggle) toggle.classList.toggle("is-active", groupMode);
    if (tools) tools.hidden = !groupMode;
    if (count) count.textContent = n === 1 ? "1 target" : n + " targets";
    if (passBtn) passBtn.disabled = posting || n < 1;
    bar.querySelectorAll("button").forEach(function (btn) {
      if (btn.id === "sentinelGroupToggle") return;
      if (btn.id === "sentinelGroupPass") {
        btn.disabled = posting || n < 1;
        return;
      }
      btn.disabled = posting || !groupMode;
    });
    document.body.classList.toggle("sentinel-group-mode", groupMode);
    refreshWrapSelection(document);
  }

  function setGroupMode(on) {
    groupMode = !!on;
    if (!groupMode) {
      posting = false;
    }
    setStatus("", false);
    syncTogglePressed();
    updateChrome();
  }

  function enterGroupMode() {
    if (groupMode) return;
    setGroupMode(true);
  }

  function addPayloads(payloads) {
    let added = 0;
    for (let i = 0; i < payloads.length; i += 1) {
      const t = payloads[i];
      const key = String(t && t.targetKey ? t.targetKey : "").trim();
      if (!key || selected.has(key)) continue;
      selected.set(key, t);
      added += 1;
    }
    return added;
  }

  function removePayloads(payloads) {
    for (let i = 0; i < payloads.length; i += 1) {
      const key = String(payloads[i] && payloads[i].targetKey ? payloads[i].targetKey : "").trim();
      if (key) selected.delete(key);
    }
  }

  function toggleButton(btn) {
    const payloads = payloadsForButton(btn);
    if (!payloads.length) return;
    let allIn = true;
    for (let i = 0; i < payloads.length; i += 1) {
      if (!selected.has(String(payloads[i].targetKey))) {
        allIn = false;
        break;
      }
    }
    if (allIn) removePayloads(payloads);
    else addPayloads(payloads);
    updateChrome();
  }

  function buttonsInRoot(root) {
    if (!root || !root.querySelectorAll) return [];
    return Array.prototype.slice.call(root.querySelectorAll(".test-btn"));
  }

  function addButtons(btns, label) {
    let n = 0;
    for (let i = 0; i < btns.length; i += 1) {
      n += addPayloads(payloadsForButton(btns[i]));
    }
    setStatus(n ? "Added " + n + " from " + label + "." : "No new targets in " + label + ".", false);
    updateChrome();
  }

  function addThisPage() {
    if (typeof opts.materializeActivePage === "function") opts.materializeActivePage();
    const root = typeof opts.activePageRoot === "function" ? opts.activePageRoot() : null;
    addButtons(buttonsInRoot(root), "this page");
  }

  function addThisDevice() {
    if (typeof opts.materializeAllPages === "function") opts.materializeAllPages();
    addButtons(buttonsInRoot(document.querySelector("#rtiDeviceCanvas") || document), "this device");
  }

  function addSection(id, label) {
    addButtons(buttonsInRoot(document.getElementById(id)), label);
  }

  function clearGroup() {
    selected.clear();
    setStatus("", false);
    updateChrome();
  }

  function passGroup() {
    if (posting || !opts || typeof opts.sendWs !== "function") return;
    const targets = [];
    selected.forEach(function (t) {
      targets.push({
        targetKey: t.targetKey,
        kind: t.kind,
        refs: t.refs && typeof t.refs === "object" ? t.refs : {},
        targetName: t.targetName,
      });
    });
    if (!targets.length) return;
    if (targets.length >= CONFIRM_AT && typeof global.confirm === "function") {
      if (!global.confirm("Pass " + targets.length + " targets?")) return;
    }
    posting = true;
    if (typeof opts.setPendingBatch === "function") opts.setPendingBatch(true);
    if (typeof opts.onPostingChange === "function") opts.onPostingChange(true);
    setStatus("Passing " + targets.length + " targets…", false);
    updateChrome();
    opts.sendWs({
      type: "test_result.submit_batch",
      outcome: "PASS",
      targets: targets,
    });
  }

  function onBatchAck(ok, message) {
    posting = false;
    if (typeof opts.setPendingBatch === "function") opts.setPendingBatch(false);
    if (ok) {
      selected.clear();
      setStatus("Group passed.", false);
      if (typeof opts.refreshVisuals === "function") opts.refreshVisuals();
    } else {
      setStatus(String(message || "Group pass failed."), true);
    }
    updateChrome();
  }

  function handleTestButtonClick(btn, evt) {
    const shift = !!(evt && evt.shiftKey);
    if (!groupMode && !shift) return false;
    if (evt && typeof evt.preventDefault === "function") evt.preventDefault();
    if (evt && typeof evt.stopPropagation === "function") evt.stopPropagation();
    if (shift) enterGroupMode();
    toggleButton(btn);
    return true;
  }

  function overlayOpen() {
    const ov = document.getElementById("ov");
    return !!(ov && ov.classList && ov.classList.contains("open"));
  }

  function isChromeTarget(el) {
    if (!el || !el.closest) return true;
    if (el.closest("#" + BAR_ID)) return true;
    if (el.closest("#" + MARQUEE_ID)) return true;
    if (el.closest("#ov")) return true;
    if (el.closest("#rtiDeviceCanvas") || el.closest("#rtiCanvas") || el.closest(".device-page")) return false;
    return true;
  }

  function pageRoot() {
    if (opts && typeof opts.activePageRoot === "function") {
      const root = opts.activePageRoot();
      if (root) return root;
    }
    return document.querySelector("#rtiDeviceCanvas") || document;
  }

  function marqueeEl() {
    let el = document.getElementById(MARQUEE_ID);
    if (el) return el;
    el = document.createElement("div");
    el.id = MARQUEE_ID;
    el.hidden = true;
    document.body.appendChild(el);
    return el;
  }

  function rectFromPoints(a, b) {
    const left = Math.min(a.x, b.x);
    const top = Math.min(a.y, b.y);
    return { left: left, top: top, width: Math.abs(a.x - b.x), height: Math.abs(a.y - b.y) };
  }

  function paintMarquee(rect) {
    const el = marqueeEl();
    el.hidden = false;
    el.style.left = rect.left + "px";
    el.style.top = rect.top + "px";
    el.style.width = rect.width + "px";
    el.style.height = rect.height + "px";
  }

  function hideMarquee() {
    const el = document.getElementById(MARQUEE_ID);
    if (el) el.hidden = true;
  }

  function wrapsIntersecting(rect) {
    const root = pageRoot();
    const wraps = root.querySelectorAll ? root.querySelectorAll(".btn-wrap") : [];
    const hit = [];
    for (let i = 0; i < wraps.length; i += 1) {
      const box = wraps[i].getBoundingClientRect();
      if (box.width <= 0 || box.height <= 0) continue;
      const overlap = !(
        box.right < rect.left ||
        box.left > rect.left + rect.width ||
        box.bottom < rect.top ||
        box.top > rect.top + rect.height
      );
      if (overlap) hit.push(wraps[i]);
    }
    return hit;
  }

  function addWraps(wraps) {
    let n = 0;
    for (let i = 0; i < wraps.length; i += 1) {
      const btn = wraps[i].querySelector(".test-btn");
      if (btn) n += addPayloads(payloadsForButton(btn));
    }
    return n;
  }

  function endDrag() {
    document.body.classList.remove("sentinel-group-dragging");
    hideMarquee();
    drag = null;
  }

  function onPointerDown(e) {
    if (!opts || opts.surface !== "device") return;
    if (e.pointerType === "mouse" && e.button !== 0) return;
    if (e.shiftKey || posting || overlayOpen()) return;
    if (isChromeTarget(e.target)) return;
    drag = { x0: e.clientX, y0: e.clientY, active: false };
  }

  function onPointerMove(e) {
    if (!drag) return;
    const dx = e.clientX - drag.x0;
    const dy = e.clientY - drag.y0;
    if (!drag.active) {
      if (Math.abs(dx) < DRAG_THRESHOLD_PX && Math.abs(dy) < DRAG_THRESHOLD_PX) return;
      drag.active = true;
      document.body.classList.add("sentinel-group-dragging");
      enterGroupMode();
    }
    if (e.cancelable && typeof e.preventDefault === "function") e.preventDefault();
    paintMarquee(rectFromPoints({ x: drag.x0, y: drag.y0 }, { x: e.clientX, y: e.clientY }));
  }

  function onPointerUp(e) {
    if (!drag) return;
    const wasActive = drag.active;
    const start = { x: drag.x0, y: drag.y0 };
    endDrag();
    if (!wasActive) return;
    swallowClick = true;
    if (e && e.cancelable && typeof e.preventDefault === "function") e.preventDefault();
    const rect = rectFromPoints(start, { x: e.clientX, y: e.clientY });
    const n = addWraps(wrapsIntersecting(rect));
    setStatus(n ? "Added " + n + " from selection." : "No new targets in that region.", false);
    updateChrome();
  }

  function onSwallowClick(e) {
    if (!swallowClick) return;
    swallowClick = false;
    if (typeof e.preventDefault === "function") e.preventDefault();
    if (typeof e.stopPropagation === "function") e.stopPropagation();
  }

  function bindDragSelect() {
    if (dragListenersBound) return;
    dragListenersBound = true;
    document.addEventListener("pointerdown", onPointerDown, true);
    document.addEventListener("pointermove", onPointerMove, true);
    document.addEventListener("pointerup", onPointerUp, true);
    document.addEventListener("pointercancel", onPointerUp, true);
    document.addEventListener("click", onSwallowClick, true);
  }

  function mountBar() {
    if (document.getElementById(BAR_ID)) {
      bar = document.getElementById(BAR_ID);
      return;
    }
    bar = document.createElement("div");
    bar.id = BAR_ID;
    bar.innerHTML =
      '<button type="button" id="sentinelGroupToggle" aria-pressed="false">Group</button>' +
      '<div id="sentinelGroupTools" hidden>' +
      '<button type="button" id="sentinelGroupAddPage" data-surface="device">Add this page</button>' +
      '<button type="button" id="sentinelGroupAddDevice" data-surface="device">Add this device</button>' +
      '<button type="button" id="sentinelGroupAddSystem" data-surface="home">Add system events</button>' +
      '<button type="button" id="sentinelGroupAddDriver" data-surface="home">Add driver events</button>' +
      '<span class="group-count">0 targets</span>' +
      '<button type="button" id="sentinelGroupPass" class="group-pass" disabled>Pass group</button>' +
      '<button type="button" id="sentinelGroupClear">Clear</button>' +
      '<button type="button" id="sentinelGroupDone">Done</button>' +
      "</div>" +
      '<div class="group-status" hidden></div>';
    document.body.appendChild(bar);
    const surface = opts && opts.surface === "home" ? "home" : "device";
    bar.querySelectorAll("[data-surface]").forEach(function (el) {
      el.hidden = el.getAttribute("data-surface") !== surface;
    });
    bar.querySelector("#sentinelGroupToggle").addEventListener("click", function () {
      setGroupMode(!groupMode);
    });
    bar.querySelector("#sentinelGroupAddPage").addEventListener("click", addThisPage);
    bar.querySelector("#sentinelGroupAddDevice").addEventListener("click", addThisDevice);
    bar.querySelector("#sentinelGroupAddSystem").addEventListener("click", function () {
      addSection("system-events", "system events");
    });
    bar.querySelector("#sentinelGroupAddDriver").addEventListener("click", function () {
      addSection("driver-events", "driver events");
    });
    bar.querySelector("#sentinelGroupPass").addEventListener("click", passGroup);
    bar.querySelector("#sentinelGroupClear").addEventListener("click", clearGroup);
    bar.querySelector("#sentinelGroupDone").addEventListener("click", function () {
      setGroupMode(false);
    });
  }

  function attach(nextOpts) {
    opts = nextOpts && typeof nextOpts === "object" ? nextOpts : {};
    injectStyle();
    mountBar();
    bindDragSelect();
    updateChrome();
  }

  global.__sentinelGroupPass = {
    attach: attach,
    handleTestButtonClick: handleTestButtonClick,
    onBatchAck: onBatchAck,
    isGroupMode: function () {
      return groupMode;
    },
    selectedCount: function () {
      return selected.size;
    },
  };
})(typeof globalThis !== "undefined" ? globalThis : window);
