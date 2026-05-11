# Injection Rejection Plan — UI Stabilization & 2026 Upgrade

## Executive Summary

The current system is structurally strong in backend, data contracts, and pipeline design. However, the frontend rendering layer introduces instability due to:

- Heavy reliance on DOM injection (`innerHTML`, string-built HTML)
- Lack of deterministic templates
- Mixed responsibilities (layout, data, behavior intertwined)
- Inconsistent styling across generated and runtime UI

This leads to fragile updates, difficult change control, performance issues at scale, and layered patching.

---

## Core Problem

Current approach:

Data → JS → Inject DOM → Patch Layout → Patch Styles

Target approach:

Data → Template → Static HTML → Shared CSS → Minimal JS (state only)

---

## Strategic Shift

Adopt a **Deterministic Rendering System**:

- Layout is static or templated
- Styling is centralized
- JS handles only state and events
- No runtime layout decisions
- No HTML string injection for structure

---

## Implementation Plan

### 1. Introduce a UI Schema Layer

Pipeline becomes:

.apex → extraction → contract JSON → UI schema → render

Benefits:
- Stable contract for UI
- Decouples raw data from rendering
- Enables templating

---

### 2. Replace String-Based HTML Generation

Current:
- `render_core.py` builds HTML via string concatenation

Target:
- Introduce templating (e.g., Jinja2)

Structure:

/templates
  /devices
  /components

Benefits:
- Predictable structure
- Reusability
- Safer rendering

---

### 3. Eliminate Layout Injection

Facts:
- Screen size is fixed per device
- Hard key layout is fixed
- Only button positions vary

Approach:
- Static device templates
- Static hard key HTML
- Dynamic buttons via CSS variables

Example:

.button {
  position: absolute;
  left: var(--x);
  top: var(--y);
  width: var(--w);
  height: var(--h);
}

---

### 4. Standardize Components

Create shared components:

- Button
- Status indicator

Use consistent classes:

.btn
.btn--pass
.btn--fail
.btn--pending

---

### 5. Fix Real-Time Performance

Problem:
- Sequential DOM updates per target

Solution:
- Batch updates using requestAnimationFrame
- Update state first, render once
- Update only affected elements

---

### 6. Remove DOM Injection in Commissioning UI

Replace:
- innerHTML
- insertAdjacentHTML

With:
- Predefined DOM
- textContent updates
- Class toggling

Benefits:
- Predictable rendering
- Reduced reflows
- Eliminates XSS risk

---

### 7. Consolidate Styling

Target structure:

/css
  base.css
  layout.css
  components.css
  devices.css

Rules:
- No JS-generated styles
- No per-render CSS injection
- Only CSS variables inline

---

### 8. Reduce render_core.py Risk

Current:
- Large, high-coupling file

Plan:
- Extract component render functions
- Introduce templates incrementally
- Add test coverage before splitting

---

### 9. Optimize Generated Output

Fix:
- Externalize JS/CSS
- Cache static assets
- Reduce HTML payload size

---

### 10. Improve Deployment Consistency

Enhancements:
- Version UI schema with code
- Validate schema before generation
- Regenerate artifacts after deploy when required

---

## Expected Outcomes

### Stability
- Predictable UI changes
- No cascading failures

### Performance
- Faster rendering
- No per-target lag

### Maintainability
- Clear separation of concerns

### Scalability
- Efficient handling of large datasets (30k+ items)

---

## What Not to Change

- Extraction pipeline
- Backend APIs
- WebSocket infrastructure
- Overall data flow

---

## Conclusion

This is a targeted refactor of the rendering layer, not a full rewrite.

The goal is to replace injection-driven UI with a deterministic, template-driven system aligned with modern standards.

