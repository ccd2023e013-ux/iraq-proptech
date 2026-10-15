"use client";

import Link from "next/link";
import { type KeyboardEvent, useState } from "react";

import { Icon } from "@/components/ui/Icon";
import { SafeImage } from "@/components/ui/SafeImage";
import type { Media } from "@/types/property";

/**
 * Immersive gallery: one large photograph that cross-fades between images,
 * floating glass controls, keyboard arrows, and a thumbnail strip whose
 * current item is lifted and outlined. Videos follow below.
 */
export function Gallery({
  media,
  title,
  emptyLabel,
  labels = { prev: "‹", next: "›" },
  creditsLabel,
  transitionName,
  stamp,
}: {
  media: Media[];
  title: string;
  emptyLabel: string;
  labels?: { prev: string; next: string };
  /** Link text to the photo credits, shown under credited (Commons) photos. */
  creditsLabel?: string;
  /** `view-transition-name` of the main photo (the map preview's photo
   * travels into it). */
  transitionName?: string;
  /** A label printed on the photo itself (e.g. "DEMO · representative"). */
  stamp?: string;
}) {
  const images = media.filter((m) => m.kind !== "VIDEO");
  const videos = media.filter((m) => m.kind === "VIDEO");
  const [index, setIndex] = useState(0);
  const current = images[index];
  const go = (step: number) => setIndex((i) => (i + step + images.length) % images.length);

  function onKey(event: KeyboardEvent<HTMLDivElement>) {
    if (images.length < 2) return;
    const rtl = document.documentElement.dir === "rtl";
    if (event.key === "ArrowRight") go(rtl ? -1 : 1);
    else if (event.key === "ArrowLeft") go(rtl ? 1 : -1);
    else return;
    event.preventDefault();
  }

  if (!images.length && !videos.length) {
    return (
      // No photos: a slim band instead of a large empty frame, so the facts
      // (title, price, specs) lead the page.
      <div className="relative isolate flex h-24 items-center justify-center overflow-hidden rounded-[var(--radius-card)] bg-fill text-ink-3 shadow-[inset_0_0_0_1px_var(--hairline)] sm:h-28">
        <div aria-hidden className="stage-grid absolute inset-0 -z-10 opacity-70" />
        <span className="flex items-center gap-2 text-sm">
          <Icon name="home" className="size-5" />
          {emptyLabel}
        </span>
      </div>
    );
  }

  const control =
    "press surface-float absolute top-1/2 grid size-11 -translate-y-1/2 place-items-center rounded-[var(--radius-control)] text-ink opacity-90 transition-opacity hover:opacity-100 max-sm:size-9";

  return (
    <div className="flex flex-col gap-3">
      {current && (
        <div
          role="group"
          aria-roledescription="carousel"
          aria-label={title}
          tabIndex={images.length > 1 ? 0 : -1}
          onKeyDown={onKey}
          style={transitionName && index === 0 ? { viewTransitionName: transitionName } : undefined}
          className="group relative overflow-hidden rounded-[var(--radius-card)] bg-fill shadow-[inset_0_0_0_1px_var(--hairline)]"
        >
          <SafeImage
            key={current.id}
            src={current.url}
            alt={current.caption ?? title}
            fallbackLabel={emptyLabel}
            loading="eager"
            className="photo aspect-[4/3] w-full object-cover sm:aspect-[16/9] lg:aspect-[2.25/1]"
          />
          {stamp && (
            <span className="absolute start-0 bottom-0 rounded-se-[var(--radius-control)] bg-gold-500 px-3 py-1.5 text-[13px] font-semibold text-[#1d1405]">
              {stamp}
            </span>
          )}
          {images.length > 1 && (
            <>
              <button
                type="button"
                aria-label={labels.prev}
                onClick={() => go(-1)}
                className={`${control} start-3 sm:start-4`}
              >
                <Icon name="chevron" className="size-5 rotate-180" />
              </button>
              <button
                type="button"
                aria-label={labels.next}
                onClick={() => go(1)}
                className={`${control} end-3 sm:end-4`}
              >
                <Icon name="chevron" className="size-5" />
              </button>
              <span className="surface-float absolute end-4 bottom-4 rounded-[var(--radius-tag)] px-3 py-1 text-xs font-medium text-ink tabular">
                {index + 1} / {images.length}
              </span>
            </>
          )}
        </div>
      )}
      {/* A photo's caption sits under it; representative DEMO photos carry
          their credit here and link to the full attribution. */}
      {current?.caption && (
        <p className="caption flex flex-wrap items-baseline gap-x-2" dir="auto">
          <span>{current.caption}</span>
          {creditsLabel && current.caption.includes("Wikimedia Commons") && (
            <Link href="/credits" className="link">
              {creditsLabel}
            </Link>
          )}
        </p>
      )}
      {images.length > 1 && (
        <ul className="quiet-scroll flex gap-2 overflow-x-auto px-0.5 pt-0.5 pb-1">
          {images.map((m, i) => (
            <li key={m.id} className="shrink-0">
              <button
                type="button"
                onClick={() => setIndex(i)}
                aria-current={i === index}
                aria-label={`${i + 1} / ${images.length}`}
                className={`press block overflow-hidden rounded-xl transition-[opacity,box-shadow,translate] duration-[var(--duration-base)] ${
                  i === index
                    ? "-translate-y-0.5 opacity-100 shadow-[0_0_0_2px_var(--accent-fill)]"
                    : "opacity-70 hover:opacity-100"
                }`}
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
      className="press surface-1 inline-flex h-10 items-center gap-2 rounded-[var(--radius-control)] px-4 text-sm font-medium text-ink"
    >
      {done ? (
        <Icon name="check" className="icon-swap size-4 text-accent" strokeWidth={2.2} />
      ) : (
        <Icon name="arrow" className="size-4 -rotate-45" />
      )}
      <span aria-live="polite">{done ? copied : label}</span>
    </button>
  );
}
