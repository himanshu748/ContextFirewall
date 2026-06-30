"use client";

import { useEffect, useState } from "react";

// The active ContextFirewall API key (cf_live_...) the console uses to call the
// backend on the signed-in user's behalf. It is the user's *own* key, kept in
// localStorage so the SPA can attach it to requests; raw keys are never sent to
// or stored by our server (only their SHA-256 lives in Supabase).
const STORAGE_KEY = "contextfirewall.apikey";
const EVENT_NAME = "contextfirewall-apikey-change";

export function getActiveApiKey(): string {
  if (typeof window === "undefined") return "";
  try {
    return localStorage.getItem(STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

export function setActiveApiKey(key: string) {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, key);
  window.dispatchEvent(new Event(EVENT_NAME));
}

export function clearActiveApiKey() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(STORAGE_KEY);
  window.dispatchEvent(new Event(EVENT_NAME));
}

export function useActiveApiKey(): string {
  const [key, setKey] = useState("");
  useEffect(() => {
    const sync = () => setKey(getActiveApiKey());
    sync();
    window.addEventListener("storage", sync);
    window.addEventListener(EVENT_NAME, sync);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener(EVENT_NAME, sync);
    };
  }, []);
  return key;
}
