create table if not exists idempotency_keys (
  scope text not null,
  idempotency_key text not null,
  response_json jsonb not null,
  created_at_utc timestamptz not null default now(),
  primary key (scope, idempotency_key)
);
