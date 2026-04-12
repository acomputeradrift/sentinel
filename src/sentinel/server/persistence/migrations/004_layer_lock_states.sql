create table if not exists layer_lock_states (
  project_id uuid not null references projects(project_id),
  scope_key text not null,
  layer_key text not null,
  visible boolean not null,
  locked boolean not null,
  updated_at_utc timestamptz not null,
  primary key (project_id, scope_key, layer_key)
);

create index if not exists layer_lock_states_project_scope_idx
  on layer_lock_states (project_id, scope_key, updated_at_utc desc);
