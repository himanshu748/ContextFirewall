function origin(value) {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:" ? url.origin : null;
  } catch {
    return null;
  }
}

const apiOrigin = origin(process.env.NEXT_PUBLIC_API_URL) || "http://localhost:8000";
const supabaseOrigin = origin(process.env.NEXT_PUBLIC_SUPABASE_URL);
const supabaseWebSocket = supabaseOrigin?.replace(/^http/, "ws");
const development = process.env.NODE_ENV !== "production";

const contentSecurityPolicy = [
  "default-src 'self'",
  // Next.js 14 emits inline hydration scripts; nonces require a separate
  // middleware/SSR migration. Never allow eval in production.
  `script-src 'self' 'unsafe-inline'${development ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https:",
  "font-src 'self' data:",
  `connect-src 'self' ${[apiOrigin, supabaseOrigin, supabaseWebSocket, ...(development ? ["ws:", "wss:"] : [])].filter(Boolean).join(" ")}`,
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Lint rules (e.g. react/no-unescaped-entities) should not block production deploys.
  // Type-checking stays enabled so real type errors still fail the build.
  eslint: { ignoreDuringBuilds: true },
  async headers() {
    return [{
      source: "/(.*)",
      headers: [
        { key: "Content-Security-Policy", value: contentSecurityPolicy },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
      ],
    }];
  },
};

export default nextConfig;
