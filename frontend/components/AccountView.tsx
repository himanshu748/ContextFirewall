"use client";

import { useState } from "react";
import {
  KeyRound,
  Plus,
  Copy,
  Check,
  Trash2,
  LogOut,
  Loader2,
  ShieldCheck,
  CircleUser,
  AlertTriangle,
} from "lucide-react";
import { useAuth } from "@/lib/auth";

function fmtDate(iso: string | null): string {
  if (!iso) return "never";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function AuthForms() {
  const { signInWithPassword, signUpWithPassword, signInWithGoogle } = useAuth();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    const res =
      mode === "signin"
        ? await signInWithPassword(email.trim(), password)
        : await signUpWithPassword(email.trim(), password);
    if (res.error) setErr(res.error);
    else if ("needsConfirmation" in res && res.needsConfirmation)
      setMsg("Check your inbox to confirm your email, then sign in.");
    setBusy(false);
  };

  return (
    <div className="mx-auto max-w-md rounded-2xl border border-ink-700 bg-ink-900/40 p-6">
      <div className="flex items-center gap-2 text-sm font-semibold text-slate-100">
        <CircleUser className="h-4 w-4 text-firewall-400" />
        {mode === "signin" ? "Sign in to ContextFirewall" : "Create your account"}
      </div>
      <p className="mt-1 text-xs text-slate-500">
        Get your own private memory namespace and API keys for the MCP server.
      </p>

      <button
        onClick={() => signInWithGoogle()}
        className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg border border-ink-700 bg-ink-850 px-3 py-2 text-sm font-medium text-slate-200 transition-colors hover:border-ink-600"
      >
        <svg className="h-4 w-4" viewBox="0 0 24 24" aria-hidden>
          <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.27-4.74 3.27-8.1Z" />
          <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.99.66-2.26 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23Z" />
          <path fill="#FBBC05" d="M5.84 14.1a6.6 6.6 0 0 1 0-4.2V7.06H2.18a11 11 0 0 0 0 9.88l3.66-2.84Z" />
          <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.46 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38Z" />
        </svg>
        Continue with Google
      </button>

      <div className="my-4 flex items-center gap-3 text-[11px] text-slate-600">
        <span className="h-px flex-1 bg-ink-700" /> or <span className="h-px flex-1 bg-ink-700" />
      </div>

      <div className="space-y-2">
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
          className="w-full rounded-md border border-ink-700 bg-ink-950 px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600 outline-none focus:border-firewall-500/50"
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          onKeyDown={(e) => e.key === "Enter" && submit()}
          className="w-full rounded-md border border-ink-700 bg-ink-950 px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600 outline-none focus:border-firewall-500/50"
        />
      </div>

      {err && <p className="mt-2 text-xs text-block">{err}</p>}
      {msg && <p className="mt-2 text-xs text-pass">{msg}</p>}

      <button
        onClick={submit}
        disabled={busy || !email || !password}
        className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg border border-firewall-500/30 bg-firewall-500/10 px-3 py-2 text-sm font-medium text-firewall-400 transition-colors hover:bg-firewall-500/15 disabled:opacity-50"
      >
        {busy && <Loader2 className="h-4 w-4 animate-spin" />}
        {mode === "signin" ? "Sign in" : "Create account"}
      </button>

      <button
        onClick={() => {
          setMode(mode === "signin" ? "signup" : "signin");
          setErr(null);
          setMsg(null);
        }}
        className="mt-3 w-full text-center text-xs text-slate-500 hover:text-slate-300"
      >
        {mode === "signin" ? "No account? Create one" : "Already have an account? Sign in"}
      </button>
    </div>
  );
}

function KeyManager() {
  const { user, profile, keys, activeKey, createKey, revokeKey, useKey, signOut } = useAuth();
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [justMinted, setJustMinted] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const liveKeys = keys.filter((k) => !k.revoked_at);

  const onCreate = async () => {
    setCreating(true);
    setErr(null);
    const res = await createKey(name.trim());
    if (res.error) setErr(res.error);
    else if (res.raw) setJustMinted(res.raw);
    setName("");
    setCreating(false);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-ink-700 bg-ink-900/40 p-5">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-100">
            <CircleUser className="h-4 w-4 text-firewall-400" /> {profile?.email ?? user?.email}
          </div>
          <div className="mt-1 text-xs text-slate-500">
            Your private namespace:{" "}
            <span className="font-mono text-firewall-400">{profile?.namespace ?? "…"}</span>
          </div>
        </div>
        <button
          onClick={() => signOut()}
          className="inline-flex items-center gap-1.5 rounded-lg border border-ink-700 bg-ink-850 px-3 py-1.5 text-xs font-medium text-slate-300 transition-colors hover:border-ink-600 hover:text-slate-100"
        >
          <LogOut className="h-3.5 w-3.5" /> Sign out
        </button>
      </div>

      <div className="rounded-2xl border border-ink-700 bg-ink-900/40 p-5">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-100">
          <KeyRound className="h-4 w-4 text-firewall-400" /> API keys
        </div>
        <p className="mt-1 text-xs text-slate-500">
          Use a key as <span className="font-mono">Authorization: Bearer cf_live_…</span> in your MCP
          client or REST calls. The full key is shown only once, at creation.
        </p>

        {justMinted && (
          <div className="mt-4 rounded-lg border border-pass-border/60 bg-pass-dim/40 p-3">
            <div className="text-[11px] font-medium uppercase tracking-wider text-pass">
              New key — copy it now, it won&apos;t be shown again
            </div>
            <div className="mt-2 flex items-center gap-2">
              <code className="flex-1 overflow-x-auto rounded-md border border-ink-700 bg-ink-950 px-3 py-2 font-mono text-[12px] text-slate-100">
                {justMinted}
              </code>
              <button
                onClick={() => {
                  navigator.clipboard?.writeText(justMinted).then(() => {
                    setCopied(true);
                    setTimeout(() => setCopied(false), 1400);
                  });
                }}
                className="inline-flex items-center gap-1 rounded-md border border-ink-700 bg-ink-850 px-2.5 py-2 text-[11px] text-slate-300 hover:text-slate-100"
              >
                {copied ? <Check className="h-3.5 w-3.5 text-pass" /> : <Copy className="h-3.5 w-3.5" />}
                {copied ? "copied" : "copy"}
              </button>
            </div>
            <button
              onClick={() => setJustMinted(null)}
              className="mt-2 text-[11px] text-slate-500 hover:text-slate-300"
            >
              Done
            </button>
          </div>
        )}

        <div className="mt-4 flex gap-2">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Key name (e.g. laptop, cursor)"
            onKeyDown={(e) => e.key === "Enter" && onCreate()}
            className="flex-1 rounded-md border border-ink-700 bg-ink-950 px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600 outline-none focus:border-firewall-500/50"
          />
          <button
            onClick={onCreate}
            disabled={creating}
            className="inline-flex items-center gap-1.5 rounded-lg border border-firewall-500/30 bg-firewall-500/10 px-3 py-2 text-sm font-medium text-firewall-400 transition-colors hover:bg-firewall-500/15 disabled:opacity-50"
          >
            {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            New key
          </button>
        </div>
        {err && <p className="mt-2 text-xs text-block">{err}</p>}

        <div className="mt-4 divide-y divide-ink-800">
          {liveKeys.length === 0 && (
            <p className="py-3 text-xs text-slate-500">No keys yet. Create one to enable writes.</p>
          )}
          {liveKeys.map((k) => {
            const isActive = activeKey.startsWith(k.key_prefix);
            return (
              <div key={k.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 text-sm text-slate-200">
                    <span className="font-mono">{k.key_prefix}…</span>
                    <span className="text-slate-500">{k.name}</span>
                    {isActive && (
                      <span className="inline-flex items-center gap-1 rounded border border-pass-border/60 bg-pass-dim/40 px-1.5 py-0.5 text-[10px] font-medium text-pass">
                        <ShieldCheck className="h-3 w-3" /> active
                      </span>
                    )}
                  </div>
                  <div className="mt-0.5 text-[11px] text-slate-500">
                    created {fmtDate(k.created_at)} · last used {fmtDate(k.last_used_at)}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {!isActive && (
                    <span className="text-[11px] text-slate-600" title="Only the full key can be set active; it is shown once at creation.">
                      paste to use
                    </span>
                  )}
                  <button
                    onClick={() => revokeKey(k.id)}
                    className="inline-flex items-center gap-1 rounded-md border border-ink-700 bg-ink-850 px-2 py-1 text-[11px] text-slate-400 transition-colors hover:border-block-border/60 hover:text-block"
                  >
                    <Trash2 className="h-3.5 w-3.5" /> Revoke
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        <div className="mt-4 flex items-start gap-2 rounded-lg border border-ink-700 bg-ink-950/60 p-3 text-[11px] text-slate-500">
          <KeyRound className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-500" />
          <span>
            Set a key active for this browser: paste a full <span className="font-mono">cf_live_…</span> value below.
            The console uses the active key to read and write your namespace.
            <PasteActive onUse={useKey} />
          </span>
        </div>
      </div>
    </div>
  );
}

function PasteActive({ onUse }: { onUse: (raw: string) => void }) {
  const [val, setVal] = useState("");
  return (
    <span className="mt-2 flex gap-2">
      <input
        value={val}
        onChange={(e) => setVal(e.target.value)}
        placeholder="cf_live_…"
        className="flex-1 rounded-md border border-ink-700 bg-ink-950 px-2.5 py-1.5 font-mono text-[11px] text-slate-200 placeholder:text-slate-600 outline-none focus:border-firewall-500/50"
      />
      <button
        onClick={() => val.trim() && onUse(val.trim())}
        className="rounded-md border border-firewall-500/30 bg-firewall-500/10 px-2.5 py-1.5 text-[11px] font-medium text-firewall-400 hover:bg-firewall-500/15"
      >
        Use
      </button>
    </span>
  );
}

export function AccountView() {
  const { configured, loading, user } = useAuth();

  if (!configured) {
    return (
      <div className="mx-auto max-w-md rounded-2xl border border-amber-500/30 bg-amber-500/[0.06] p-6">
        <div className="flex items-center gap-2 text-sm font-semibold text-amber-300">
          <AlertTriangle className="h-4 w-4" /> Auth not configured
        </div>
        <p className="mt-2 text-xs leading-relaxed text-slate-400">
          Set <span className="font-mono">NEXT_PUBLIC_SUPABASE_URL</span> and{" "}
          <span className="font-mono">NEXT_PUBLIC_SUPABASE_ANON_KEY</span> on the deployment to enable
          sign-in and per-account API keys. The console runs in read-only demo mode without them.
        </p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-16 text-sm text-slate-500">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading account…
      </div>
    );
  }

  return user ? <KeyManager /> : <AuthForms />;
}
