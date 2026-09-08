-- Append-only File-tab changelog history. Survives upload-row prune
-- (v1 still keeps one .apex / one uploads row per project).

alter table projects
  add column if not exists changelog_history_json jsonb;
