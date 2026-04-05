# Temporary Fix Attempt Log

## Purpose
Track extraction-progress and timeout fix attempts, with explicit failure reasons.

## Working Rule (Active)
1. Read this document before each new iteration.
2. On any failure, append an entry immediately before continuing.
3. Keep entries factual: attempt, expected outcome, observed outcome, failure reason, next adjustment.

## Attempts

### Attempt 1
- Date/Time (UTC): 2026-04-05T00:00:00Z (placeholder)
- Goal: Improve extraction progress movement on large files.
- Change Summary: Added additional extraction heartbeat points.
- Expected: Progress bar visibly advances during long extraction windows.
- Observed: Bar still appeared stalled for long periods on large runs.
- Failure Reason: Integer percent quantization still collapsed many updates into same displayed value.
- Next Adjustment: Implement fractional progress end-to-end (extractor -> pipeline -> API/WS -> UI).

### Attempt 2
- Date/Time (UTC): 2026-04-05T00:00:00Z (placeholder)
- Goal: Verify large-file regenerate completion and collect duration evidence.
- Change Summary: Ran blocking full regenerate verification command from terminal.
- Expected: One-shot proof (duration, status, logs).
- Observed: Command repeatedly ran too long for interactive cycle and was aborted.
- Failure Reason: No guardrail for max command duration; verification method not broken into bounded phases.
- Next Adjustment: Break verification into smaller bounded checks with explicit max wait windows.

### Attempt 3
- Date/Time (UTC): 2026-04-05T18:30:00Z
- Goal: Validate current extraction behavior under large-file run.
- Change Summary: Bounded live-process and log inspection on deployed server.
- Expected: Single extraction process per project/upload and steady completion path.
- Observed:
  - Two concurrent `extract_project_data.py` processes running for the same project/upload.
  - Each process consuming ~50% CPU on a 1 vCPU host.
  - Long-lived extraction with repeated `generation_phase` publish events but no transition to generation for extended period.
- Failure Reason:
  - No single-flight guard for regenerate per project/upload allows overlapping heavy extraction runs.
  - Overlap can effectively double CPU contention and stretch wall-clock time far beyond normal baseline.
- Next Adjustment:
  - Add per-project regenerate lock/reject semantics (single active extraction/generation per project).
  - Add idempotency/debounce at API boundary for duplicate regenerate triggers.

### Attempt 4
- Date/Time (UTC): 2026-04-05T18:35:00Z
- Goal: Cleanup overlapping extraction processes safely.
- Change Summary: Tried multi-step remote cleanup scripts with complex shell quoting.
- Expected: Kill overlapping extractor processes in one scripted pass.
- Observed: Multiple command failures due quoting/line-ending issues in remote script execution.
- Failure Reason: Overly complex cross-shell command composition from PowerShell to remote bash.
- Next Adjustment: Use direct explicit PID kill + immediate process re-check (minimal command complexity).

### Attempt 5
- Date/Time (UTC): 2026-04-05T18:40:00Z
- Goal: Complete large-file extraction run cleanly.
- Change Summary: User-provided server failure log reviewed.
- Expected: Extraction exits normally and proceeds to generation.
- Observed: `Extraction failed: rc=-15` with progress reaching ~39% before termination.
- Failure Reason: Process received SIGTERM (manual/system termination), not extractor logic exception.
- Next Adjustment: Prevent overlapping/duplicate runs and avoid manual termination during active attempt; add single-flight guard.

### Attempt 6
- Date/Time (UTC): 2026-04-05T19:05:00Z
- Goal: Add regression proof for large-run guardrails before code changes.
- Change Summary: Added tests for (a) same-project parallel regenerate rejection and (b) tail-limited subprocess failure logging.
- Expected: Tests fail on current behavior and define target outcomes.
- Observed:
  - No single-flight guard: second regenerate call for same project did not raise.
  - Subprocess failure messages do not include `stdout_tail` or line-count metadata.
- Failure Reason:
  - `pipeline.regenerate_project` currently allows concurrent runs per project.
  - `_run_subprocess_with_progress` raises plain `CalledProcessError` without bounded/tail-focused diagnostics.
- Next Adjustment:
  - Add per-project in-process lock/active guard in `pipeline.regenerate_project`.
  - Add bounded stdout capture + structured failure summary (`stdout_lines`, `stdout_tail`, `stderr_tail`) in pipeline subprocess path.

### Attempt 7
- Date/Time (UTC): 2026-04-05T19:10:00Z
- Goal: Verify first pipeline fix pass against new tests.
- Change Summary: Implemented single-flight regenerate guard and subprocess tail-based failure summary in pipeline.
- Expected: Both new tests pass.
- Observed: Concurrency test passed; tail-summary test failed on assertion logic.
- Failure Reason: Test used substring `log-line-1`, which also matches `log-line-100+`.
- Next Adjustment: Use line-bounded assertion (`\nlog-line-1\n`) to validate omission of early lines without substring collision.

### Attempt 8
- Date/Time (UTC): 2026-04-05T19:12:00Z
- Goal: Validate improved large-run context logging for extraction/generation scripts.
- Change Summary: Added tests requiring input-size and output-unit context logs.
- Expected: Tests fail on current behavior and define required log content.
- Observed:
  - Extract logs missing `apex_size_bytes` and `contract_size_bytes`.
  - Generate logs missing `project_data_size_bytes`, `app_ui_size_bytes`, and render unit counts.
- Failure Reason: Script logging currently reports lifecycle checkpoints but not large-file diagnostic context metrics.
- Next Adjustment: Add structured key/value logging support and emit size/count metrics at script start.

### Attempt 9
- Date/Time (UTC): 2026-04-05T19:18:00Z
- Goal: Implement and verify large-run guardrails + logging improvements.
- Change Summary:
  - Added per-project single-flight regenerate guard in pipeline.
  - Added bounded subprocess failure summaries (`stdout_lines`, `stdout_tail`, `stderr_tail`).
  - Added structured key/value logging helper and emitted extraction/generation size + render-plan metrics.
- Expected: New and related regression tests pass.
- Observed:
  - New guard/log tests passed.
  - Full impacted regression suites passed (`test_extraction_progress_staging`, `test_server_commissioning_pipeline`).
- Failure Reason: none.
- Next Adjustment: none for this iteration.

### Attempt 10
- Date/Time (UTC): 2026-04-05T19:30:00Z
- Goal: Begin deployment commit step per runbook.
- Change Summary: Tried `git add ... && git commit ...` in PowerShell.
- Expected: Stage selected files and create commit.
- Observed: PowerShell parser error on `&&`.
- Failure Reason: Shell does not support `&&` separator.
- Next Adjustment: Use sequential commands with `;` and inspect exit status after each command.

### Attempt 11
- Date/Time (UTC): 2026-04-05T19:28:00Z
- Goal: Instrument real `Sung` extraction internals (`_resolve_button` / `_resolve_viewport_frames`) to find hotspot.
- Change Summary: Ran remote monkeypatch profiling script with early-stop sampling.
- Expected: Return per-button/per-viewport timing stats within bounded window.
- Observed:
  - Command timed out without usable profiler summary.
  - A malformed remote f-string (lost quotes) left a long-running shell process.
  - Another long-running app extraction process was also active at the same time.
- Failure Reason:
  - Quoting/escaping error in remote inline Python payload.
  - Concurrent active extractor processes invalidate clean single-run sampling.
- Next Adjustment:
  - Kill all active extraction/profiling processes first.
  - Re-run profiling using a safer script file approach (no complex nested quoting).

### Attempt 12
- Date/Time (UTC): 2026-04-05T19:35:00Z
- Goal: Capture SQL statement frequency during sampled `Sung` extraction.
- Change Summary: Tried inline remote heredoc SQL trace script over SSH.
- Expected: Return top repeated SQL statement shapes.
- Observed: Command failed immediately with `The string is missing the terminator: '`.
- Failure Reason: Nested quote termination in PowerShell->SSH command string.
- Next Adjustment: Write profiler script as a local file, copy with `scp`, execute remotely, then remove.

### Attempt 13
- Date/Time (UTC): 2026-04-05T19:42:00Z
- Goal: Determine why `Sung` appears bogged around 20–30% during extraction.
- Change Summary:
  - Ran bounded live extraction probe on exact file (`914deb03-...__Sung Residence v207.2.apex`) with timestamped progress.
  - Ran sampled function-timing probe on real extractor internals.
  - Ran sampled SQL trace frequency probe using copied script execution.
- Expected: Isolate concrete hotspot(s) with evidence.
- Observed:
  - Progress was continuous (not frozen), but very slow in work-stage: reached ~25.31% after 720s (terminated at timeout).
  - Sampled internals (2,500 buttons): `_resolve_button` avg ~135ms; `_resolve_viewport_frames` avg ~3.5s, max ~15.4s.
  - Sampled SQL top query: repeated `select MacroStepId from MacroStepsView where MacroId in (...)` (473 executions in 1,200-button sample), issued from per-button path in `_resolve_button`.
  - Repeated `select * from RTIDeviceButtonData where SharedLayerId = ?` also high frequency (194 executions in 1,200-button sample), consistent with viewport/page layer re-fetch overhead.
  - Workload magnitude from DB: non-viewport button passes ~24,310 + viewport child passes ~2,480 due shared-layer reuse across pages.
- Failure Reason: none (investigation succeeded).
- Next Adjustment:
  - Cache `macro_step_ids` per macro-id set (or per macro id union) instead of querying `MacroStepsView` per button.
  - Cache buttons-by-`SharedLayerId` (for both page and viewport loops) to avoid repeated `RTIDeviceButtonData` queries.
  - Add extractor stage diagnostics logging for work-unit totals and per-section timing so future regressions are visible immediately.
