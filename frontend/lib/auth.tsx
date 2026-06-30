"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { User } from "@supabase/supabase-js";
import { getSupabase, supabaseConfigured } from "./supabase";
import {
  clearActiveApiKey,
  getActiveApiKey,
  setActiveApiKey,
  useActiveApiKey,
} from "./activeKey";

export interface ApiKeyRow {
  id: string;
  name: string;
  key_prefix: string;
  namespace: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}

export interface Profile {
  namespace: string;
  email: string | null;
}

interface AuthContextValue {
  configured: boolean;
  loading: boolean;
  user: User | null;
  profile: Profile | null;
  keys: ApiKeyRow[];
  activeKey: string;
  signInWithPassword: (email: string, password: string) => Promise<{ error?: string }>;
  signUpWithPassword: (
    email: string,
    password: string,
  ) => Promise<{ error?: string; needsConfirmation?: boolean }>;
  signOut: () => Promise<void>;
  createKey: (name: string) => Promise<{ raw?: string; error?: string }>;
  revokeKey: (id: string) => Promise<{ error?: string }>;
  useKey: (raw: string) => void;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [keys, setKeys] = useState<ApiKeyRow[]>([]);
  const [loading, setLoading] = useState(supabaseConfigured);
  const activeKey = useActiveApiKey();

  const loadAccount = useCallback(async (u: User | null) => {
    const supabase = getSupabase();
    if (!supabase || !u) {
      setProfile(null);
      setKeys([]);
      return;
    }
    const [{ data: prof }, { data: keyRows }] = await Promise.all([
      supabase.from("cf_profiles").select("namespace, email").eq("id", u.id).maybeSingle(),
      supabase
        .from("cf_api_keys")
        .select("id, name, key_prefix, namespace, created_at, last_used_at, revoked_at")
        .order("created_at", { ascending: false }),
    ]);
    setProfile(prof ? { namespace: prof.namespace as string, email: (prof.email as string) ?? u.email ?? null } : null);
    setKeys((keyRows as ApiKeyRow[]) ?? []);
  }, []);

  useEffect(() => {
    const supabase = getSupabase();
    if (!supabase) {
      setLoading(false);
      return;
    }
    let active = true;
    supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      const u = data.session?.user ?? null;
      setUser(u);
      loadAccount(u).finally(() => active && setLoading(false));
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_event, session) => {
      const u = session?.user ?? null;
      setUser(u);
      loadAccount(u);
      if (!u) clearActiveApiKey();
    });
    return () => {
      active = false;
      sub.subscription.unsubscribe();
    };
  }, [loadAccount]);

  const refresh = useCallback(async () => {
    await loadAccount(user);
  }, [loadAccount, user]);

  const signInWithPassword = useCallback(async (email: string, password: string) => {
    const supabase = getSupabase();
    if (!supabase) return { error: "Auth is not configured." };
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    return error ? { error: error.message } : {};
  }, []);

  const signUpWithPassword = useCallback(async (email: string, password: string) => {
    const supabase = getSupabase();
    if (!supabase) return { error: "Auth is not configured." };
    const { data, error } = await supabase.auth.signUp({ email, password });
    if (error) return { error: error.message };
    // When email confirmation is on, there is no active session yet.
    return { needsConfirmation: !data.session };
  }, []);

  const signOut = useCallback(async () => {
    const supabase = getSupabase();
    clearActiveApiKey();
    if (supabase) await supabase.auth.signOut();
    setUser(null);
    setProfile(null);
    setKeys([]);
  }, []);

  const createKey = useCallback(
    async (name: string) => {
      const supabase = getSupabase();
      if (!supabase) return { error: "Auth is not configured." };
      const { data, error } = await supabase.rpc("cf_create_api_key", { p_name: name || "default" });
      if (error) return { error: error.message };
      const raw = data as string;
      setActiveApiKey(raw);
      await refresh();
      return { raw };
    },
    [refresh],
  );

  const revokeKey = useCallback(
    async (id: string) => {
      const supabase = getSupabase();
      if (!supabase) return { error: "Auth is not configured." };
      const { error } = await supabase.rpc("cf_revoke_api_key", { p_id: id });
      if (error) return { error: error.message };
      await refresh();
      return {};
    },
    [refresh],
  );

  const useKey = useCallback((raw: string) => setActiveApiKey(raw), []);

  const value = useMemo<AuthContextValue>(
    () => ({
      configured: supabaseConfigured,
      loading,
      user,
      profile,
      keys,
      activeKey,
      signInWithPassword,
      signUpWithPassword,
      signOut,
      createKey,
      revokeKey,
      useKey,
      refresh,
    }),
    [loading, user, profile, keys, activeKey, signInWithPassword, signUpWithPassword, signOut, createKey, revokeKey, useKey, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}

export { getActiveApiKey };
