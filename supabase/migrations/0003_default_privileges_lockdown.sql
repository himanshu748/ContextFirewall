-- Durable lockdown: revoke PostgREST-role access to current AND FUTURE public
-- tables.
--
-- Why 0002 was not enough: Cognee's pipelines create and recreate tables at
-- runtime (every cognify run can mint new vector tables). 0002 enables RLS on
-- the tables that exist when it runs; tables created afterwards come up with
-- RLS disabled and default grants, silently re-exposing memory data to the
-- anon/publishable key via PostgREST. Revoking the roles' privileges — and the
-- default privileges for tables created later — closes the hole permanently,
-- regardless of RLS state on any individual table.
--
-- The backend is unaffected: it connects directly as the table owner, not
-- through PostgREST. The console's narrow client surface (cf_profiles and
-- cf_api_keys reads, both RLS-scoped to the signed-in user) is re-asserted
-- explicitly below.

revoke all on all tables in schema public from anon, authenticated;

alter default privileges for role postgres in schema public
  revoke all on tables from anon, authenticated;

-- Re-assert the intended client surface from 0001 (RLS still applies).
grant usage on schema public to authenticated;
grant select on public.cf_profiles to authenticated;
grant select (id, user_id, name, key_prefix, namespace, created_at, last_used_at, revoked_at)
  on public.cf_api_keys to authenticated;
