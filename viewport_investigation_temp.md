# Viewport Visibility Investigation (Temp Working Doc)

Status: Active investigation log.  
Rule for this thread: update this document on every attempt before moving to the next theory.

## Problem Statement

Outside the viewport viewer, some viewport child buttons appear missing/randomly invisible.  
Inside the viewport viewer, those buttons are visible.

## Current Best Theory (T1)

Some viewport child buttons (`.btn-wrap.vp-btn`) are rendered but get visually covered on the base page by higher stacked elements (most likely `.vp-box` hit targets or same-layer siblings), while viewer clones normalize stacking so those same controls become visible there.

Secondary possibility: a subset of "missing" buttons are intentionally hidden by runtime gates (frame/orientation/layer visibility), which can look random.

## Theory T1 - Test Plan

### Test T1.1 - Classify all viewport buttons (hidden vs covered)

Steps:
1. Open the generated device page and go to the target page with the issue.
2. In DevTools Console, run the classifier snippet that prints each `.btn-wrap.vp-btn` with:
   - computed visibility (`display/visibility`)
   - frame/layer/orientation fields
   - top element at center point (`elementsFromPoint`)
3. Export/paste the resulting rows into this doc under "Results".

Expected results if T1 is correct:
- Many "missing" controls show `visible=true` but `covered=true`.
- Top covering element often includes class `.vp-box` or another positioned overlay/shell.
- At least some controls may show `visible=false` due to frame/orientation/layer gates, but that is not the majority for the reported symptom.

### Test T1.2 - Confirm z-order relationship for overlapping pairs

Steps:
1. Run overlap check between `.btn-wrap.vp-btn` and `.vp-box`.
2. Record only collisions where:
   - rectangles overlap, and
   - `vp-box z-index >= button z-index`
3. Compare button IDs from collision list to buttons user reports as missing.

Expected results if T1 is correct:
- Reported missing button IDs appear in overlap list with conflicting/higher `.vp-box` z.
- Visible/non-problem buttons show fewer/no such collisions.

### Test T1.3 - Verify inside-viewer visibility path differs

Steps:
1. Open viewport viewer for affected viewport.
2. Inspect corresponding cloned node(s) in `.vp-popup-stage`.
3. Confirm clone stacking/containment differs from base page:
   - clones under `.vp-popup-vcontent`
   - normalized local z behavior
4. Confirm missing-outside buttons become visible-inside for same frame/orientation.

Expected results if T1 is correct:
- Same logical button appears in popup and is visible there.
- Base-page invisibility is explained by occlusion/context, not extraction omission.

## Execution Log

### Iteration 1

- Theory tested: T1
- Test(s) run: T1.1 (classify all `.btn-wrap.vp-btn` as hidden vs covered)
- Expected:
  - Significant count of `visible=true && covered=true`
  - Top covering element often `.vp-box`
  - Hidden-by-gate (`visible=false`) exists but is not majority
- Actual:
  - total = 6
  - hidden = 0
  - covered = 6
  - For all 6 rows: `visible=true`, `display='block'`, `covered=true`, topClass=`vp-box`
  - z evidence: `topZ=10999750` while button z values are `10000000..10000006` (plus one at `10000002`)
- Match? (Yes/Partial/No): Yes (strong)
- Refinement decision:
  - Promote occlusion-by-viewport-box from hypothesis to confirmed primary cause for this sample/page.
  - De-prioritize frame/orientation/layer gating for this specific symptom instance (not observed in this run).
  - Next action: run T1.2 to verify overlap+z dominance mapping against reported missing button IDs across additional affected pages/viewports.

### Iteration 2

- Theory tested: T1 (visual comparison under normal viewport operation)
- Test(s) run: Screenshot side-by-side comparison (normal page vs focused viewport)
- Expected:
  - All 5 viewport buttons should be visible through the grey transparent viewport overlay in normal operation.
- Actual (user-confirmed):
  - There are 5 buttons in the viewport.
  - Buttons #2 and #3 are not showing in normal view.
  - Buttons #1, #4, and #5 are showing.
- Match? (Yes/Partial/No): Partial (supports selective visibility failure, not total overlay suppression)
- Refinement decision:
  - Update active failure signature to: "5 expected, #2 and #3 missing in normal view."
  - Next tests must target only slots #2 and #3 and identify exact DOM/runtime cause for those positions.

### Iteration 3

- Theory tested: T2 (slots #2 and #3 are present but selectively suppressed by overlap/stacking in normal view)
- Test(s) run: Slot-targeted DOM/runtime probe for buttons #2 and #3
- Expected:
  - If coverage is cause: both slots show block/visible + covered=true with higher top element z.
  - If runtime hide is cause: one or both slots show display:none or visibility:hidden.
- Actual (user-provided console output):
  - Slot #2: btnId=50736, text="Activity: Home/Lights", display=block, visibility=visible, opacity=1, btnZ=10000006, topClass=vp-box, topZ=10999750, covered=true
  - Slot #3: btnId=50730, text="1", display=block, visibility=visible, opacity=1, btnZ=10000000, topClass=vp-box, topZ=10999750, covered=true
  - Both slots include vpPv=0, vpLv=1 and are in same viewport/layer context.
- Match? (Yes/Partial/No): Yes (strong for overlap/stacking)
- Refinement decision:
  - Runtime hide path is ruled out for slots #2 and #3 in this state.
  - Confirmed: both "missing" slots are rendered and visible in CSS terms, but visually occluded by `.vp-box` with higher z.
  - Next focus should compare why slots #1/#4/#5 appear perceptible while #2/#3 are perceived missing despite same overlay class; likely contrast/perception and/or partial geometric overlap differences.

### Iteration 4

- Theory tested: T3 (contrast/perception issue under overlay explains why only #2/#3 appear missing)
- Test(s) run: User runtime observation while entering viewport mode
- Expected:
  - If T3 is true, opening viewport mode should not cause previously missing base-page buttons to suddenly become clearly visible outside the viewer.
- Actual (user-confirmed):
  - On click/open viewport, the originally missing buttons suddenly appear outside of the viewport viewer and are clearly visible.
- Match? (Yes/Partial/No): No
- Refinement decision:
  - Mark T3 as disproved.
  - Promote state-transition logic as primary suspect: entering `.viewport-mode` changes visibility/stacking behavior for base-page viewport buttons.
  - Next theory should isolate exact pre/post viewport-mode rules that differ for slots #2/#3.

### Iteration 5

- Theory tested: T4 (pre/post viewport-mode transition bug affects visibility of missing slots)
- Test(s) run: before-open vs after-open snapshot/diff for viewport buttons, with focus/z state capture
- Expected:
  - Meaningful pre/post change should appear for missing slots (#2/#3), likely z/focus/visibility-related.
- Actual (user-provided console output):
  - Slots #2/#3 before open:
    - display=block, visibility=visible, hasVpFocus=false
    - z values: slot2=10000006, slot3=10000000
  - Slots #2/#3 after open:
    - display=block, visibility=visible, hasVpFocus=true
    - z value for all viewport buttons becomes 2000000002
  - Same pattern observed for all viewport slots, not only #2/#3.
- Match? (Yes/Partial/No): Yes
- Refinement decision:
  - Confirmed root mechanism: entering viewport mode applies `.vp-focus` and force-elevates viewport buttons to a very high z tier (`2000000002`), overcoming pre-open occlusion.
  - The issue is now narrowed to pre-open layering rules (vp-box above buttons) versus desired behavior (buttons visible through overlay in normal mode).
  - Next theory should isolate whether pre-open `vp-box` z policy is too aggressive globally or only for this layer-band composition.

### Iteration 6

- Theory tested: T5 (state/stacking transition is the active mechanism, not extraction or contrast)
- Test(s) run: Manual pre-open z/focus force test in DevTools
- Expected:
  - If state/stacking is the mechanism, forcing viewport-level z/focus in normal mode should make previously missing buttons appear without opening viewer.
- Actual (user-confirmed):
  - Initial slot targeting note: index selection text was off by one in chat wording.
  - Despite that, applying high z/focus force in normal mode did make the previously missing buttons appear.
- Match? (Yes/Partial/No): Yes
- Refinement decision:
  - Strong proof that missing behavior is controlled by runtime stacking state, not data extraction, and not pure contrast.
  - Keep viewport overlay behavior as valid baseline; defect is inconsistent pre-open button visibility state versus expected "all visible through overlay."

### Iteration 7

- Theory tested: T6 (pre-open viewport box z placement masks viewport child buttons; moving box below button content in-layer restores expected visibility)
- Test(s) run: Source change in generation z policy (`render_core.py`)
- Change applied:
  - `_viewport_box_z_index(...)` now computes at the bottom of the owning layer band and steps one below order-0 button z.
  - Goal: preserve viewport region/hitbox presence without painting over viewport child button content in normal mode.
- Expected:
  - In normal mode, all 5 viewport buttons should be visible through the viewport region.
  - Clicking viewport region should still open viewport viewer.
  - Viewport-mode promotion (`vp-focus` / high z) should continue to work.
- Actual (user-confirmed after deploy):
  - FAIL: did not fix missing buttons.
  - Grey viewport overlay/signifier disappeared in normal mode.
  - Buttons are still missing.
- Match? (Yes/Partial/No): No
- Refinement decision:
  - Lowering viewport box z was a bad change.
  - `.vp-box` must remain on top as intentional product behavior.

### Iteration 8

- Theory tested: Raise viewport child button z globally to top tier while keeping `.vp-box` logic unchanged.
- Test(s) run: Code change deployed (`normal_vp_button_z = _Z_VP_FOCUS`).
- Expected:
  - Buttons visible and overlay/viewer trigger preserved.
- Actual (user-confirmed):
  - Half-fix: all buttons show.
  - Overlay signifier that opens viewer is missing.
  - Viewer cannot be opened.
- Match? (Yes/Partial/No): Partial
- Refinement decision:
  - Global z-promotion of lower-layer buttons broke project stacking contract and interaction.
  - Hard rule established: preserve layer precedence first; never jump lower-layer content to global top.

### Iteration 9

- Theory tested: Restore system after failed stacking changes.
- Test(s) run: Full rollback and redeploy to prior known-good commit.
- Actual:
  - Reverted to commit `00be6b28f2c87d5d8ae63a143579f54265a74747`.
  - Deploy transcript confirmed `RESULT:SUCCESS`.
- Refinement decision:
  - Continue from known-good baseline only.
  - Future attempts must keep `.vp-box` on top and respect per-layer z ordering.

## Next Theory Queue (not yet active)

- T2: Frame-selection defaults hide many controls outside viewer (`currentViewportIndexes`) and viewer workflow makes this less obvious.
- T3: Layer-visibility logic mismatch between owner layer and viewport sublayer creates apparent randomness.

