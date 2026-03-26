-- Persist project upload history and authoritative active upload pointer.

create table if not exists uploads (
  upload_id uuid primary key,
  project_id uuid not null references projects(project_id),
  original_filename text not null,
  storage_path text not null,
  uploaded_at_utc timestamptz not null
);

create index if not exists uploads_project_id_idx on uploads (project_id, uploaded_at_utc desc);

alter table projects
  add column if not exists active_upload_id uuid references uploads(upload_id);

