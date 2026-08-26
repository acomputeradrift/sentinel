-- Named technicians belong to the commissioning operator (company stub user).
-- Tech links bind a named technician to a job. Result rows denormalize the
-- technician name so who survives revoke, rename, and re-upload.

create table if not exists technicians (
  technician_id uuid primary key,
  user_id uuid not null references users (user_id),
  name text not null,
  created_at_utc timestamptz not null
);

create unique index if not exists technicians_user_id_name_ci_uq
  on technicians (user_id, lower(name));

create index if not exists technicians_user_id_idx on technicians (user_id);

alter table tech_links add column if not exists technician_id uuid references technicians (technician_id);

create index if not exists tech_links_technician_id_idx on tech_links (technician_id);

alter table test_results add column if not exists recorded_by_technician_id uuid references technicians (technician_id);
alter table test_results add column if not exists recorded_by_technician_name text;
