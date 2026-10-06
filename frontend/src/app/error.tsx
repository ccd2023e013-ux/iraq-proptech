"use client";

import Link from "next/link";
import { useEffect } from "react";

import { Icon } from "@/components/ui/Icon";
import { stagger } from "@/lib/motion";

// Root error boundary. Bilingual because the locale may be the thing that failed.
// Calm and actionable: what happened in plain words, then retry or go home.
// The technical reference (digest) is shown small for support, never the stack.
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="relative isolate mx-auto flex max-w-xl flex-col items-center px-4 py-24 text-center">
      <div aria-hidden className="stage-grid absolute inset-0 -z-10" />
      <div
        aria-hidden
        className="surface-1 reveal mb-6 grid size-14 place-items-center rounded-2xl"
      >
        <Icon name="alert" className="size-6 text-ink-2" />
      </div>
      <h1 className="reveal display-md text-ink" style={stagger(1)}>
        حدث خطأ غير متوقع
      </h1>
      <p className="reveal mt-2 text-ink-2" lang="en" dir="ltr" style={stagger(2)}>
        Something went wrong on our side. Your data is safe.
      </p>
      <div className="reveal mt-8 flex flex-wrap justify-center gap-2" style={stagger(3)}>
        <button
          type="button"
          onClick={reset}
          className="press inline-flex h-11 items-center gap-2 rounded-full bg-accent-fill px-5 font-medium text-on-accent hover:bg-accent-fill-hover"
        >
          <Icon name="refresh" className="size-4" />
          إعادة المحاولة / Try again
        </button>
        <Link
          href="/"
          className="press surface-1 inline-flex h-11 items-center gap-2 rounded-full px-5 font-medium text-ink"
        >
          الرئيسية / Home
        </Link>
      </div>
      {error.digest && (
        <p className="meta mt-6" dir="ltr">
          Ref: <span className="tabular">{error.digest}</span>
        </p>
      )}
    </div>
  );
}
