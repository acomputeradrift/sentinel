# Sentinel Management surface, tokens, new test pass, and PDF reports

Working plan. Locked from the 2026-09-05 investigation (token 410 on refresh, three-surface split, dealer clear/reset, report data). Do not implement a slice until Jamie approves that slice’s file list.

**Related:** `docs/api_contract_v1.md`, `docs/data_contracts.md`, `docs/directives/invariants.md`, `docs/directives/scope.md`, `docs/architecture/live_update_no_strand_strategy.md`.

---

## Locked decisions

1. **Three operator/field surfaces** (not three stacks):
   - **Technician** — `/testing/{techToken}` — one project, test only.
   - **Console** — `/commissioning/` — one selected job: File, Commissioning, Diagnostics, this-job test-type settings. Shortcut only for this job’s **active** tech URL (Copy/Open).
   - **Management** — new browser URL `/management/` — shop-wide: people, tokens, start-new-pass, reports.
2. **#1 refresh warning** is `This technician link has been revoked.` (`TECH_LINK_REVOKED`, HTTP 410). Same text for unknown and revoked. Deploys are **not** wiping Postgres tokens. The console cannot re-show the issued path (hash-only + list returns `techUrl: ""`), so a new token is issued and the old tab 410s.
3. **Do not mint or rotate tokens as a side effect of list, refresh, or deploy.**
4. **One active link per named technician per project.** Management is the system of record. Do not keep two full token editors.
5. **Dealers may reset testing on their own projects.** Field techs may not. Another dealer never. Vendor (Jamie) is not required for normal reset.
6. **Start new test pass** replaces today’s hard `DELETE` of `test_results` / `fail_tags`. History stays. Current derived state goes back to untested after a recorded pass boundary.
7. **Reports use only stored/derived data.** No inferred RTI facts. No new data types invented for a prettier PDF.

`scope.md` today names two testing areas plus diagnostics. Adding `/management/` is a **scope add** and must be approved before that slice’s code.

---

## Responsibility split

| Surface | Owns | Does not own |
|---|---|---|
| Technician | PASS/FAIL, fail notes | Tokens, diagnostics, reports, reset |
| Console | This job: upload, regenerate, live progress/fails, diagnostics, per-project testing-type on/off | Rotate/revoke/create-second-link, hard wipe, shop roster, PDF builder |
| Management | Roster, token lifecycle (issue, **re-display URL**, copy/open, rotate, revoke, active vs dead), start new pass, PDF reports | Device mimic, diagnostics, File/regenerate |

Clear Tests tab moves off the Console once Management start-new-pass ships. Until then, do not add a second wipe button.

---

## 1) Token revoke / blank-URL fix

**User-visible problem:** Refresh of a technician URL shows #1 after deploy or console reload.

**Root cause:** Issued `techToken` is returned only on create/rotate. DB stores SHA-256 only. `GET .../tech-links` sets `techUrl: ""`. Reload blanks Copy/Open. Create issues another token. Old bookmark → 410.

**Required behavior**

- Persist the last issued path (or plaintext token) for commissioning/management read-back.
- `GET` list returns that `techUrl` for **active** links. No rotate on GET.
- After deploy + console/management refresh, Copy/Open still work and the **same** URL stays valid.
- Rotate is explicit: new URL, old URL becomes #1, UI shows that.
- Revoke is explicit. No revoke-fails-then-rotate fallback.
- Optional later: distinct message for unknown vs revoked. Not required to stop the loop.

**Do first.** Management UI and Console shortcut both need this API. A new page on hash-only tokens will still go blank.

---

## 2) Management browser URL

**Entry:** `/management/` (packaged static UI, same family as `/commissioning/`). Same droplet, same API host.

**Pages / sections (v1)**

1. **Context** — client + project picker (all of this dealer’s jobs), or a cross-project token list.
2. **Technicians** — company roster (already find-or-create by name).
3. **Tech links** — for the selected project (and later a shop-wide “who is live” table):
   - name, live `/testing/{token}` (+ `runtime=shell` when opened from our UI), issued at, active/revoked
   - Copy, Open, Rotate, Revoke
   - create = issue **or** reuse the one active link for that name on this project
4. **Start new test pass** — see §3.
5. **Reports** — see §4.

No login product in v1 (stub company user stays). Still dealer-scoped by existing `user_id` on clients. Cross-dealer isolation is a later auth slice; do not pretend `/management/` is multi-tenant until that exists.

---

## 3) Start new test pass (replace Clear Tests)

**Today:** `POST /api/v1/commissioning/projects/{projectId}/clear-tests` deletes all `test_results` and `fail_tags` for the project. Console copy: “Remove all recorded test results.”

**Sold product**

- Dealer operator, **this project only**, from Management.
- Confirm by typing the project name.
- Record who/when/project (and optional reason).
- **Do not delete history.** Append a pass-boundary (or equivalent) so derived `currentOutcome` is `UNTESTED` for targets after that boundary. Pies, fails list, tech page follow derived state. Old rows remain queryable for reports (“include prior passes”).
- Fail tags reset for the new pass (or become inactive); do not destroy the fact that a tag existed if we can keep it on the old pass.
- Event-log the action (invariant 6).

Field tech never sees this control.

---

## 4) PDF report generator — UI from real data

Reports tab on the Console is a stub. Management owns the builder. Generate a PDF from **selected** slices of data we already persist or derive.

### Data that exists (do not invent)

**Identity**

- Client name, project name, `projectId`
- Active upload: `originalFilename`, `uploadedAtUtc`
- `asOfGenerationRunId`, project `status` (note: DB still stores `EMPTY`; READY is session/WS today — persist READY is a companion, not required for v1 PDF if we print filename + generated-at from upload)

**Progress (`ProjectProgress`)**

- Project `counts`: total / tested / pass / fail / untested / `percentComplete` / `lastTestedAtUtc`
- `eventSections.system` and `eventSections.driver` (same counts)
- Per-**device** rollups (`deviceId`, `displayName`, same counts)
- Page-level rollups are **not** implemented — do not offer a page picker until they exist
- Disabled **testing types** are already excluded from these counts

**Current per-target state**

- `targetKey`, `kind` (`EVENT|BUTTON|VIEWPORT_BUTTON`), `targetName`
- `currentOutcome` `PASS|FAIL|UNTESTED`
- `lastTestedAtUtc`, `lastFailNote`
- `recordedBy` / `techName` (survives revoke)

**Fails (latest FAIL + tags)**

- Fail note (required on FAIL)
- Programmer task tag: `NOT_STARTED|IN_PROGRESS|DONE`
- Classification `FailTag`: `TARGET|SCOPE|DATA|RESOLUTION|UNKNOWN`
- Placement: `deviceName`, `pageName`, `buttonName`, `layerName`, `viewport`
- Room/source: `effectiveRoomName`, `effectiveSourceName`, `effectiveScopeNames`, `scopeType`

**History (`TestResultRecord`)**

- Full append-only rows: outcome, note, time, `source` `SINGLE|GROUP`, `batchId`, `recordedBy`
- Snapshot `activities` is latest-per-target, capped at 50 — **reports must not use that cap**; query history properly

**Testing-type catalog** (include/exclude in the PDF, independent of job on/off if the dealer wants a full inventory)

- Buttons: Text, System Macro, Macro Step, Variable (Text/Reversed/Inactive/Visible/Value/State/Command/Image/List), Bitmap, Icon, Page Link
- Events: Event Trigger, System Macro, Macro Step

**Tech links / roster** — operator appendix only; default **off** on owner-facing PDFs.

**Not available today** — do not put on the picker: photos, signatures, site address, page pies, live device screenshots.

### Report builder UI (Management)

One form, two layers: **preset** then **overrides**.

**A. Audience preset** (sets defaults; user can still tick boxes)

| Preset | Intent |
|---|---|
| Closeout / owner | Cover + project progress + device list + **current fails with notes**. No full audit, no tokens, no programmer tags. |
| Dealer punch list | Cover + fails only, with notes, device/page/button, room/source, tech name, task tag (`NOT_STARTED`…). |
| Full audit | Cover + progress + all current targets + full append-only history + who + SINGLE/GROUP. |

**B. Scope** (what jobs/slices)

- This project (required in v1). Multi-project PDF is later.
- Include: whole project, and/or **System events**, **Driver events**, **selected devices** (checklist from `progress.devices`).
- Honor current testing-type settings, with an override: “Include types turned off on the job” (prints them, labeled excluded-from-progress).

**C. Content checkboxes** (only fields we have)

- Cover (client, project, file, generated/uploaded at, report time)
- Progress summary (project counts)
- Event section counts
- Device counts table
- Current target list — filter: Pass / Fail / Untested
- Fail detail — notes, device/page/button, room/source, tech name
- Programmer fields — task tag, FailTag classification (off for Closeout)
- Full history (all append-only rows; optional “prior passes” once start-new-pass exists)
- Testing-type legend (what was required vs off)
- Operator appendix — active tech names only, **not** raw tokens, default off

**D. Generate**

- Server builds PDF from the same progress/fails/history queries as the console (no second extract).
- Filename: `{client}-{project}-{preset}-{date}.pdf`.
- Additive API, e.g. `POST /api/v1/commissioning/projects/{projectId}/reports` with the option bag; `GET` returns the file.

Existing `devtools/render_*_pdf.py` scripts are architecture diagrams, not this product. Do not reuse them as the report engine.

---

## Numbered todo (do not skip)

1. **Approve this plan** (this file). Correct here before code.
2. **Approve `scope.md` add** for `/management/` as a third browser surface (operator, not a third testing UI).
3. **Token persist + list `techUrl`** — tests first, then migration + queries + list/create/rotate contract (additive). Prove: create → reload list → same URL; rotate → old URL 410, new URL listed. No Management UI yet.
4. **One active link per technician per project** on create (reuse or reject duplicate). Tests first.
5. **Revoke is revoke only** — remove console fallback that rotates on revoke failure.
6. **Start new test pass** — tests first: history rows remain; derived current state is untested; confirm-by-name; event log; dealer-scoped. Replace `clear-tests` delete behavior (keep old route as alias only if we must; prefer new route and retire the delete).
7. **Persist project `READY`** when generation succeeds (and treat existing generated artifacts as ready after restart) so Create/Open is not session-only. Separate from tokens but blocks “job looks dead after deploy.”
8. **Management static UI** at `/management/` — roster + tech links using the persisted URL API. Console Tech Links tab becomes Copy/Open shortcut or is removed in the same slice (one editor).
9. **Move start-new-pass** onto Management; remove Console Clear Tests tab.
10. **Report option contract** — JSON bag matching §4 checkboxes; unittest against sample progress/fails/history (no PDF pixels yet).
11. **PDF generator + Management builder UI** — presets + checkboxes + device/event scope; Playwright for the builder; unittest that omitted sections are absent from the rendered document structure.
12. **Deploy** only when Jamie says deploy, after Intent Check Gate for the slice just shipped.

---

## Out of this plan

- Targeted / single-page tech links (held).
- Technician logins.
- Real multi-dealer auth (needed before selling; not this plan’s first slice).
- Dual-instance rolling deploy (live-update strategy Phases 2–4).
- Page-level progress pies.
- Inferring report fields that are not in the extract or result store.
