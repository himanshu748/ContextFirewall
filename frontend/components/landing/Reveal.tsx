"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Reveals children with a subtle fade-up the first time they scroll into view.
 * Robust by design: a safety-net timer guarantees content is shown even when
 * IntersectionObserver never fires (off-screen in full-page screenshots, the
 * demo recording, prerender/SEO, or JS-light clients) so the page is never blank.
 */
export function Reveal({
  children,
  delay = 0,
  className = "",
}: {
  children: React.ReactNode;
  delay?: number;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let io: IntersectionObserver | null = null;
    const reveal = () => setShown(true);

    if (typeof IntersectionObserver !== "undefined") {
      io = new IntersectionObserver(
        (entries) => {
          entries.forEach((e) => {
            if (e.isIntersecting) {
              reveal();
              io?.disconnect();
            }
          });
        },
        { threshold: 0.12, rootMargin: "0px 0px -8% 0px" }
      );
      io.observe(el);
    } else {
      reveal();
    }

    const t = window.setTimeout(reveal, 900);
    return () => {
      io?.disconnect();
      window.clearTimeout(t);
    };
  }, []);

  return (
    <div
      ref={ref}
      className={`reveal ${shown ? "reveal-in" : ""} ${className}`}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </div>
  );
}
