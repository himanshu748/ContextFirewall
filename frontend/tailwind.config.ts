import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-inter)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      colors: {
        ink: {
          950: "#08090c",
          900: "#0c0e13",
          850: "#11141b",
          800: "#161a23",
          700: "#1e2330",
          600: "#2a3040",
        },
        firewall: {
          // brand accent — a confident electric blue/cyan
          400: "#38bdf8",
          500: "#0ea5e9",
          600: "#0284c7",
        },
        pass: { DEFAULT: "#34d399", dim: "#10241d", border: "#1f5641" },
        block: { DEFAULT: "#fb7185", dim: "#2a1217", border: "#5e2230" },
        warn: { DEFAULT: "#fbbf24", dim: "#241c0c", border: "#5a4416" },
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(56,189,248,0.18), 0 8px 40px -12px rgba(56,189,248,0.25)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.4s ease-out both",
      },
    },
  },
  plugins: [],
};

export default config;
