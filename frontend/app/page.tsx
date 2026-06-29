import Link from "next/link";
import {
  ShieldHalf,
  ArrowRight,
  Github,
  Clock,
  GitCompare,
  KeyRound,
  FileSearch,
  Database,
  Search,
  Sparkles,
  Trash2,
  History,
  Boxes,
  ScanSearch,
  PackageCheck,
  CheckCircle2,
  XCircle,
  Network,
} from "lucide-react";
import { LiveBadge } from "@/components/landing/LiveBadge";
import { Reveal } from "@/components/landing/Reveal";
import { LogoStrip } from "@/components/landing/LogoStrip";

type Icon = React.ComponentType<{ className?: string }>;
type Tone = "block" | "pass" | "warn" | "firewall";

const REPO = "https://github.com/himanshu748/ContextFirewall";

const tone: Record<Tone, { text: string; border: string; bg: string; dot: string }> = {
  block: { text: "text-block", border: "border-block-border", bg: "bg-block-dim", dot: "bg-block" },
  pass: { text: "text-pass", border: "border-pass-border", bg: "bg-pass-dim", dot: "bg-pass" },
  warn: { text: "text-warn", border: "border-warn-border", bg: "bg-warn-dim", dot: "bg-warn" },
  firewall: { text: "text-firewall-400", border: "border-firewall-600/40", bg: "bg-firewall-500/10", dot: "bg-firewall-400" },
};

const failures: { tag: string; icon: Icon; tone: Tone; text: string }[] = [
  { tag: "Stale", icon: Clock, tone: "warn", text: "“Deploy with flyctl deploy.” Retired when the service moved off Fly.io." },
  { tag: "Contradicted", icon: GitCompare, tone: "block", text: "“JWT access tokens never expire.” Disproven by the incident postmortem." },
  { tag: "Secret", icon: KeyRound, tone: "block", text: "An AWS access key pasted into a worker-config note." },
  { tag: "Unsupported", icon: FileSearch, tone: "warn", text: "“/search does 1,000,000 req/s, no cache.” Nothing backs it. Trust 0.10." },
];

const steps: { n: string; icon: Icon; name: string; desc: string }[] = [
  { n: "01", icon: History, name: "Record", desc: "Agent sessions (prompts, tool calls, terminal output, decisions, errors and fixes) are captured as a timeline." },
  { n: "02", icon: Boxes, name: "Cognify", desc: "Cognee extracts entities and relationships into a knowledge graph, with temporal links between facts." },
  { n: "03", icon: ScanSearch, name: "Audit", desc: "Every candidate memory is scored against four checks and given a plain-language verdict and trust score." },
  { n: "04", icon: PackageCheck, name: "Pack", desc: "Only memories that pass every check are assembled into a trusted context pack for the next agent." },
];

const checks: { icon: Icon; name: string; tone: Tone; tag: string; desc: string }[] = [
  { icon: Clock, name: "Staleness", tone: "warn", tag: "temporal", desc: "Facts have a shelf life. When a newer memory supersedes an old one, the stale fact decays and is held back from the pack." },
  { icon: GitCompare, name: "Contradiction", tone: "block", tag: "graph reasoning", desc: "The graph surfaces memories that conflict. The better-supported fact wins; the contradicted one is flagged, never silently served." },
  { icon: KeyRound, name: "Secrets", tone: "block", tag: "leak prevention", desc: "API keys, tokens and connection strings are detected and blocked before they can ever be packed into an agent's context." },
  { icon: FileSearch, name: "Evidence & trust", tone: "pass", tag: "provenance", desc: "Claims with no supporting events score low. Unsupported “facts” fall below the trust threshold and don't make the cut." },
];

const lifecycle: { icon: Icon; verb: string; api: string; desc: string }[] = [
  { icon: Database, verb: "remember", api: "add + cognify", desc: "Sessions are ingested and cognified into the knowledge graph." },
  { icon: Search, verb: "recall", api: "search", desc: "Relevant memories are retrieved for the agent's current task." },
  { icon: Sparkles, verb: "improve", api: "memify", desc: "Recurring lessons and coding rules are distilled and reinforced." },
  { icon: Trash2, verb: "forget", api: "governed delete", desc: "Rejected, stale or unsafe memories are removed under human review." },
];

export default function Landing() {
  return (
    <main className="relative min-h-screen overflow-hidden">
      {/* backdrop grid */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[640px] cf-grid" aria-hidden />

      {/* ---------------- Nav ---------------- */}
      <header className="sticky top-0 z-40 border-b border-ink-800/70 bg-ink-950/70 backdrop-blur">
        <nav className="mx-auto flex max-w-6xl items-center justify-between px-5 py-3.5">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-firewall-600/40 bg-firewall-500/10 text-firewall-400">
              <ShieldHalf className="h-4 w-4" />
            </div>
            <div className="text-sm font-semibold tracking-tight text-slate-100">ContextFirewall</div>
          </div>
          <div className="hidden items-center gap-7 text-sm text-slate-400 md:flex">
            <a href="#how" className="transition-colors hover:text-slate-100">How it works</a>
            <a href="#checks" className="transition-colors hover:text-slate-100">The four checks</a>
            <a href="#cognee" className="transition-colors hover:text-slate-100">Cognee</a>
            <a href={REPO} target="_blank" rel="noopener noreferrer" className="transition-colors hover:text-slate-100">GitHub</a>
          </div>
          <Link
            href="/app"
            className="group inline-flex items-center gap-1.5 rounded-lg bg-firewall-500 px-3.5 py-2 text-sm font-medium text-ink-950 transition-colors hover:bg-firewall-400"
          >
            Open the console
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </nav>
      </header>

      {/* ---------------- Hero ---------------- */}
      <section className="relative mx-auto max-w-6xl px-5 pt-20 pb-16 sm:pt-28">
        <div className="mx-auto max-w-3xl text-center">
          <div className="reveal reveal-in mb-6 inline-flex items-center gap-2 rounded-full border border-ink-700 bg-ink-900/60 px-3 py-1 text-xs text-slate-400">
            <span className="h-1.5 w-1.5 rounded-full bg-firewall-400" />
            Memory governance for AI coding agents · built on Cognee
          </div>
          <h1 className="cf-gradient-text text-balance text-4xl font-semibold leading-[1.08] tracking-tight sm:text-6xl">
            Every remembered fact is audited before it reaches the next agent.
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-pretty text-base leading-relaxed text-slate-400 sm:text-lg">
            An AI agent is only as safe as the memory it inherits. ContextFirewall records agent sessions into a
            Cognee knowledge graph, then audits every fact for <span className="text-slate-200">staleness</span>,{" "}
            <span className="text-slate-200">contradiction</span>, <span className="text-slate-200">secrets</span> and{" "}
            <span className="text-slate-200">evidence</span>, passing only what is trustworthy into the next agent's context.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link
              href="/app"
              className="group inline-flex w-full items-center justify-center gap-2 rounded-xl bg-firewall-500 px-5 py-3 text-sm font-semibold text-ink-950 transition-colors hover:bg-firewall-400 sm:w-auto"
            >
              Open the console
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
            <a
              href={REPO}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-ink-700 bg-ink-900/60 px-5 py-3 text-sm font-semibold text-slate-200 transition-colors hover:border-ink-600 hover:bg-ink-850 sm:w-auto"
            >
              <Github className="h-4 w-4" /> View source
            </a>
          </div>
          <div className="mt-6 flex justify-center">
            <LiveBadge />
          </div>
        </div>

        {/* Hero firewall panel */}
        <Reveal className="mx-auto mt-16 max-w-3xl" delay={120}>
          <div className="cf-glow-ring overflow-hidden rounded-2xl border border-ink-700 bg-ink-900/70">
            <div className="flex items-center gap-2 border-b border-ink-800 px-4 py-2.5">
              <span className="h-2.5 w-2.5 rounded-full bg-block/60" />
              <span className="h-2.5 w-2.5 rounded-full bg-warn/60" />
              <span className="h-2.5 w-2.5 rounded-full bg-pass/60" />
              <span className="ml-2 font-mono text-xs text-slate-500">context-firewall · audit</span>
              <span className="ml-auto inline-flex items-center gap-1.5 rounded-md border border-firewall-600/40 bg-firewall-500/10 px-2 py-0.5 text-[11px] text-firewall-400">
                <ScanSearch className="h-3 w-3" /> auditing 10 memories
              </span>
            </div>
            <div className="cf-scan grid gap-3 p-4 sm:grid-cols-2">
              {/* blocked */}
              <div className="space-y-3">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-block/80">Blocked at the firewall</div>
                <PanelRow tone="block" icon={XCircle} label="Stale" trust={0.5}
                  text="Deploy command superseded by make release." />
                <PanelRow tone="block" icon={KeyRound} label="Secret" trust={0.9}
                  text="AWS access key found in a worker-config note." />
                <PanelRow tone="block" icon={GitCompare} label="Contradicted" trust={0.45}
                  text="“Access tokens never expire,” later disproven." />
              </div>
              {/* passed */}
              <div className="space-y-3">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-pass/80">Passed into the pack</div>
                <PanelRow tone="pass" icon={CheckCircle2} label="Decision" trust={0.99}
                  text="Deploy with make release (migrations + blue-green)." />
                <PanelRow tone="pass" icon={CheckCircle2} label="Config" trust={0.92}
                  text="Service targets Python 3.12 (asyncpg 0.30)." />
                <PanelRow tone="pass" icon={CheckCircle2} label="Lesson" trust={0.77}
                  text="Run make check before pushing (CI gate)." />
              </div>
            </div>
          </div>
        </Reveal>
      </section>

      {/* ---------------- Logos ---------------- */}
      <LogoStrip />

      {/* ---------------- Problem ---------------- */}
      <section className="mx-auto max-w-6xl px-5 py-24">
        <Reveal>
          <p className="text-sm font-semibold uppercase tracking-wider text-firewall-400">The problem</p>
          <h2 className="mt-3 max-w-2xl text-3xl font-semibold tracking-tight text-slate-100 sm:text-4xl">
            Memory is a new attack surface for agents.
          </h2>
          <p className="mt-4 max-w-2xl text-base leading-relaxed text-slate-400">
            Hand an agent your team's accumulated memory and it will confidently act on a stale deploy command, a fix
            that was later contradicted, a leaked API key, or a claim nothing ever supported. Plain recall can't tell
            good memory from dangerous memory, so it serves all of it.
          </p>
        </Reveal>
        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {failures.map((f, i) => {
            const t = tone[f.tone];
            return (
              <Reveal key={f.tag} delay={i * 70}>
                <div className={`h-full rounded-xl border ${t.border} ${t.bg} p-5`}>
                  <div className={`mb-3 inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider ${t.text}`}>
                    <f.icon className="h-3.5 w-3.5" /> {f.tag}
                  </div>
                  <p className="text-sm leading-relaxed text-slate-300">{f.text}</p>
                </div>
              </Reveal>
            );
          })}
        </div>
      </section>

      {/* ---------------- How it works ---------------- */}
      <section id="how" className="border-t border-ink-800/60 bg-ink-950/40">
        <div className="mx-auto max-w-6xl px-5 py-24">
          <Reveal>
            <p className="text-sm font-semibold uppercase tracking-wider text-firewall-400">How it works</p>
            <h2 className="mt-3 max-w-2xl text-3xl font-semibold tracking-tight text-slate-100 sm:text-4xl">
              A firewall between memory and action.
            </h2>
          </Reveal>
          <div className="mt-12 grid gap-px overflow-hidden rounded-2xl border border-ink-700 bg-ink-800 sm:grid-cols-2 lg:grid-cols-4">
            {steps.map((s, i) => (
              <Reveal key={s.n} delay={i * 80} className="h-full">
                <div className="flex h-full flex-col gap-3 bg-ink-900/80 p-6">
                  <div className="flex items-center justify-between">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-firewall-600/40 bg-firewall-500/10 text-firewall-400">
                      <s.icon className="h-5 w-5" />
                    </div>
                    <span className="font-mono text-xs text-slate-600">{s.n}</span>
                  </div>
                  <div className="text-base font-semibold text-slate-100">{s.name}</div>
                  <p className="text-sm leading-relaxed text-slate-400">{s.desc}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ---------------- The four checks ---------------- */}
      <section id="checks" className="mx-auto max-w-6xl px-5 py-24">
        <Reveal>
          <p className="text-sm font-semibold uppercase tracking-wider text-firewall-400">The four checks</p>
          <h2 className="mt-3 max-w-2xl text-3xl font-semibold tracking-tight text-slate-100 sm:text-4xl">
            Four checks stand between a memory and your agent.
          </h2>
          <p className="mt-4 max-w-2xl text-base leading-relaxed text-slate-400">
            Each memory gets a verdict and a trust score in plain language, so a human can see exactly why something
            was blocked, and forget it for good.
          </p>
        </Reveal>
        <div className="mt-10 grid gap-4 md:grid-cols-2">
          {checks.map((c, i) => {
            const t = tone[c.tone];
            return (
              <Reveal key={c.name} delay={i * 70}>
                <div className="group h-full rounded-2xl border border-ink-700 bg-ink-900/50 p-6 transition-colors hover:border-ink-600">
                  <div className="flex items-start justify-between">
                    <div className={`flex h-11 w-11 items-center justify-center rounded-xl border ${t.border} ${t.bg} ${t.text}`}>
                      <c.icon className="h-5 w-5" />
                    </div>
                    <span className={`rounded-full border ${t.border} ${t.bg} px-2.5 py-0.5 text-[11px] ${t.text}`}>{c.tag}</span>
                  </div>
                  <h3 className="mt-4 text-lg font-semibold text-slate-100">{c.name}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-400">{c.desc}</p>
                </div>
              </Reveal>
            );
          })}
        </div>
      </section>

      {/* ---------------- Cognee lifecycle ---------------- */}
      <section id="cognee" className="border-y border-ink-800/60 bg-gradient-to-b from-ink-950/40 to-ink-900/20">
        <div className="mx-auto max-w-6xl px-5 py-24">
          <Reveal>
            <p className="text-sm font-semibold uppercase tracking-wider text-firewall-400">Built on Cognee</p>
            <h2 className="mt-3 max-w-3xl text-3xl font-semibold tracking-tight text-slate-100 sm:text-4xl">
              The full memory lifecycle, including <span className="font-mono text-firewall-400">forget()</span>.
            </h2>
            <p className="mt-4 max-w-2xl text-base leading-relaxed text-slate-400">
              ContextFirewall doesn't just read from Cognee; it exercises the whole lifecycle. Governance lives in
              the loop: nothing is permanent until it has earned trust, and anything unsafe can be forgotten.
            </p>
          </Reveal>
          <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {lifecycle.map((l, i) => (
              <Reveal key={l.verb} delay={i * 80} className="h-full">
                <div className="relative h-full rounded-2xl border border-ink-700 bg-ink-900/60 p-6">
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-firewall-600/40 bg-firewall-500/10 text-firewall-400">
                    <l.icon className="h-5 w-5" />
                  </div>
                  <div className="mt-4 font-mono text-sm font-semibold text-slate-100">{l.verb}()</div>
                  <div className="mt-0.5 font-mono text-[11px] text-firewall-400/80">{l.api}</div>
                  <p className="mt-2 text-sm leading-relaxed text-slate-400">{l.desc}</p>
                  {i < lifecycle.length - 1 && (
                    <ArrowRight className="absolute -right-3 top-1/2 hidden h-5 w-5 -translate-y-1/2 text-ink-600 lg:block" />
                  )}
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ---------------- Before / After ---------------- */}
      <section className="mx-auto max-w-6xl px-5 py-24">
        <Reveal>
          <h2 className="max-w-2xl text-3xl font-semibold tracking-tight text-slate-100 sm:text-4xl">
            Same question. Two very different answers.
          </h2>
          <p className="mt-4 max-w-2xl text-base leading-relaxed text-slate-400">
            “What should a new agent know before working on taskflow-api?” Asked of raw recall, then of the firewall.
          </p>
        </Reveal>
        <div className="mt-10 grid gap-4 lg:grid-cols-2">
          <Reveal>
            <div className="h-full rounded-2xl border border-block-border/60 bg-block-dim/30 p-6">
              <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-block">
                <XCircle className="h-4 w-4" /> Ungoverned recall
              </div>
              <ul className="space-y-2.5 text-sm text-slate-400">
                <li className="rounded-lg border-l-2 border-block/50 bg-block/5 px-3 py-2">Deploy with <span className="font-mono text-slate-300">flyctl deploy</span> <span className="text-block">· stale</span></li>
                <li className="rounded-lg border-l-2 border-block/50 bg-block/5 px-3 py-2">Use AWS key <span className="font-mono text-slate-300">AKIA••••••</span> for uploads <span className="text-block">· leaked secret</span></li>
                <li className="rounded-lg border-l-2 border-block/50 bg-block/5 px-3 py-2">Access tokens never expire <span className="text-block">· contradicted</span></li>
                <li className="rounded-lg border-l-2 border-block/50 bg-block/5 px-3 py-2">/search does 1M req/s, no cache <span className="text-block">· unsupported</span></li>
              </ul>
              <p className="mt-4 text-xs text-slate-500">A flat vector store hands all of this to the next agent.</p>
            </div>
          </Reveal>
          <Reveal delay={100}>
            <div className="h-full rounded-2xl border border-pass-border/60 bg-pass-dim/30 p-6">
              <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-pass">
                <CheckCircle2 className="h-4 w-4" /> Trusted context pack
              </div>
              <ul className="space-y-2.5 text-sm text-slate-300">
                <li className="rounded-lg border-l-2 border-pass/50 bg-pass/5 px-3 py-2">Deploy with <span className="font-mono">make release</span> (migrations + blue-green) <span className="text-pass">· trust 0.99</span></li>
                <li className="rounded-lg border-l-2 border-pass/50 bg-pass/5 px-3 py-2">Access tokens expire after 15 min; use the refresh flow <span className="text-pass">· trust 0.99</span></li>
                <li className="rounded-lg border-l-2 border-pass/50 bg-pass/5 px-3 py-2">Rate-limit 100 req/min per key in Redis <span className="text-pass">· trust 0.77</span></li>
              </ul>
              <p className="mt-4 text-xs text-slate-500">Only audited, current, evidence-backed facts. No secrets.</p>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ---------------- Why a graph ---------------- */}
      <section className="border-t border-ink-800/60 bg-ink-950/40">
        <div className="mx-auto max-w-4xl px-5 py-24 text-center">
          <Reveal>
            <Network className="mx-auto h-8 w-8 text-firewall-400" />
            <p className="mx-auto mt-6 max-w-3xl text-balance text-2xl font-medium leading-snug text-slate-200 sm:text-3xl">
              Why a knowledge graph? Because trust is relational and temporal. Cognee lets the firewall see{" "}
              <span className="cf-accent-text">when a fact was superseded</span> and{" "}
              <span className="cf-accent-text">which memories contradict each other</span>. These are judgments a flat
              vector store can't make.
            </p>
          </Reveal>
        </div>
      </section>

      {/* ---------------- Final CTA ---------------- */}
      <section className="mx-auto max-w-6xl px-5 py-24">
        <Reveal>
          <div className="cf-glow-ring relative overflow-hidden rounded-3xl border border-firewall-600/30 bg-gradient-to-br from-ink-900 to-ink-950 px-6 py-16 text-center sm:px-12">
            <div className="pointer-events-none absolute inset-0 cf-grid opacity-60" aria-hidden />
            <div className="relative">
              <h2 className="mx-auto max-w-2xl text-3xl font-semibold tracking-tight text-slate-100 sm:text-4xl">
                Put a firewall in front of your agents' memory.
              </h2>
              <p className="mx-auto mt-4 max-w-xl text-base text-slate-400">
                Open the console and watch every remembered fact get audited live on Cognee, before it reaches
                your next agent.
              </p>
              <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
                <Link
                  href="/app"
                  className="group inline-flex items-center justify-center gap-2 rounded-xl bg-firewall-500 px-6 py-3 text-sm font-semibold text-ink-950 transition-colors hover:bg-firewall-400"
                >
                  Open the console
                  <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                </Link>
                <a
                  href={REPO}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center justify-center gap-2 rounded-xl border border-ink-700 bg-ink-900/60 px-6 py-3 text-sm font-semibold text-slate-200 transition-colors hover:border-ink-600"
                >
                  <Github className="h-4 w-4" /> Read the code
                </a>
              </div>
            </div>
          </div>
        </Reveal>
      </section>

      {/* ---------------- Footer ---------------- */}
      <footer className="border-t border-ink-800">
        <div className="mx-auto flex max-w-6xl flex-col gap-6 px-5 py-10 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-firewall-600/40 bg-firewall-500/10 text-firewall-400">
              <ShieldHalf className="h-4 w-4" />
            </div>
            <div>
              <div className="text-sm font-semibold text-slate-200">ContextFirewall</div>
              <div className="-mt-0.5 text-[11px] text-slate-500">Guardrails for the memory layer</div>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-slate-400">
            <Link href="/app" className="transition-colors hover:text-slate-100">Live demo</Link>
            <a href={REPO} target="_blank" rel="noopener noreferrer" className="transition-colors hover:text-slate-100">GitHub</a>
            <a href="https://www.cognee.ai" target="_blank" rel="noopener noreferrer" className="transition-colors hover:text-slate-100">Cognee</a>
            <a href="https://wemakedevs.org/hackathons/cognee" target="_blank" rel="noopener noreferrer" className="transition-colors hover:text-slate-100">Hackathon</a>
          </div>
        </div>
        <div className="mx-auto max-w-6xl px-5 pb-10">
          <p className="text-xs leading-relaxed text-slate-600">
            Built by Himanshu Kumar for the WeMakeDevs × Cognee hackathon. Built with the help of an AI assistant
            (Hyperagent); every Cognee and model call shown is real, with no fabricated memories or results. The demo
            runs on a sample agent session (taskflow-api) so no private data is exposed.
          </p>
        </div>
      </footer>
    </main>
  );
}

function PanelRow({
  tone: toneKey,
  icon: RowIcon,
  label,
  text,
  trust,
}: {
  tone: Tone;
  icon: Icon;
  label: string;
  text: string;
  trust: number;
}) {
  const t = tone[toneKey];
  const pct = Math.round(trust * 100);
  return (
    <div className={`rounded-lg border ${t.border} ${t.bg} p-3`}>
      <div className="flex items-center justify-between">
        <div className={`inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider ${t.text}`}>
          <RowIcon className="h-3.5 w-3.5" /> {label}
        </div>
        <div className="font-mono text-[11px] text-slate-500">{trust.toFixed(2)}</div>
      </div>
      <p className="mt-1.5 text-xs leading-snug text-slate-300">{text}</p>
      <div className="mt-2 h-1 overflow-hidden rounded-full bg-ink-700">
        <div className={`h-full ${t.dot}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
