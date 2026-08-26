-- Durable group-pass provenance on append-only test_results.
-- SINGLE rows (per-control Pass/Fail and popup Pass All) keep batch_id null.
-- GROUP rows from results/batch share one batch_id so snapshots can rebuild
-- a group pass after reconnect instead of looking like N walked singles.

alter table test_results add column if not exists batch_id uuid null;
alter table test_results add column if not exists source text not null default 'SINGLE';

create index if not exists test_results_project_batch_idx
  on test_results (project_id, batch_id)
  where batch_id is not null;
