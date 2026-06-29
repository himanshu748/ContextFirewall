/* eslint-disable @next/next/no-img-element */

// Real brand logos of the stack ContextFirewall actually runs on.
// SVGs live in /public/logos (Cognee wordmark + Simple Icons marks, recolored).
const STACK = [
  { src: "/logos/neo4j.svg", label: "Neo4j" },
  { src: "/logos/postgresql.svg", label: "Postgres · pgvector" },
  { src: "/logos/huggingface.svg", label: "Hugging Face" },
  { src: "/logos/fastapi.svg", label: "FastAPI" },
  { src: "/logos/nextdotjs.svg", label: "Next.js" },
  { src: "/logos/vercel.svg", label: "Vercel" },
];

export function LogoStrip() {
  return (
    <section className="border-y border-ink-800/60 bg-ink-950/40">
      <div className="mx-auto max-w-6xl px-5 py-9">
        <p className="text-center text-[11px] font-medium uppercase tracking-[0.22em] text-slate-600">
          Runs on real infrastructure
        </p>
        <div className="mt-7 flex flex-wrap items-center justify-center gap-x-9 gap-y-6">
          <img
            src="/logos/cognee.svg"
            alt="Cognee"
            className="h-5 w-auto opacity-90 transition-opacity hover:opacity-100"
          />
          <span className="hidden h-5 w-px bg-ink-700 sm:block" aria-hidden />
          {STACK.map((s) => (
            <div
              key={s.label}
              className="flex items-center gap-2 opacity-70 transition-opacity hover:opacity-100"
            >
              <img src={s.src} alt={s.label} className="h-5 w-5" />
              <span className="text-sm font-medium text-slate-400">{s.label}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
