"use client";

import { useEffect, useRef, useState } from "react";

/**
 * <img> with progressive loading (fades in once decoded) that degrades to a
 * neutral placeholder when the file cannot be loaded, so pages never show a
 * broken image. Parents provide the background (bg-fill / skeleton).
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
  const [loaded, setLoaded] = useState(false);
  const ref = useRef<HTMLImageElement>(null);

  useEffect(() => {
    // Cached images may finish before hydration and never fire onLoad.
    const img = ref.current;
    if (img?.complete && img.naturalWidth > 0) setLoaded(true);
  }, [src]);

  if (failed) {
    return (
      <div
        role="img"
        aria-label={alt || fallbackLabel}
        className={`grid place-items-center bg-fill text-sm text-ink-3 ${className ?? ""}`}
      >
        {fallbackLabel}
      </div>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element -- media is served by our API
    <img
      ref={ref}
      src={src}
      alt={alt}
      loading={loading}
      decoding="async"
      data-loaded={loaded || undefined}
      className={`${className ?? ""} transition-opacity duration-[var(--duration-slow)] ${loaded ? "opacity-100" : "opacity-0"}`}
      onLoad={() => setLoaded(true)}
      onError={() => setFailed(true)}
    />
  );
}
