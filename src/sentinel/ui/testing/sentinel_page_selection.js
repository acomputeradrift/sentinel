/**
 * Page-level button selection for technician device HTML.
 * Drag-marquee and shift-click add/remove wraps on the current page; Pass All
 * submits every target on the selected buttons (same as per-button Pass All).
 * Expects globals from the generated page script (buildTargetPayload, etc.).
 */
(function (global) {
  "use strict";

  const DRAG_PX = 6;
  const selectedWraps = new Set();
  let drag = null;
  let suppressClick = false;

  function $(id) {
    return document.getElementById(id);
  }

  function ovOpen() {
    const ov = $("ov");
    return !!(ov && ov.classList && ov.classList.contains("open"));
  }

  function pageSelBar() {
    return $("pageSelBar");
  }

  function pageSelMarquee() {
    return $("pageSelMarquee");
  }

  function pageSelCount() {
    return $("pageSelCount");
  }

  function pageSelPassAll() {
    return $("pageSelPassAll");
  }

  function inIgnoredChrome(el) {
    if (!el || !el.closest) return true;
    if (el.closest(".ov, .pop, .vp-popup-panel, .page-sel-bar, .app-ui-controls, .zoom-controls, .layer-panel, .orientation-toggle")) {
      return true;
    }
    if (el.closest(".page-link-hit")) return true;
    return false;
  }

  function inDeviceSurface(el) {
    if (!el || !el.closest) return false;
    return !!el.closest(".rti-device-canvas, .rtiDeviceContent, #rtiDeviceCanvas, #rtiDeviceContent, #rtiUsableCanvas, #rtiCanvas");
  }

  function selectableWrapsOnPage() {
    const page = typeof activePageEl === "function" ? activePageEl() : document.querySelector(".device-page.active");
    if (!page) return [];
    const out = [];
    page.querySelectorAll(".btn-wrap").forEach((wrap) => {
      if (!wrap || wrap.classList.contains("vp-btn")) return;
      if (wrap.classList.contains("synthetic-list-scroll")) return;
      if (String(wrap.dataset.visible || "1") === "0") return;
      const btn = wrap.querySelector(".test-btn");
      if (!btn) return;
      let meta = {};
      try {
        meta = JSON.parse(btn.dataset.meta || "{}");
      } catch (_e) {
        meta = {};
      }
      const targets = Array.isArray(meta.targets) ? meta.targets.map((t) => String(t || "").trim()).filter(Boolean) : [];
      if (!targets.length) return;
      const r = wrap.getBoundingClientRect();
      if (r.width < 1 || r.height < 1) return;
      const style = window.getComputedStyle(wrap);
      if (style.display === "none" || style.visibility === "hidden") return;
      if (style.pointerEvents === "none") return;
      out.push(wrap);
    });
    return out;
  }

  function rectsIntersect(a, b) {
    return a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
  }

  function wrapKey(wrap) {
    if (!wrap) return "";
    if (wrap.dataset && wrap.dataset.pageSelKey) return wrap.dataset.pageSelKey;
    const key = `ps:${selectedWraps.size}:${Math.random().toString(36).slice(2)}`;
    wrap.dataset.pageSelKey = key;
    return key;
  }

  function pruneSelection() {
    const live = new Set(selectableWrapsOnPage());
    for (const wrap of Array.from(selectedWraps)) {
      if (!wrap || !wrap.isConnected || !live.has(wrap)) selectedWraps.delete(wrap);
    }
  }

  function syncSelectionClass() {
    document.querySelectorAll(".btn-wrap.is-page-selected").forEach((el) => {
      if (!selectedWraps.has(el)) el.classList.remove("is-page-selected");
    });
    selectedWraps.forEach((wrap) => {
      if (wrap && wrap.classList) wrap.classList.add("is-page-selected");
    });
  }

  function syncSelBar() {
    pruneSelection();
    syncSelectionClass();
    const bar = pageSelBar();
    const countEl = pageSelCount();
    const passBtn = pageSelPassAll();
    const n = selectedWraps.size;
    if (countEl) countEl.textContent = n === 1 ? "1 button selected" : `${n} buttons selected`;
    if (bar) {
      if (n > 0) {
        bar.classList.add("is-on");
        bar.removeAttribute("hidden");
      } else {
        bar.classList.remove("is-on");
        bar.setAttribute("hidden", "hidden");
      }
    }
    if (passBtn) {
      const posting = typeof isPosting !== "undefined" && isPosting;
      passBtn.disabled = posting || n < 1;
    }
  }

  function clearPageSelection() {
    selectedWraps.forEach((wrap) => {
      if (wrap && wrap.classList) wrap.classList.remove("is-page-selected");
    });
    selectedWraps.clear();
    hideMarquee();
    syncSelBar();
  }

  function toggleWrap(wrap) {
    if (!wrap) return;
    if (selectedWraps.has(wrap)) selectedWraps.delete(wrap);
    else selectedWraps.add(wrap);
    wrapKey(wrap);
    syncSelBar();
  }

  function applyMarqueeSelection(rect, additive) {
    const hits = selectableWrapsOnPage().filter((wrap) => rectsIntersect(rect, wrap.getBoundingClientRect()));
    if (!additive) {
      selectedWraps.forEach((wrap) => {
        if (wrap && wrap.classList) wrap.classList.remove("is-page-selected");
      });
      selectedWraps.clear();
    }
    hits.forEach((wrap) => {
      selectedWraps.add(wrap);
      wrapKey(wrap);
    });
    syncSelBar();
  }

  function hideMarquee() {
    const el = pageSelMarquee();
    if (!el) return;
    el.classList.remove("is-on");
    el.setAttribute("hidden", "hidden");
    el.style.left = "0px";
    el.style.top = "0px";
    el.style.width = "0px";
    el.style.height = "0px";
  }

  function showMarquee(x0, y0, x1, y1) {
    const el = pageSelMarquee();
    if (!el) return;
    const left = Math.min(x0, x1);
    const top = Math.min(y0, y1);
    const width = Math.abs(x1 - x0);
    const height = Math.abs(y1 - y0);
    el.style.left = `${left}px`;
    el.style.top = `${top}px`;
    el.style.width = `${width}px`;
    el.style.height = `${height}px`;
    el.classList.add("is-on");
    el.removeAttribute("hidden");
  }

  function marqueeRect(x0, y0, x1, y1) {
    const left = Math.min(x0, x1);
    const top = Math.min(y0, y1);
    return { left, top, right: left + Math.abs(x1 - x0), bottom: top + Math.abs(y1 - y0) };
  }

  function newSelectionId() {
    try {
      if (global.crypto && typeof global.crypto.randomUUID === "function") return global.crypto.randomUUID();
    } catch (_e) {}
    return `sel-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function collectSelectionPassItems() {
    pruneSelection();
    const wraps = Array.from(selectedWraps);
    const pageState = typeof activePageState === "function" ? activePageState() : {};
    const selectionId = newSelectionId();
    const items = [];
    for (const wrap of wraps) {
      const btn = wrap.querySelector(".test-btn");
      if (!btn) continue;
      let meta = {};
      try {
        meta = JSON.parse(btn.dataset.meta || "{}");
      } catch (_e) {
        meta = {};
      }
      const labels = Array.isArray(meta.targets) ? meta.targets : [];
      for (const raw of labels) {
        const label = String(raw || "").trim();
        if (!label) continue;
        if (typeof buildTargetPayload !== "function") continue;
        const target = buildTargetPayload(btn, meta, label);
        if (!target || !target.targetKey) continue;
        items.push({
          target: {
            targetKey: target.targetKey,
            kind: target.kind,
            refs: Object.assign({}, target.refs || {}),
            targetName: target.targetName,
          },
          outcome: "PASS",
          failNote: null,
          wrap,
          btn,
        });
      }
    }
    const buttonCount = wraps.length;
    const targetCount = items.length;
    const sourceDetail = {
      selectionId,
      pageId: pageState && pageState.pageId != null ? pageState.pageId : null,
      pageName: pageState && pageState.pageName != null ? String(pageState.pageName) : "",
      buttonCount,
      targetCount,
    };
    return { items, sourceDetail };
  }

  function postSelectionPassAll() {
    if (typeof isPosting !== "undefined" && isPosting) return;
    const collected = collectSelectionPassItems();
    const items = collected.items;
    if (!items.length) return;
    if (typeof _sendTechWs !== "function") return;
    const results = items.map((it) => ({
      target: it.target,
      outcome: "PASS",
      failNote: null,
      source: "SELECTION_PASS_ALL",
      sourceDetail: collected.sourceDetail,
    }));
    if (typeof statusByTargetKey !== "undefined" && statusByTargetKey && typeof statusByTargetKey.set === "function") {
      for (const it of items) {
        statusByTargetKey.set(it.target.targetKey, { outcome: "PASS", recordedAtUtc: "" });
      }
    }
    if (typeof refreshButtonVisualStates === "function") refreshButtonVisualStates();
    global.__pageSelPendingBatch = true;
    if (typeof setPosting === "function") setPosting(true);
    if (typeof setPostStatus === "function") setPostStatus("", "");
    if (typeof _logTechWs === "function") _logTechWs("send", "test_result.submit_batch");
    _sendTechWs({ type: "test_result.submit_batch", results });
  }

  function onPointerDown(ev) {
    if (ev.button != null && ev.button !== 0) return;
    if (ovOpen()) return;
    if (typeof viewportMode !== "undefined" && viewportMode && viewportMode.active) return;
    const t = ev.target;
    if (inIgnoredChrome(t)) return;
    if (!inDeviceSurface(t)) return;
    drag = {
      x0: ev.clientX,
      y0: ev.clientY,
      additive: !!ev.shiftKey,
      moved: false,
      startWrap: t && t.closest ? t.closest(".btn-wrap") : null,
    };
  }

  function onPointerMove(ev) {
    if (!drag) return;
    const dx = ev.clientX - drag.x0;
    const dy = ev.clientY - drag.y0;
    if (!drag.moved && (Math.abs(dx) >= DRAG_PX || Math.abs(dy) >= DRAG_PX)) {
      drag.moved = true;
      try {
        document.body.classList.add("page-sel-dragging");
      } catch (_e) {}
    }
    if (!drag.moved) return;
    ev.preventDefault();
    showMarquee(drag.x0, drag.y0, ev.clientX, ev.clientY);
  }

  function onPointerUp(ev) {
    if (!drag) return;
    const state = drag;
    drag = null;
    try {
      document.body.classList.remove("page-sel-dragging");
    } catch (_e) {}
    if (state.moved) {
      suppressClick = true;
      global.__pageSelSuppressClick = true;
      setTimeout(() => {
        suppressClick = false;
        global.__pageSelSuppressClick = false;
      }, 0);
      applyMarqueeSelection(marqueeRect(state.x0, state.y0, ev.clientX, ev.clientY), state.additive);
      hideMarquee();
      return;
    }
    hideMarquee();
    const wrap = ev.target && ev.target.closest ? ev.target.closest(".btn-wrap") : state.startWrap;
    if (ev.shiftKey && wrap && selectableWrapsOnPage().includes(wrap)) {
      toggleWrap(wrap);
      suppressClick = true;
      global.__pageSelSuppressClick = true;
      setTimeout(() => {
        suppressClick = false;
        global.__pageSelSuppressClick = false;
      }, 0);
      return;
    }
    if (!wrap && !ev.shiftKey) {
      clearPageSelection();
    }
  }

  function onClickCapture(ev) {
    if (!(suppressClick || global.__pageSelSuppressClick || ev.shiftKey)) return;
    const btn = ev.target && ev.target.closest ? ev.target.closest(".test-btn") : null;
    if (!btn && !suppressClick && !global.__pageSelSuppressClick) return;
    if (ev.shiftKey || suppressClick || global.__pageSelSuppressClick) {
      ev.preventDefault();
      ev.stopPropagation();
    }
  }

  function bindBar() {
    const passBtn = pageSelPassAll();
    const clearBtn = $("pageSelClear");
    if (passBtn && !passBtn.dataset.boundPageSel) {
      passBtn.dataset.boundPageSel = "1";
      passBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        postSelectionPassAll();
      });
    }
    if (clearBtn && !clearBtn.dataset.boundPageSel) {
      clearBtn.dataset.boundPageSel = "1";
      clearBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        clearPageSelection();
      });
    }
  }

  function patchSetActivePage() {
    if (typeof setActivePage !== "function") return;
    if (setActivePage.__pageSelPatched) return;
    const orig = setActivePage;
    const wrapped = function () {
      clearPageSelection();
      return orig.apply(this, arguments);
    };
    wrapped.__pageSelPatched = true;
    global.setActivePage = wrapped;
  }

  function patchSetPosting() {
    if (typeof setPosting !== "function") return;
    if (setPosting.__pageSelPatched) return;
    const orig = setPosting;
    const wrapped = function (on) {
      orig(on);
      syncSelBar();
    };
    wrapped.__pageSelPatched = true;
    global.setPosting = wrapped;
  }

  function init() {
    bindBar();
    patchSetActivePage();
    patchSetPosting();
    document.addEventListener("pointerdown", onPointerDown, true);
    document.addEventListener("pointermove", onPointerMove, true);
    document.addEventListener("pointerup", onPointerUp, true);
    document.addEventListener("pointercancel", onPointerUp, true);
    document.addEventListener("click", onClickCapture, true);
    hideMarquee();
    syncSelBar();
  }

  global.__sentinelPageSelection = {
    clear: clearPageSelection,
    sync: syncSelBar,
    selectedCount: () => selectedWraps.size,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(typeof window !== "undefined" ? window : globalThis);
