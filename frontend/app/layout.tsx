import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono", display: "swap" });

const SITE = "https://contextfirewall.vercel.app";
const OG_IMAGE =
  "https://pub.hyperagent.com/api/published/pbf01KW9H8BV2_2H7X0AF4RQ4X26GE/bf19b9bc-b42a-45ec-8683-9c582d91619a.png";
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
        url: OG_IMAGE,
        width: 1248,
        height: 832,
        alt: "ContextFirewall — guardrails for the memory layer",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: TITLE,
    description: DESC,
    images: [OG_IMAGE],
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
