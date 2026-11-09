import assert from "node:assert/strict";
import test from "node:test";

process.env.NODE_ENV = "production";
process.env.NEXT_PUBLIC_API_URL = "https://api.example.test/v1";
process.env.NEXT_PUBLIC_SUPABASE_URL = "https://tenant.supabase.co";
const { default: nextConfig } = await import("../next.config.mjs");

test("response security headers cover all routes and trusted origins", async () => {
  const rules = await nextConfig.headers();
  assert.equal(rules.length, 1);
  assert.equal(rules[0].source, "/(.*)");
  const headers = Object.fromEntries(rules[0].headers.map(({ key, value }) => [key, value]));
  assert.equal(headers["X-Frame-Options"], "DENY");
  assert.equal(headers["X-Content-Type-Options"], "nosniff");
  assert.match(headers["Permissions-Policy"], /camera=\(\)/);
  assert.match(headers["Content-Security-Policy"], /frame-ancestors 'none'/);
  assert.match(headers["Content-Security-Policy"], /connect-src 'self' https:\/\/api\.example\.test https:\/\/tenant\.supabase\.co wss:\/\/tenant\.supabase\.co/);
  assert.doesNotMatch(headers["Content-Security-Policy"], /unsafe-eval/);
});
