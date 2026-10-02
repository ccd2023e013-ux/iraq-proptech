"use client";

import { useState } from "react";

import type { Media } from "@/types/property";

/** Accessible image gallery: large view + thumbnails (keyboard & touch friendly). */
export function Gallery({
  media,
  title,
  emptyLabel,
}: {
  media: Media[];
  title: string;
  emptyLabel: string;
}) {
  const images = media.filter((m) => m.kind !== "VIDEO");
  const videos = media.filter((m) => m.kind === "VIDEO");
  const [index, setIndex] = useState(0);
  const current = images[index];

  if (!images.length && !videos.length) {
    return (
      <div className="grid aspect-[16/9] place-items-center rounded-[var(--radius-card)] bg-sand-100 text-sand-500">
        {emptyLabel}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {current && (
        <div className="relative overflow-hidden rounded-[var(--radius-card)] bg-sand-100">
          {/* eslint-disable-next-line @next/next/no-img-element -- served by our API */}
          <img
            src={current.url}
            alt={current.caption ?? title}
            className="aspect-[16/10] w-full object-cover"
          />
          {images.length > 1 && (
            <>
              <button
                type="button"
                aria-label="‹"
                onClick={() => setIndex((index - 1 + images.length) % images.length)}
                className="absolute start-3 top-1/2 grid size-10 -translate-y-1/2 place-items-center rounded-full bg-white/90 text-xl shadow"
              >
                ‹
              </button>
              <button
                type="button"
                aria-label="›"
                onClick={() => setIndex((index + 1) % images.length)}
                className="absolute end-3 top-1/2 grid size-10 -translate-y-1/2 place-items-center rounded-full bg-white/90 text-xl shadow"
              >
                ›
              </button>
              <span className="absolute bottom-3 end-3 rounded-md bg-black/60 px-2 py-0.5 text-xs text-white tabular">
                {index + 1} / {images.length}
              </span>
            </>
          )}
        </div>
      )}
      {images.length > 1 && (
        <ul className="flex gap-2 overflow-x-auto pb-1">
          {images.map((m, i) => (
            <li key={m.id}>
              <button
                type="button"
                onClick={() => setIndex(i)}
                aria-current={i === index}
                className={`block overflow-hidden rounded-md border-2 ${i === index ? "border-brand-600" : "border-transparent"}`}
              >
                {/* eslint-disable-next-line @next/next/no-img-element -- served by our API */}
                <img src={m.thumbnail_url ?? m.url} alt="" className="h-16 w-24 object-cover" />
              </button>
            </li>
          ))}
        </ul>
      )}
      {videos.map((v) => (
        <video key={v.id} src={v.url} controls className="w-full rounded-[var(--radius-card)]" />
      ))}
    </div>
  );
}

export function ShareButton({ label, copied }: { label: string; copied: string }) {
  const [done, setDone] = useState(false);
  async function share() {
    const url = window.location.href;
    if (navigator.share) {
      await navigator.share({ url }).catch(() => undefined);
      return;
    }
    await navigator.clipboard?.writeText(url);
    setDone(true);
    setTimeout(() => setDone(false), 2000);
  }
  return (
    <button
      type="button"
      onClick={share}
      className="inline-flex items-center gap-2 rounded-lg border border-sand-200 px-4 py-2 text-sm font-medium hover:border-brand-300"
    >
      {done ? copied : label}
    </button>
  );
}
