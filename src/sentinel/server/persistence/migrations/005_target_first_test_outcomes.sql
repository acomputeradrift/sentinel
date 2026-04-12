-- Materialized first outcome per (project, target) for O(1) first-time-fail counts.
-- Maintained in append_test_result; historical rows backfilled on first count query.

create table if not exists target_first_test_outcomes (
  project_id uuid not null references projects(project_id) on delete cascade,
  target_key text not null,
  first_outcome text not null,
  first_test_result_id uuid not null references test_results(test_result_id) on delete cascade,
  first_recorded_at_utc timestamptz not null,
  primary key (project_id, target_key)
);

create index if not exists target_first_test_outcomes_project_fail_idx
  on target_first_test_outcomes (project_id)
  where first_outcome = 'FAIL';
