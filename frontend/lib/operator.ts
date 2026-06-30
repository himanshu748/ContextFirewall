"use client";

import { useEffect, useState } from "react";

const STORAGE_KEY = "contextfirewall.operator";
const EVENT_NAME = "contextfirewall-operator-change";

export interface OperatorSettings {
  token: string;
  namespace: string;
}

const EMPTY: OperatorSettings = { token: "", namespace: "" };

function normalize(value: unknown): OperatorSettings {
  if (!value || typeof value !== "object") return EMPTY;
  const v = value as Record<string, unknown>;
  return {
    token: typeof v.token === "string" ? v.token : "",
    namespace: typeof v.namespace === "string" ? v.namespace.trim() : "",
  };
}

export function readOperatorSettings(): OperatorSettings {
  if (typeof window === "undefined") return EMPTY;
  try {
    return normalize(JSON.parse(localStorage.getItem(STORAGE_KEY) || "null"));
  } catch {
    return EMPTY;
  }
}

export function saveOperatorSettings(settings: OperatorSettings) {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  window.dispatchEvent(new Event(EVENT_NAME));
}

export function clearOperatorSettings() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(STORAGE_KEY);
  window.dispatchEvent(new Event(EVENT_NAME));
}

export function useOperatorSettings() {
  const [settings, setSettings] = useState<OperatorSettings>(EMPTY);

  useEffect(() => {
    const sync = () => setSettings(readOperatorSettings());
    sync();
    window.addEventListener("storage", sync);
    window.addEventListener(EVENT_NAME, sync);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener(EVENT_NAME, sync);
    };
  }, []);

  return settings;
}
