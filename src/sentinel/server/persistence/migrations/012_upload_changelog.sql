-- Persist last-file-vs-this-file changelog on the upload row.
-- v1 keeps one upload per project; this is the changelog for the load that replaced the previous file.

alter table uploads
  add column if not exists changelog_json jsonb;
