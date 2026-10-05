"use client";

import { useState } from "react";

import { SafeImage } from "@/components/ui/SafeImage";
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
      <div className="grid aspect-[16/9] place-items-center rounded-[var(--radius-media)] bg-fill text-sand-500">
        {emptyLabel}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {current && (
        <div className="relative overflow-hidden rounded-[var(--radius-media)] bg-fill">
          <SafeImage
            key={current.id}
            src={current.url}
            alt={current.caption ?? title}
            fallbackLabel={emptyLabel}
            loading="eager"
            className="aspect-[4/3] w-full object-cover sm:aspect-[2/1]"
          />
          {images.length > 1 && (
            <>
              <button
                type="button"
                aria-label="‹"
                onClick={() => setIndex((index - 1 + images.length) % images.length)}
                className="absolute start-3 top-1/2 grid size-10 -translate-y-1/2 place-items-center rounded-full bg-glass text-xl text-ink shadow-soft backdrop-blur-md"
              >
                ‹
              </button>
              <button
                type="button"
                aria-label="›"
                onClick={() => setIndex((index + 1) % images.length)}
                className="absolute end-3 top-1/2 grid size-10 -translate-y-1/2 place-items-center rounded-full bg-glass text-xl text-ink shadow-soft backdrop-blur-md"
              >
                ›
              </button>
              <span className="absolute bottom-3 end-3 rounded-full bg-black/55 px-2.5 backdrop-blur-md py-0.5 text-xs text-white tabular">
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
                className={`block overflow-hidden rounded-xl ring-2 ${i === index ? "ring-accent" : "ring-transparent"}`}
              >
                <SafeImage
                  src={m.thumbnail_url ?? m.url}
                  alt=""
                  fallbackLabel="—"
                  className="h-16 w-24 object-cover"
                />
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
      className="inline-flex h-10 items-center gap-2 rounded-full px-4 text-sm font-medium text-ink ring-1 ring-inset ring-hairline transition hover:bg-fill"
    >
      {done ? copied : label}
    </button>
  );
}
