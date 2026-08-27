-- Per-project testing-type toggles. Missing row / empty array = all types ON
-- (today's required-target set). Off excludes the type from required work;
-- it does not auto-pass and does not hide drawn controls.

create table if not exists project_testing_type_settings (
  project_id uuid primary key references projects (project_id),
  disabled_types jsonb not null,
  updated_at_utc timestamptz not null
);
