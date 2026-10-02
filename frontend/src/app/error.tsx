"use client";

import { useEffect } from "react";

// Root error boundary. Bilingual because the locale may be the thing that failed.
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
    <div className="mx-auto max-w-xl px-4 py-24 text-center">
      <h1 className="mb-2 text-2xl font-bold text-brand-900">حدث خطأ غير متوقع</h1>
      <p className="mb-6 text-sand-700" lang="en" dir="ltr">
        Something went wrong.
      </p>
      <button
        type="button"
        onClick={reset}
        className="rounded-lg bg-brand-700 px-5 py-2 font-medium text-white hover:bg-brand-800"
      >
        إعادة المحاولة / Try again
      </button>
    </div>
  );
}
