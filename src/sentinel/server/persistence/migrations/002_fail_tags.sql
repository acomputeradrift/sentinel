-- FAIL task tagging for commissioning UI
-- Tag values are validated in application code.

create table if not exists fail_tags (
  project_id uuid not null references projects(project_id),
  target_key text not null,
  tag text not null,
  updated_at_utc timestamptz not null,
  primary key (project_id, target_key)
);

create index if not exists fail_tags_project_id_idx on fail_tags (project_id);

