"use client";

import { useState } from "react";

/**
 * <img> that degrades to a neutral placeholder when the file cannot be loaded
 * (storage unreachable, deleted object), so pages never show a broken image.
 */
export function SafeImage({
  src,
  alt,
  className,
  fallbackLabel,
  loading = "lazy",
}: {
  src: string;
  alt: string;
  className?: string;
  fallbackLabel: string;
  loading?: "lazy" | "eager";
}) {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return (
      <div
        role="img"
        aria-label={alt || fallbackLabel}
        className={`grid place-items-center bg-sand-100 text-sm text-sand-500 ${className ?? ""}`}
      >
        {fallbackLabel}
      </div>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element -- media is served by our API
    <img
      src={src}
      alt={alt}
      loading={loading}
      className={className}
      onError={() => setFailed(true)}
    />
  );
}
