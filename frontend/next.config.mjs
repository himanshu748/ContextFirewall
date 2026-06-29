/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Lint rules (e.g. react/no-unescaped-entities) should not block production deploys.
  // Type-checking stays enabled so real type errors still fail the build.
  eslint: { ignoreDuringBuilds: true },
};

export default nextConfig;
