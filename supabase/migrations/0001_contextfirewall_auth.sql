-- ContextFirewall multi-tenant auth: per-account namespace + hashed API keys.
--
-- Run this once against the "context firewall" Supabase project
-- (project ref: tmsfudajqumspruyssov) via the SQL editor or `supabase db push`.
--
-- Tables live in `public` with a `cf_` prefix so PostgREST exposes them to the
-- authenticated role without changing the project's exposed-schema setting.
-- A user only ever sees their own rows (RLS); raw API keys are never stored
-- (only their SHA-256), and the hash column is not selectable by clients.

create table if not exists public.cf_profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text,
  namespace text unique not null,
  created_at timestamptz not null default now()
);

create table if not exists public.cf_api_keys (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null default 'default',
  key_prefix text not null,
  key_hash text not null unique,
  namespace text not null,
  created_at timestamptz not null default now(),
  last_used_at timestamptz,
  revoked_at timestamptz
);
create index if not exists cf_api_keys_user_idx on public.cf_api_keys(user_id);
create index if not exists cf_api_keys_hash_idx on public.cf_api_keys(key_hash) where revoked_at is null;

-- Derive a stable, slug-safe namespace from the user id on signup.
create or replace function public.cf_handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.cf_profiles (id, email, namespace)
  values (new.id, new.email, 'u_' || substr(replace(new.id::text, '-', ''), 1, 12))
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists cf_on_auth_user_created on auth.users;
create trigger cf_on_auth_user_created
  after insert on auth.users
  for each row execute function public.cf_handle_new_user();

-- Mint a key: the raw key is returned exactly once; only its SHA-256 is stored.
create or replace function public.cf_create_api_key(p_name text default 'default')
returns text
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  v_ns text;
  v_raw text;
begin
  if auth.uid() is null then
    raise exception 'not authenticated';
  end if;
  select namespace into v_ns from public.cf_profiles where id = auth.uid();
  if v_ns is null then
    raise exception 'no profile for user';
  end if;
  v_raw := 'cf_live_' || encode(extensions.gen_random_bytes(24), 'hex');
  insert into public.cf_api_keys (user_id, name, key_prefix, key_hash, namespace)
  values (
    auth.uid(),
    coalesce(nullif(trim(p_name), ''), 'default'),
    substr(v_raw, 1, 16),
    encode(extensions.digest(v_raw, 'sha256'), 'hex'),
    v_ns
  );
  return v_raw;
end;
$$;

create or replace function public.cf_revoke_api_key(p_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.cf_api_keys
     set revoked_at = now()
   where id = p_id and user_id = auth.uid() and revoked_at is null;
end;
$$;

-- Row Level Security: a user only ever sees their own rows.
alter table public.cf_profiles enable row level security;
alter table public.cf_api_keys enable row level security;

drop policy if exists cf_profiles_self_select on public.cf_profiles;
create policy cf_profiles_self_select on public.cf_profiles
  for select using (auth.uid() = id);

drop policy if exists cf_api_keys_self_select on public.cf_api_keys;
create policy cf_api_keys_self_select on public.cf_api_keys
  for select using (auth.uid() = user_id);

-- Grants. No INSERT/UPDATE/DELETE for clients (handled by SECURITY DEFINER
-- functions), and the secret hash column is not selectable by clients.
grant usage on schema public to authenticated;
grant select on public.cf_profiles to authenticated;
grant select (id, user_id, name, key_prefix, namespace, created_at, last_used_at, revoked_at)
  on public.cf_api_keys to authenticated;
grant execute on function public.cf_create_api_key(text) to authenticated;
grant execute on function public.cf_revoke_api_key(uuid) to authenticated;
