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
    systemEvents: "var(--sentinel-fill-system-event, #1e5f86)",
    driverEvents: "var(--sentinel-fill-driver-event, #1e5f86)",
  };

  const STATE_TRIM = {
    pass: "var(--sentinel-trim-pass, #39b54a)",
    partial: "var(--sentinel-trim-partial, #fcb040)",
    fail: "var(--sentinel-trim-fail, #ef4444)",
    retest: "var(--sentinel-trim-retest, #c026d3)",
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

  const MACRO_ALIASES = { macro: 1, macros: 1, "system macro": 1, "system macros": 1 };
  const MACRO_STEP_ALIASES = {
    macrostep: 1,
    macrosteps: 1,
    "macro step": 1,
    "macro steps": 1,
    "macro-step": 1,
  };
  const TRIGGER_ALIASES = { trigger: 1, triggers: 1, "event trigger": 1, "event triggers": 1 };
  const PAGE_LINK_ALIASES = { pagelink: 1, "page link": 1, pagelinks: 1, "page links": 1 };

  let disabledTypeIds = new Set();

  function canonicalizeTestingLabel(label) {
    const s = String(label || "").trim();
    if (!s) return "";
    const lower = s.toLowerCase();
    if (MACRO_ALIASES[lower]) return "System Macro";
    if (MACRO_STEP_ALIASES[lower]) return "Macro Step";
    if (TRIGGER_ALIASES[lower]) return "Event Trigger";
    if (PAGE_LINK_ALIASES[lower]) return "Page Link";
    if (lower === "text" || lower === "texts") return "Text";
    if (lower === "bitmap") return "Bitmap";
    if (lower === "icon") return "Icon";
    if (lower.indexOf("variable - ") === 0) {
      const tail = s.split("-").slice(1).join("-").trim();
      return tail ? "Variable - " + tail.charAt(0).toUpperCase() + tail.slice(1) : s;
    }
    if (lower.indexOf("var.") === 0) {
      const tail = s.slice(4).trim();
      return tail ? "Variable - " + tail.charAt(0).toUpperCase() + tail.slice(1) : s;
    }
    return s;
  }

  function familyForKind(kind) {
    return String(kind || "").trim().toUpperCase() === "EVENT" ? "event" : "button";
  }

  function typeIdForLabel(label, kind) {
    const name = canonicalizeTestingLabel(label);
    if (!name) return "";
    return familyForKind(kind) + ":" + name;
  }

  function setDisabledTypeIds(ids) {
    const next = new Set();
    (Array.isArray(ids) ? ids : []).forEach(function (id) {
      const s = String(id || "").trim();
      if (s) next.add(s);
    });
    disabledTypeIds = next;
  }

  function applySettingsPayload(payload) {
    const src = payload && typeof payload === "object" ? payload : {};
    const nested = src.testingTypeSettings && typeof src.testingTypeSettings === "object" ? src.testingTypeSettings : src;
    setDisabledTypeIds(nested.disabledTypes);
    if (global.__sentinelGroupPass && typeof global.__sentinelGroupPass.pruneDisabled === "function") {
      global.__sentinelGroupPass.pruneDisabled();
    }
  }

  function isWorkLabelEnabled(label, kind) {
    const typeId = typeIdForLabel(label, kind);
    if (!typeId) return true;
    return !disabledTypeIds.has(typeId);
  }

  function filterWorkTargets(meta) {
    const m = meta && typeof meta === "object" ? meta : {};
    return buttonTargetsFromMeta(m).filter(function (label) {
      return isWorkLabelEnabled(label, m.kind);
    });
  }

  /**
   * Compute pass/partial/fail/untested. Any FAIL among targets => fail (red outline).
   */
  function aggregateTestOutcomeState(meta, ctxBtn, statusByTargetKey, buildTargetPayload) {
    const m = meta && typeof meta === "object" ? meta : {};
    const wrap = ctxBtn && ctxBtn.closest ? ctxBtn.closest(".btn-wrap") : null;
    const categoryKey = buttonCategoryKeyFromMeta(m, wrap);
    const targets = filterWorkTargets(m);
    if (categoryKey === "emptyTag") {
      return { stateKey: "fail", passCount: 0, targetCount: 0 };
    }
    if (!targets.length) {
      return { stateKey: "untested", passCount: 0, targetCount: 0 };
    }
    let passCount = 0;
    let failCount = 0;
    let retestCount = 0;
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
      if (outcome === "FAIL") {
        failCount += 1;
        if (rec.retestReady) retestCount += 1;
      }
    }
    if (failCount > 0) {
      if (retestCount > 0) {
        return { stateKey: "retest", passCount, targetCount: targets.length };
      }
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
    canonicalizeTestingLabel: canonicalizeTestingLabel,
    typeIdForLabel: typeIdForLabel,
    setDisabledTypeIds: setDisabledTypeIds,
    applySettingsPayload: applySettingsPayload,
    isWorkLabelEnabled: isWorkLabelEnabled,
    filterWorkTargets: filterWorkTargets,
    aggregateTestOutcomeState: aggregateTestOutcomeState,
    applyTestTrimToWrap: applyTestTrimToWrap,
    refreshButtonWraps: refreshButtonWraps,
  };
})(typeof globalThis !== "undefined" ? globalThis : window);
