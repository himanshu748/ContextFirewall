"use client";

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

// Set these on Vercel (and in .env.local for dev):
//   NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
//   NEXT_PUBLIC_SUPABASE_ANON_KEY=<publishable / anon key>
const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

// When unset the console still runs in read-only demo mode (auth UI is hidden).
export const supabaseConfigured = Boolean(url && anonKey);

let client: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient | null {
  if (!supabaseConfigured) return null;
  if (!client) {
    client = createClient(url as string, anonKey as string, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    });
  }
  return client;
}
