/**
 * Technician group-pass chrome (project home + device pages).
 * Injected with test-status embed; pages call globalThis.__sentinelGroupPass.attach(...).
 *
 * Grouping model: an ephemeral session set of targetKeys. Fill it by tapping Select
 * (iPad) then tapping controls / a viewport / rubber-band dragging, or via desktop
 * shift-click / shift-drag, then Pass group in one WebSocket batch. Not persisted.
 * Fail stays per-target.
 */
(function (global) {
  "use strict";

  const CONFIRM_AT = 25;
  const DRAG_THRESHOLD_PX = 8;
  const STYLE_ID = "sentinel-group-pass-style";
  const TOGGLE_ID = "sentinelGroupToggle";
  const ACTIONS_ID = "sentinelGroupActions";
  const MARQUEE_ID = "sentinelGroupMarquee";
  const CLUSTER_ID = "sentinelGroupToggleCluster";

  const CSS = [
    "#" + TOGGLE_ID + "{display:inline-flex;align-items:center;justify-content:center;min-width:96px;height:40px;padding:0 16px;border-radius:14px;border:2px solid #f0a126;background:transparent;color:#29445a;font-size:14px;font-weight:700;cursor:pointer;box-sizing:border-box;white-space:nowrap;flex-shrink:0;font-family:Segoe UI,Tahoma,sans-serif;}",
    "#" + TOGGLE_ID + ".is-active{background:#29445a;color:#fff;border-color:#29445a;}",
    "#" + CLUSTER_ID + "{display:inline-flex;align-items:center;gap:8px;flex-shrink:0;}",
    ".home-header{position:relative;padding-right:140px;box-sizing:border-box;}",
    ".home-header #" + TOGGLE_ID + "{position:absolute;top:24px;right:28px;}",
    "#" + ACTIONS_ID + "{position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);z-index:9500;display:flex;flex-direction:column;gap:8px;box-sizing:border-box;min-width:220px;max-width:min(360px,calc(100vw - 24px));max-height:min(50vh,420px);overflow:auto;padding:12px;border:1px solid #b9cad8;border-radius:16px;background:rgba(247,251,255,.98);box-shadow:0 10px 30px rgba(20,50,75,.16);font-family:Segoe UI,Tahoma,sans-serif;color:#14324b;}",
    "#" + ACTIONS_ID + "[hidden]{display:none !important;}",
    "#" + ACTIONS_ID + " button{border:1px solid #a9bccd;background:#f7fbff;border-radius:12px;min-height:44px;padding:10px 14px;font-size:15px;line-height:1.1;cursor:pointer;color:#14324b;width:100%;}",
    "#" + ACTIONS_ID + " button:disabled{opacity:.55;cursor:not-allowed;}",
    "#" + ACTIONS_ID + " button.group-pass{background:#eaf7ef;border-color:#39b54a;color:#1f5d2d;font-weight:700;}",
    "#" + ACTIONS_ID + " .group-count{font-size:13px;font-weight:700;}",
    "#" + ACTIONS_ID + " .group-status{width:100%;font-size:12px;line-height:1.25;color:#274258;}",
    "#" + ACTIONS_ID + " .group-status.is-error{color:#8f1f1f;}",
    "body.sentinel-group-mode .btn-wrap.is-group-selected{outline:3px solid #7c3aed;outline-offset:2px;}",
    "body.sentinel-group-mode #rtiCanvas,body.sentinel-group-mode #rtiDeviceCanvas,body.sentinel-group-mode .device-page{touch-action:none;}",
    "#" + MARQUEE_ID + "{position:fixed;z-index:9400;pointer-events:none;box-sizing:border-box;border:1px dashed #7c3aed;background:rgba(124,58,237,.12);}",
    "body.sentinel-group-dragging{user-select:none;}",
  ].join("\n");

  const selected = new Map();
  let groupMode = false;
  let posting = false;
  let opts = null;
  let toggle = null;
  let actions = null;
  let drag = null;
  let swallowClick = false;
  let dragListenersBound = false;
  let hideActionsWhileDragging = false;

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
    const filter =
      global.__sentinelTestStatus && typeof global.__sentinelTestStatus.filterWorkTargets === "function"
        ? global.__sentinelTestStatus.filterWorkTargets
        : null;
    const workLabels = filter ? filter(meta) : labels;
    const out = [];
    for (let i = 0; i < workLabels.length; i += 1) {
      const t = opts.buildTargetPayload(btn, meta, workLabels[i]);
      if (t && t.targetKey) out.push(t);
    }
    return out;
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

  function statusText() {
    if (!actions) return "";
    const el = actions.querySelector(".group-status");
    return el ? String(el.textContent || "").trim() : "";
  }

  function setStatus(text, isError) {
    if (!actions) return;
    const el = actions.querySelector(".group-status");
    if (!el) return;
    const t = String(text || "").trim();
    el.textContent = t;
    el.classList.toggle("is-error", !!isError && !!t);
    if (t) el.removeAttribute("hidden");
    else el.setAttribute("hidden", "hidden");
  }

  function syncTogglePressed() {
    if (!toggle) return;
    toggle.setAttribute("aria-pressed", groupMode ? "true" : "false");
    toggle.classList.toggle("is-active", groupMode);
  }

  function actionsShouldShow() {
    if (!groupMode || hideActionsWhileDragging) return false;
    if (posting) return true;
    if (selected.size > 0) return true;
    return !!statusText();
  }

  function positionActions() {
    if (!actions || actions.hidden) return;
    actions.style.top = "50%";
    actions.style.left = "50%";
    actions.style.transform = "translate(-50%, -50%)";
  }

  function updateChrome() {
    const n = selected.size;
    if (toggle) toggle.classList.toggle("is-active", groupMode);
    if (actions) {
      const count = actions.querySelector(".group-count");
      const passBtn = actions.querySelector("#sentinelGroupPass");
      if (count) count.textContent = n === 1 ? "1 target" : n + " targets";
      const show = actionsShouldShow();
      actions.hidden = !show;
      actions.querySelectorAll("button").forEach(function (btn) {
        if (btn.id === "sentinelGroupPass") {
          btn.disabled = posting || n < 1;
          return;
        }
        if (btn.id === "sentinelGroupDone") {
          btn.disabled = posting;
          return;
        }
        btn.disabled = posting || !groupMode;
      });
      if (passBtn) passBtn.disabled = posting || n < 1;
      if (show) positionActions();
    }
    document.body.classList.toggle("sentinel-group-mode", groupMode);
    refreshWrapSelection(document);
  }

  function setGroupMode(on) {
    groupMode = !!on;
    if (!groupMode) {
      posting = false;
      hideActionsWhileDragging = false;
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
    if (el.closest("#" + TOGGLE_ID)) return true;
    if (el.closest("#" + CLUSTER_ID)) return true;
    if (el.closest("#" + ACTIONS_ID)) return true;
    if (el.closest("#" + MARQUEE_ID)) return true;
    if (el.closest("#ov")) return true;
    if (el.closest("#topControls") || el.closest("#zoomControls") || el.closest("#orientationControls")) return true;
    if (el.closest("#layerControls") || el.closest("#vpPopup")) return true;
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

  function wrapsForViewport(vpIndex) {
    const root = pageRoot();
    const wraps = root.querySelectorAll ? root.querySelectorAll(".btn-wrap") : [];
    const hit = [];
    const want = String(vpIndex);
    for (let i = 0; i < wraps.length; i += 1) {
      if (String(wraps[i].getAttribute("data-vp") || "") === want) hit.push(wraps[i]);
    }
    return hit;
  }

  function handleViewportBoxClick(box, evt) {
    const shift = !!(evt && evt.shiftKey);
    if (!groupMode && !shift) return false;
    if (evt && typeof evt.preventDefault === "function") evt.preventDefault();
    if (evt && typeof evt.stopPropagation === "function") evt.stopPropagation();
    if (shift) enterGroupMode();
    const n = addWraps(wrapsForViewport(box && box.getAttribute ? box.getAttribute("data-vp") : ""));
    setStatus(n ? "Added " + n + " from viewport." : "No new targets in that viewport.", false);
    updateChrome();
    return true;
  }

  function endDrag() {
    document.body.classList.remove("sentinel-group-dragging");
    hideMarquee();
    hideActionsWhileDragging = false;
    drag = null;
  }

  function onPointerDown(e) {
    if (!opts || opts.surface !== "device") return;
    if (e.pointerType === "mouse" && e.button !== 0) return;
    if (posting || overlayOpen()) return;
    if (isChromeTarget(e.target)) return;
    if (drag) return;
    const shift = !!e.shiftKey;
    if (!groupMode && !shift) return;
    if (shift) enterGroupMode();
    drag = { x0: e.clientX, y0: e.clientY, active: false, pointerId: e.pointerId };
  }

  function onPointerMove(e) {
    if (!drag) return;
    if (drag.pointerId != null && e.pointerId != null && e.pointerId !== drag.pointerId) {
      if (e.cancelable && typeof e.preventDefault === "function") e.preventDefault();
      return;
    }
    const dx = e.clientX - drag.x0;
    const dy = e.clientY - drag.y0;
    if (!drag.active) {
      if (Math.abs(dx) < DRAG_THRESHOLD_PX && Math.abs(dy) < DRAG_THRESHOLD_PX) return;
      drag.active = true;
      hideActionsWhileDragging = true;
      document.body.classList.add("sentinel-group-dragging");
      enterGroupMode();
      updateChrome();
    }
    if (e.cancelable && typeof e.preventDefault === "function") e.preventDefault();
    paintMarquee(rectFromPoints({ x: drag.x0, y: drag.y0 }, { x: e.clientX, y: e.clientY }));
  }

  function onPointerUp(e) {
    if (!drag) return;
    if (drag.pointerId != null && e.pointerId != null && e.pointerId !== drag.pointerId) return;
    const wasActive = drag.active;
    const start = { x: drag.x0, y: drag.y0 };
    endDrag();
    if (!wasActive) {
      updateChrome();
      return;
    }
    swallowClick = true;
    if (e && e.cancelable && typeof e.preventDefault === "function") e.preventDefault();
    const rect = rectFromPoints(start, { x: e.clientX, y: e.clientY });
    const n = addWraps(wrapsIntersecting(rect));
    setStatus(n ? "Added " + n + " from selection." : "No new targets in that region.", false);
    updateChrome();
  }

  function onSwallowClick(e) {
    if (swallowClick) {
      swallowClick = false;
      if (typeof e.preventDefault === "function") e.preventDefault();
      if (typeof e.stopPropagation === "function") e.stopPropagation();
      return;
    }
    const box = e.target && e.target.closest ? e.target.closest(".vp-box") : null;
    if (!box) return;
    if (handleViewportBoxClick(box, e)) return;
  }

  function onGesturePrevent(e) {
    if (!groupMode) return;
    if (!opts || opts.surface !== "device") return;
    if (isChromeTarget(e.target)) return;
    if (e && e.cancelable && typeof e.preventDefault === "function") e.preventDefault();
  }

  function bindDragSelect() {
    if (dragListenersBound) return;
    dragListenersBound = true;
    const cap = { capture: true, passive: false };
    document.addEventListener("pointerdown", onPointerDown, cap);
    document.addEventListener("pointermove", onPointerMove, cap);
    document.addEventListener("pointerup", onPointerUp, cap);
    document.addEventListener("pointercancel", onPointerUp, cap);
    document.addEventListener("click", onSwallowClick, true);
    document.addEventListener("touchmove", onGesturePrevent, cap);
    document.addEventListener("gesturestart", onGesturePrevent, cap);
    document.addEventListener("gesturechange", onGesturePrevent, cap);
    window.addEventListener("resize", function () {
      if (actions && !actions.hidden) positionActions();
    });
  }

  function mountToggle() {
    const existing = document.getElementById(TOGGLE_ID);
    if (existing) {
      toggle = existing;
      return;
    }
    toggle = document.createElement("button");
    toggle.type = "button";
    toggle.id = TOGGLE_ID;
    toggle.textContent = "Select";
    toggle.setAttribute("aria-pressed", "false");
    toggle.setAttribute("aria-label", "Select targets");
    const top = document.getElementById("topControls");
    if (top) {
      let cluster = document.getElementById(CLUSTER_ID);
      if (!cluster) {
        cluster = document.createElement("div");
        cluster.id = CLUSTER_ID;
        const home = top.querySelector(".project-home-link");
        if (home && home.parentNode) {
          home.parentNode.insertBefore(cluster, home);
          cluster.appendChild(home);
        } else {
          top.insertBefore(cluster, top.firstChild);
        }
      }
      cluster.appendChild(toggle);
    } else {
      const header = document.querySelector(".home-header");
      if (header) header.appendChild(toggle);
      else document.body.appendChild(toggle);
    }
    toggle.addEventListener("click", function () {
      setGroupMode(!groupMode);
    });
  }

  function mountActions() {
    const existing = document.getElementById(ACTIONS_ID);
    if (existing) {
      actions = existing;
      return;
    }
    actions = document.createElement("div");
    actions.id = ACTIONS_ID;
    actions.hidden = true;
    actions.setAttribute("role", "dialog");
    actions.setAttribute("aria-label", "Group actions");
    actions.innerHTML =
      '<div class="group-count">0 targets</div>' +
      '<button type="button" id="sentinelGroupPass" class="group-pass" disabled>Pass group</button>' +
      '<button type="button" id="sentinelGroupAddPage" data-surface="device">Add this page</button>' +
      '<button type="button" id="sentinelGroupAddDevice" data-surface="device">Add this device</button>' +
      '<button type="button" id="sentinelGroupAddSystem" data-surface="home">Add system events</button>' +
      '<button type="button" id="sentinelGroupAddDriver" data-surface="home">Add driver events</button>' +
      '<button type="button" id="sentinelGroupClear">Clear</button>' +
      '<button type="button" id="sentinelGroupDone">Done</button>' +
      '<div class="group-status" hidden></div>';
    document.body.appendChild(actions);
    const surface = opts && opts.surface === "home" ? "home" : "device";
    actions.querySelectorAll("[data-surface]").forEach(function (el) {
      el.hidden = el.getAttribute("data-surface") !== surface;
    });
    actions.querySelector("#sentinelGroupAddPage").addEventListener("click", addThisPage);
    actions.querySelector("#sentinelGroupAddDevice").addEventListener("click", addThisDevice);
    actions.querySelector("#sentinelGroupAddSystem").addEventListener("click", function () {
      addSection("system-events", "system events");
    });
    actions.querySelector("#sentinelGroupAddDriver").addEventListener("click", function () {
      addSection("driver-events", "driver events");
    });
    actions.querySelector("#sentinelGroupPass").addEventListener("click", passGroup);
    actions.querySelector("#sentinelGroupClear").addEventListener("click", clearGroup);
    actions.querySelector("#sentinelGroupDone").addEventListener("click", function () {
      setGroupMode(false);
    });
  }

  function pruneDisabled() {
    if (!global.__sentinelTestStatus || typeof global.__sentinelTestStatus.isWorkLabelEnabled !== "function") {
      return;
    }
    const keep = [];
    selected.forEach(function (t) {
      const label = t && t.targetName ? t.targetName : "";
      const kind = t && t.kind ? t.kind : "";
      if (global.__sentinelTestStatus.isWorkLabelEnabled(label, kind)) keep.push(t);
    });
    if (keep.length === selected.size) {
      updateChrome();
      return;
    }
    selected.clear();
    keep.forEach(function (t) {
      const key = String(t && t.targetKey ? t.targetKey : "").trim();
      if (key) selected.set(key, t);
    });
    updateChrome();
  }

  function attach(nextOpts) {
    opts = nextOpts && typeof nextOpts === "object" ? nextOpts : {};
    injectStyle();
    mountToggle();
    mountActions();
    bindDragSelect();
    updateChrome();
  }

  global.__sentinelGroupPass = {
    attach: attach,
    handleTestButtonClick: handleTestButtonClick,
    handleViewportBoxClick: handleViewportBoxClick,
    onBatchAck: onBatchAck,
    pruneDisabled: pruneDisabled,
    isGroupMode: function () {
      return groupMode;
    },
    selectedCount: function () {
      return selected.size;
    },
  };
})(typeof globalThis !== "undefined" ? globalThis : window);
