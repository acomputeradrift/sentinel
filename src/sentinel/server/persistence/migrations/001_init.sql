-- Sentinel persistence MVP (v1)
-- Notes:
-- - UUIDs are generated in application code (no DB extensions required).
-- - Tech tokens are stored hashed (sha256 hex), never as plaintext.

create table if not exists clients (
  client_id uuid primary key,
  name text not null,
  created_at_utc timestamptz not null
);

create unique index if not exists clients_name_uq on clients (name);

create table if not exists projects (
  project_id uuid primary key,
  client_id uuid not null references clients(client_id),
  name text not null,
  status text not null,
  created_at_utc timestamptz not null
);

create index if not exists projects_client_id_idx on projects (client_id);

create table if not exists tech_links (
  tech_link_id uuid primary key,
  project_id uuid not null references projects(project_id),
  label text null,
  created_at_utc timestamptz not null
);

create index if not exists tech_links_project_id_idx on tech_links (project_id);

create table if not exists tech_link_tokens (
  tech_link_token_id uuid primary key,
  tech_link_id uuid not null references tech_links(tech_link_id),
  token_hash text not null,
  issued_at_utc timestamptz not null,
  revoked_at_utc timestamptz null
);

create unique index if not exists tech_link_tokens_token_hash_uq on tech_link_tokens (token_hash);
create index if not exists tech_link_tokens_active_idx on tech_link_tokens (tech_link_id, revoked_at_utc);

create table if not exists generation_runs (
  generation_run_id uuid primary key,
  project_id uuid not null references projects(project_id),
  started_at_utc timestamptz not null
);

create index if not exists generation_runs_project_id_idx on generation_runs (project_id, started_at_utc desc);

create table if not exists test_results (
  test_result_id uuid primary key,
  project_id uuid not null references projects(project_id),
  generation_run_id uuid null references generation_runs(generation_run_id),
  recorded_at_utc timestamptz not null,
  recorded_by_role text not null,
  recorded_by_tech_link_id uuid null references tech_links(tech_link_id),
  target_key text not null,
  target_kind text not null,
  target_name text not null,
  refs jsonb not null,
  outcome text not null,
  fail_note text null
);

create index if not exists test_results_project_target_idx on test_results (project_id, target_key, recorded_at_utc desc);

