"use client";

import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import type { Dictionary } from "@/i18n";
import { getDictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";
import { apiFetch } from "@/lib/api/client";
import { describeError } from "@/lib/errors";

import {
  type Assets,
  compress,
  drawFrame,
  loadImages,
  record,
  type Storyboard,
  timeline,
} from "./renderer";
import { buildTexts } from "./texts";

interface Job {
  id: string;
  property_id: string;
  format: "landscape" | "vertical";
  status: string;
  storyboard: Storyboard;
  video_url: string | null;
  output_type: string | null;
  output_bytes: number | null;
  duration_ms: number | null;
}

export interface ListingOption {
  id: string;
  title: string;
}

/**
 * Media Studio: asks the API for a storyboard of the chosen listing, renders
 * it on a canvas in the browser, records it with MediaRecorder and can save
 * the result to the user's studio.
 */
export function Studio({
  dict,
  locale,
  listings,
  initialPropertyId,
  site,
}: {
  dict: Dictionary;
  locale: Locale;
  listings: ListingOption[];
  initialPropertyId: string | null;
  site: string;
}) {
  const s = dict.studio;
  const [propertyId, setPropertyId] = useState(initialPropertyId ?? listings[0]?.id ?? "");
  const [format, setFormat] = useState<"landscape" | "vertical">("landscape");
  const [language, setLanguage] = useState<Locale>(locale);
  const [quick, setQuick] = useState(false);
  const [drone, setDrone] = useState<File | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ blob: Blob; url: string; job: Job; ms: number } | null>(
    null,
  );
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [previous, setPrevious] = useState<Job[]>([]);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const supported =
    typeof window === "undefined" ||
    (typeof MediaRecorder !== "undefined" && "captureStream" in HTMLCanvasElement.prototype);

  useEffect(() => {
    if (!propertyId) return;
    apiFetch<Job[]>(`/api/v1/studio/jobs?property_id=${propertyId}`)
      .then((jobs) => setPrevious(jobs.filter((j) => j.video_url)))
      .catch(() => setPrevious([]));
  }, [propertyId, saved]);

  async function render() {
    if (!propertyId || !canvasRef.current) return;
    setError(null);
    setSaved(false);
    setProgress(0);
    if (result) URL.revokeObjectURL(result.url);
    setResult(null);
    try {
      await document.fonts?.ready;
      const job = await apiFetch<Job>("/api/v1/studio/jobs", {
        method: "POST",
        body: { property_id: propertyId, format },
      });
      const sb = job.storyboard;
      const scenes = quick ? compress(sb.scenes, 0.35) : sb.scenes;
      let video: HTMLVideoElement | null = null;
      if (drone) {
        video = document.createElement("video");
        video.muted = true;
        video.playsInline = true;
        video.src = URL.createObjectURL(drone);
        await new Promise<void>((resolve) => {
          video!.onloadeddata = () => resolve();
          video!.onerror = () => resolve();
        });
      }
      const timed = timeline(scenes, video && video.duration ? video.duration * 1000 : null);
      const total = timed[timed.length - 1]!.end;
      const images = await loadImages(
        scenes.filter((x) => x.type === "photo").map((x) => x.url ?? ""),
      );
      const assets: Assets = { images, drone: video };
      const canvas = canvasRef.current;
      const [w, h] = sb.size;
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext("2d")!;
      const texts = buildTexts(sb, getDictionary(language), language, site);
      const droneScene = timed.find((t) => t.scene.type === "drone");
      let droneStarted = false;
      const { blob } = await record(
        canvas,
        total,
        sb.fps,
        (t) => {
          if (video && droneScene && !droneStarted && t >= droneScene.start) {
            droneStarted = true;
            video.currentTime = 0;
            void video.play().catch(() => undefined);
          }
          drawFrame(ctx, w, h, t, timed, assets, texts, sb.is_demo);
        },
        (f) => setProgress(Math.round(f * 100)),
      );
      if (video) {
        video.pause();
        URL.revokeObjectURL(video.src);
      }
      setResult({ blob, url: URL.createObjectURL(blob), job, ms: Math.round(total) });
    } catch (err) {
      setError(
        err instanceof Error && err.message.includes("MediaRecorder")
          ? s.unsupported
          : describeError(dict, err),
      );
    } finally {
      setProgress(null);
    }
  }

  async function save() {
    if (!result) return;
    setSaving(true);
    setError(null);
    try {
      await apiFetch(`/api/v1/studio/jobs/${result.job.id}/output`, {
        method: "PUT",
        body: result.blob,
        headers: { "X-Duration-Ms": String(result.ms) },
      });
      setSaved(true);
    } catch (err) {
      setError(describeError(dict, err));
    } finally {
      setSaving(false);
    }
  }

  const ext = result?.blob.type.includes("mp4") ? "mp4" : "webm";
  const pill = (active: boolean) =>
    `h-9 rounded-[var(--radius-control)] px-3.5 text-sm font-medium transition ${active ? "bg-ink text-surface" : "bg-fill text-ink-2 hover:text-ink"}`;

  if (listings.length === 0) return <p className="text-ink-2">{s.noListings}</p>;

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-8 lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">
      <div className="flex flex-col gap-5">
        <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
          {s.pick}
          <select
            value={propertyId}
            onChange={(e) => setPropertyId(e.target.value)}
            className="field w-full min-w-0"
            data-testid="studio-listing"
          >
            {listings.map((l) => (
              <option key={l.id} value={l.id}>
                {l.title}
              </option>
            ))}
          </select>
        </label>
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 text-sm font-medium text-ink">{s.format}</legend>
          <div className="flex flex-wrap gap-1.5">
            <button
              type="button"
              aria-pressed={format === "landscape"}
              onClick={() => setFormat("landscape")}
              className={pill(format === "landscape")}
            >
              {s.landscape}
            </button>
            <button
              type="button"
              aria-pressed={format === "vertical"}
              onClick={() => setFormat("vertical")}
              className={pill(format === "vertical")}
            >
              {s.vertical}
            </button>
          </div>
        </fieldset>
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 text-sm font-medium text-ink">{s.language}</legend>
          <div className="flex gap-1.5">
            {(["ar", "en"] as const).map((l) => (
              <button
                key={l}
                type="button"
                aria-pressed={language === l}
                onClick={() => setLanguage(l)}
                className={pill(language === l)}
              >
                {l === "ar" ? "العربية" : "English"}
              </button>
            ))}
          </div>
        </fieldset>
        <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
          {s.drone}
          <input
            type="file"
            accept="video/mp4,video/webm,video/quicktime"
            onChange={(e) => setDrone(e.target.files?.[0] ?? null)}
            className="text-sm text-ink-2 file:me-3 file:rounded-[var(--radius-control)] file:border-0 file:bg-fill file:px-4 file:py-2 file:text-ink"
          />
          <span className="text-xs font-normal text-ink-3">{s.droneHint}</span>
        </label>
        <label className="flex items-center justify-between gap-3 text-sm text-ink">
          {s.quick}
          <input
            type="checkbox"
            checked={quick}
            onChange={(e) => setQuick(e.target.checked)}
            className="size-4 accent-[var(--accent)]"
            data-testid="studio-quick"
          />
        </label>
        <Button
          size="lg"
          block
          onClick={render}
          loading={progress !== null}
          disabled={!supported}
          data-testid="studio-render"
        >
          {progress !== null ? s.rendering.replace("{p}", String(progress)) : s.render}
        </Button>
        {!supported && <p className="text-sm text-danger">{s.unsupported}</p>}
        {error && <p className="text-sm text-danger">{error}</p>}
        <p className="text-xs text-ink-3">{s.honest}</p>
        <p className="text-xs text-ink-3">{s.renderer}</p>
      </div>

      <section className="flex min-w-0 flex-col gap-3">
        <div
          className={`mx-auto w-full overflow-hidden rounded-[var(--radius-media)] bg-ink ${format === "vertical" ? "max-w-xs" : ""}`}
        >
          <canvas
            ref={canvasRef}
            className={`block w-full ${result ? "hidden" : ""} ${format === "vertical" ? "aspect-[9/16]" : "aspect-video"}`}
            data-testid="studio-canvas"
          />
          {result && (
            <video
              src={result.url}
              controls
              playsInline
              className={`block w-full ${format === "vertical" ? "aspect-[9/16]" : "aspect-video"}`}
              data-testid="studio-result"
            />
          )}
        </div>
        {result && (
          <div className="flex flex-wrap items-center gap-2">
            <a
              href={result.url}
              download={`property-video.${ext}`}
              className="inline-flex h-10 items-center rounded-[var(--radius-control)] px-4 text-sm font-medium text-ink ring-1 ring-inset ring-hairline hover:bg-fill"
            >
              {s.download}
            </a>
            <Button onClick={save} loading={saving} disabled={saved} data-testid="studio-save">
              {saved ? s.saved : s.save}
            </Button>
            <span className="text-xs text-ink-3 tabular">
              {(result.blob.size / 1_000_000).toFixed(1)} MB · {Math.round(result.ms / 1000)} s
            </span>
          </div>
        )}
        {previous.length > 0 && (
          <div className="mt-4">
            <h2 className="text-sm font-semibold text-ink">{s.previous}</h2>
            <ul className="mt-2 flex flex-col gap-1 text-sm" data-testid="studio-saved">
              {previous.map((j) => (
                <li key={j.id}>
                  <a
                    href={j.video_url ?? "#"}
                    className="text-accent underline-offset-4 hover:underline"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {j.format === "vertical" ? s.vertical : s.landscape} ·{" "}
                    {Math.round((j.duration_ms ?? 0) / 1000)} s ·{" "}
                    {((j.output_bytes ?? 0) / 1_000_000).toFixed(1)} MB
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
    </div>
  );
}
