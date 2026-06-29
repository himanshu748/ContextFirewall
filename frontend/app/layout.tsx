import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono", display: "swap" });

const SITE = "https://contextfirewall.vercel.app";
const TITLE = "ContextFirewall — guardrails for the memory layer";
const DESC =
  "A trust firewall for AI coding-agent memory, built on Cognee. It audits every remembered fact for staleness, contradiction, secrets, and evidence — passing only what is trustworthy into the next agent's context.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE),
  title: TITLE,
  description: DESC,
  keywords: [
    "AI agents",
    "agent memory",
    "Cognee",
    "knowledge graph",
    "context engineering",
    "memory governance",
    "LLM",
    "RAG",
  ],
  authors: [{ name: "Himanshu Kumar", url: "https://github.com/himanshu748" }],
  openGraph: {
    title: TITLE,
    description: DESC,
    url: SITE,
    siteName: "ContextFirewall",
    type: "website",
    images: [
      {
        url: "/og.png",
        width: 1200,
        height: 630,
        alt: "ContextFirewall — guardrails for the memory layer",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: TITLE,
    description: DESC,
    images: ["/og.png"],
  },
  icons: { icon: "/icon.svg" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable}`}>
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
