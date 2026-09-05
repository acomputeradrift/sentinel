-- Start-new-pass boundary. History rows stay; derived current state uses
-- results recorded at or after the latest pass started_at. Fail tags for the
-- ended pass are archived, not destroyed.

create table if not exists project_test_passes (
  test_pass_id uuid primary key,
  project_id uuid not null references projects (project_id),
  started_at_utc timestamptz not null,
  recorded_by_role text not null,
  recorded_by_user_id text,
  reason text,
  confirm_name text
);

create index if not exists project_test_passes_project_started_idx
  on project_test_passes (project_id, started_at_utc desc);

create table if not exists fail_tag_history (
  fail_tag_history_id uuid primary key,
  project_id uuid not null references projects (project_id),
  target_key text not null,
  tag text not null,
  updated_at_utc timestamptz not null,
  archived_at_utc timestamptz not null,
  test_pass_id uuid references project_test_passes (test_pass_id)
);

create index if not exists fail_tag_history_project_idx
  on fail_tag_history (project_id, archived_at_utc desc);
