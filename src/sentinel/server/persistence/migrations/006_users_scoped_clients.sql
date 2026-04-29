-- Users (commissioning console) and per-user client name uniqueness.

create table if not exists users (
  user_id uuid primary key,
  display_name text not null,
  created_at_utc timestamptz not null
);

insert into users (user_id, display_name, created_at_utc) values
  ('8a7e9c2d-5f41-4b9c-9c31-2b8f0e6d1a00', 'Jamie', now())
on conflict (user_id) do nothing;

alter table clients add column if not exists user_id uuid references users (user_id);

update clients set user_id = '8a7e9c2d-5f41-4b9c-9c31-2b8f0e6d1a00' where user_id is null;

alter table clients alter column user_id set not null;

drop index if exists clients_name_uq;

create unique index if not exists clients_user_id_name_uq on clients (user_id, name);

create index if not exists clients_user_id_idx on clients (user_id);
