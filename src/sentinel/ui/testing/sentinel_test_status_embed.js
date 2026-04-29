/**
 * Shared test-status visuals for technician HTML (project home + device pages).
 * Injected before page scripts; exposes globalThis.__sentinelTestStatus.
 */
(function (global) {
  "use strict";

  const CATEGORY_FILL = {
    screenLabels: "var(--sentinel-fill-screen-label, #58585a)",
    screenButtons: "var(--sentinel-fill-screen-button, #2c6fb7)",
    hardButtons: "var(--sentinel-fill-hard-button, #2c6fb7)",
    uiItems: "var(--sentinel-fill-ui-item, #a7a9ac)",
    emptyTag: "var(--sentinel-fill-empty-tag, #ef4444)",
    systemEvents: "var(--sentinel-fill-system-event, #58585a)",
    driverEvents: "var(--sentinel-fill-driver-event, #2c6fb7)",
  };

  const STATE_TRIM = {
    pass: "var(--sentinel-trim-pass, #39b54a)",
    partial: "var(--sentinel-trim-partial, #fcb040)",
    fail: "var(--sentinel-trim-fail, #ef4444)",
    untested: "var(--sentinel-trim-untested, transparent)",
  };

  function buttonCategoryKeyFromMeta(meta, wrap) {
    const m = meta && typeof meta === "object" ? meta : {};
    const fromMeta = String(m.categoryKey || wrap?.dataset?.buttonCategory || "").trim();
    if (fromMeta && CATEGORY_FILL[fromMeta]) return fromMeta;
    const key = String(m.categoryKey || wrap?.dataset?.buttonCategory || "").trim();
    if (key && CATEGORY_FILL[key]) return key;
    const label = String(m.category || "").trim().toLowerCase();
    if (label === "screen label") return "screenLabels";
    if (label === "screen button") return "screenButtons";
    if (label === "hard button") return "hardButtons";
    if (label === "ui item") return "uiItems";
    if (label === "empty tag") return "emptyTag";
    if (label === "system event") return "systemEvents";
    if (label === "driver event") return "driverEvents";
    return "screenButtons";
  }

  function buttonTargetsFromMeta(meta) {
    const m = meta && typeof meta === "object" ? meta : {};
    const targets = Array.isArray(m.targets) ? m.targets : [];
    return targets.map((t) => String(t || "").trim()).filter(Boolean);
  }

  /**
   * Compute pass/partial/fail/untested. Any FAIL among targets => fail (red outline).
   */
  function aggregateTestOutcomeState(meta, ctxBtn, statusByTargetKey, buildTargetPayload) {
    const m = meta && typeof meta === "object" ? meta : {};
    const wrap = ctxBtn && ctxBtn.closest ? ctxBtn.closest(".btn-wrap") : null;
    const categoryKey = buttonCategoryKeyFromMeta(m, wrap);
    const targets = buttonTargetsFromMeta(m);
    if (categoryKey === "emptyTag") {
      return { stateKey: "fail", passCount: 0, targetCount: 0 };
    }
    if (!targets.length) {
      return { stateKey: "untested", passCount: 0, targetCount: 0 };
    }
    let passCount = 0;
    let failCount = 0;
    let recordedCount = 0;
    for (const label of targets) {
      const target = buildTargetPayload(ctxBtn, m, label);
      if (!target || !target.targetKey) continue;
      const rec = statusByTargetKey.get(target.targetKey);
      if (!rec) continue;
      const outcome = String(rec.outcome || "").toUpperCase();
      if (outcome !== "PASS" && outcome !== "FAIL") continue;
      recordedCount += 1;
      if (outcome === "PASS") passCount += 1;
      if (outcome === "FAIL") failCount += 1;
    }
    if (failCount > 0) {
      return { stateKey: "fail", passCount, targetCount: targets.length };
    }
    if (recordedCount === 0) {
      return { stateKey: "untested", passCount: 0, targetCount: targets.length };
    }
    if (passCount === targets.length && recordedCount === targets.length) {
      return { stateKey: "pass", passCount, targetCount: targets.length };
    }
    return { stateKey: "partial", passCount, targetCount: targets.length };
  }

  function applyTestTrimToWrap(wrap, categoryKey, agg) {
    const stateKey = agg.stateKey;
    const trimColor = STATE_TRIM[stateKey] || "transparent";
    const trimWidth = stateKey === "untested" ? "0px" : "4px";
    wrap.style.setProperty("--btn-state-trim-color", trimColor);
    wrap.style.setProperty("--btn-state-trim-width", trimWidth);
    const countEl = wrap.querySelector(".btn-pass-total");
    if (!countEl) return;
    const total = agg.targetCount || 0;
    const passCount = agg.passCount || 0;
    const countText = total > 0 ? passCount + "/" + total : "";
    countEl.textContent = countText;
    if (!countText) {
      countEl.style.display = "none";
      countEl.style.visibility = "hidden";
      return;
    }
    countEl.style.display = "block";
    countEl.style.visibility = "hidden";
    const wrapRect = wrap.getBoundingClientRect();
    const countRect = countEl.getBoundingClientRect();
    const fits = countRect.width <= wrapRect.width && countRect.height <= wrapRect.height;
    countEl.style.visibility = fits ? "visible" : "hidden";
    if (!fits) countEl.style.display = "none";
  }

  function refreshButtonWraps(options) {
    const root = options.root || document;
    const sel = options.wrapSelector || ".btn-wrap";
    const statusByTargetKey = options.statusByTargetKey;
    const buildTargetPayload = options.buildTargetPayload;
    if (!statusByTargetKey || typeof buildTargetPayload !== "function") return;
    root.querySelectorAll(sel).forEach(function (wrap) {
      const btn = wrap.querySelector(".test-btn");
      if (!btn) return;
      let meta = {};
      try {
        meta = JSON.parse(btn.dataset.meta || "{}");
      } catch (_e) {
        meta = {};
      }
      const categoryKey = buttonCategoryKeyFromMeta(meta, wrap);
      wrap.style.setProperty("--btn-fill-color", CATEGORY_FILL[categoryKey] || CATEGORY_FILL.screenButtons);
      const agg = aggregateTestOutcomeState(meta, btn, statusByTargetKey, buildTargetPayload);
      applyTestTrimToWrap(wrap, categoryKey, agg);
    });
  }

  global.__sentinelTestStatus = {
    CATEGORY_FILL: CATEGORY_FILL,
    STATE_TRIM: STATE_TRIM,
    buttonCategoryKeyFromMeta: buttonCategoryKeyFromMeta,
    buttonTargetsFromMeta: buttonTargetsFromMeta,
    aggregateTestOutcomeState: aggregateTestOutcomeState,
    applyTestTrimToWrap: applyTestTrimToWrap,
    refreshButtonWraps: refreshButtonWraps,
  };
})(typeof globalThis !== "undefined" ? globalThis : window);
