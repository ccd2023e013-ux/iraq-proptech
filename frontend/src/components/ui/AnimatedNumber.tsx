"use client";

import { useEffect, useRef, useState } from "react";

import type { Locale } from "@/i18n/config";
import { formatPrice } from "@/lib/format";

/** Formats are named (not functions) so server components can pass them. */
export type NumberFormat = "integer" | "price-iqd" | "price-usd";

function render(n: number, as: NumberFormat, locale: Locale): string {
  if (as === "integer") {
    return Math.round(n).toLocaleString(locale === "ar" ? "ar-IQ-u-nu-latn" : "en-US");
  }
  return formatPrice(Math.round(n), as === "price-usd" ? "USD" : "IQD", locale) ?? "";
}

/**
 * A meaningful number that counts up once when it scrolls into view (900ms,
 * easing out), then stays still. The server renders the final value, so the
 * number is correct without JavaScript and under reduced motion.
 */
export function AnimatedNumber({
  value,
  as = "integer",
  locale,
  className,
}: {
  value: number;
  as?: NumberFormat;
  locale: Locale;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const [shown, setShown] = useState(value);

  useEffect(() => {
    const el = ref.current;
    if (!el || !Number.isFinite(value) || value === 0) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let frame = 0;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry?.isIntersecting) return;
        observer.disconnect();
        const start = performance.now();
        const tick = (now: number) => {
          const t = Math.min(1, (now - start) / 900);
          const eased = 1 - Math.pow(1 - t, 3);
          setShown(t < 1 ? value * eased : value);
          if (t < 1) frame = requestAnimationFrame(tick);
        };
        frame = requestAnimationFrame(tick);
      },
      { threshold: 0.6 },
    );
    observer.observe(el);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
    };
  }, [value]);

  return (
    <span ref={ref} className={`tabular ${className ?? ""}`}>
      {render(shown, as, locale)}
    </span>
  );
}
