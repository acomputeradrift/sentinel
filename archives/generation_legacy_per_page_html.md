# Legacy Per-Page HTML Generation

This document preserves the removed HTML generation method that existed before Sentinel switched to single-device generation as the only supported path.

## What The Legacy Method Did

- Generated one standalone HTML file per device page.
- Used output names shaped like:
  - `<project_stem>__page-<page_index>-<page_slug>.html`
- Repeated the same shell, layout CSS, zoom logic, popup logic, and viewport logic in every generated page file.
- Used page-link controls to navigate by linking from one generated page file to another generated page file.

## Why It Was Removed

- It did not scale well for devices with many pages.
- It duplicated the same rendering code and behavior across many output files.
- It kept navigation tied to file-to-file transitions instead of in-memory application state.
- It conflicted with the approved scalable direction to render one active device page at a time from a single device shell.

## Relevant Legacy Entry Points

- `src/sentinel/generation/generate_html.py`
  - Previously defaulted to writing one file per page unless alternate flags were used.
- `src/sentinel/generation/render_core.py`
  - Previously exposed a per-page render entrypoint and page-based filename helper.

## Legacy Output Shape

- Per-page files:
  - `sample_project_data__page-0-home.html`
  - `sample_project_data__page-1-lights.html`
- Navigation model:
  - page links used `href` values pointing at those individual page files

## Replacement

- Sentinel now generates one HTML file per selected device.
- That file contains the device pages in one shell and switches the active page client-side.
- Page links now remain inside the same device HTML artifact and use extracted page relationships for page switching.
