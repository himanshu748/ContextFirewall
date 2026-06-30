-- Privacy lockdown: enable Row Level Security on every public table that lacks
-- it (the pre-existing Cognee tables + anything else), closing the hole where
-- the anon/publishable key could read or write them via PostgREST.
--
-- These tables are owned by `postgres`, and the backend connects as that owner.
-- Enabling RLS *without* FORCE and *without* policies denies the PostgREST
-- `anon`/`authenticated` roles while the table owner (the backend's direct
-- connection) and superusers continue to bypass RLS — so the Cognee runtime
-- keeps working untouched. No data is exposed to API-key clients.
--
-- Idempotent: re-running is a no-op for tables that already have RLS on. The
-- cf_* tables already have RLS + scoped policies from 0001 and are unaffected.

do $$
declare
  r record;
begin
  for r in
    select tablename
    from pg_tables
    where schemaname = 'public'
      and rowsecurity = false
  loop
    execute format('alter table public.%I enable row level security', r.tablename);
  end loop;
end $$;
