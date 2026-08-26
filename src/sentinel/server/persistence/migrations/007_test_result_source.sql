-- Provenance for how a result was recorded (individual click vs Pass All).
-- Append-only: each test_results row keeps its source for the life of the row.
-- target_first_test_outcomes is unchanged; join via first_test_result_id.

alter table test_results
  add column if not exists source text not null default 'INDIVIDUAL';

alter table test_results
  add column if not exists source_detail jsonb not null default '{}'::jsonb;

create index if not exists test_results_project_source_idx
  on test_results (project_id, source, recorded_at_utc desc);
