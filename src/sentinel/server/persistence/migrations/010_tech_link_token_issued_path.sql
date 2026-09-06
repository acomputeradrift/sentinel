-- Persist the last issued technician path so commissioning/management can
-- re-display the live /testing/{token} URL without rotating.

alter table tech_link_tokens add column if not exists issued_path text;
