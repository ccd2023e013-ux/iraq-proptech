/**
 * Browser renderer for Property Media Studio: storyboard → canvas frames →
 * MediaRecorder video. Runs entirely on the user's device, so the free
 * deployment never encodes video (server/external renderers can consume the
 * same storyboard later).
 */

import { CITIES, project, RIVERS, smoothPath, VIEW } from "@/features/home/riverGeometry";

export type SceneType = "map_intro" | "photo" | "facts" | "nearby" | "drone" | "cta";

export interface Scene {
  type: SceneType;
  duration_ms: number;
  url?: string;
  lon?: number | null;
  lat?: number | null;
  approximate?: boolean;
  items?: {
    category: string;
    name_ar: string;
    name_en: string | null;
    distance_m: number;
    source: string;
    is_demo: boolean;
  }[];
}

export interface Storyboard {
  version: number;
  format: "landscape" | "vertical";
  size: [number, number];
  fps: number;
  is_demo: boolean;
  property: {
    id: string;
    reference_code: string;
    path: string;
    title_ar: string;
    title_en: string | null;
    type_ar: string;
    type_en: string;
    purpose: string;
    city_ar: string | null;
    city_en: string | null;
    district_ar: string | null;
    district_en: string | null;
    price_amount: string | null;
    currency: "IQD" | "USD";
    rent_period: string | null;
    area_m2: string | null;
    bedrooms: number | null;
    bathrooms: number | null;
    verified: boolean;
  };
  scenes: Scene[];
}

export interface Texts {
  rtl: boolean;
  title: string;
  place: string;
  price: string;
  facts: { label: string; value: string }[];
  nearbyTitle: string;
  nearby: { label: string; value: string }[];
  nearbySource: string;
  approximate: string;
  droneNote: string;
  ctaTitle: string;
  ctaLine: string;
  site: string;
  demo: string;
  brand: string;
}

export interface Timed {
  scene: Scene;
  start: number;
  end: number;
}

/** Scene timings; an optional drone clip goes right after the map intro. */
export function timeline(scenes: Scene[], droneMs: number | null): Timed[] {
  const list: Scene[] = [];
  for (const scene of scenes) {
    list.push(scene);
    if (scene.type === "map_intro" && droneMs) {
      list.push({ type: "drone", duration_ms: Math.min(droneMs, 12_000) });
    }
  }
  let t = 0;
  return list.map((scene) => {
    const timed = { scene, start: t, end: t + scene.duration_ms };
    t += scene.duration_ms;
    return timed;
  });
}

/** Shorten every scene (quick preview / automated checks). */
export function compress(scenes: Scene[], factor: number): Scene[] {
  return scenes.map((s) => ({
    ...s,
    duration_ms: Math.max(600, Math.round(s.duration_ms * factor)),
  }));
}

const MIME_CANDIDATES = [
  "video/mp4;codecs=avc1.42E01E",
  "video/mp4",
  "video/webm;codecs=vp9",
  "video/webm;codecs=vp8",
  "video/webm",
];

export function pickMimeType(isSupported: (type: string) => boolean): string | null {
  return MIME_CANDIDATES.find((t) => isSupported(t)) ?? null;
}

const easeOut = (x: number) => 1 - Math.pow(1 - Math.min(1, Math.max(0, x)), 3);

const INK = "#0b1112";
const ACCENT = "#1fa394";
const GOLD = "#e0b45a";
const DISPLAY = '"Readex Pro Variable", "IBM Plex Sans Arabic", system-ui, sans-serif';
const BODY = '"IBM Plex Sans Arabic", "IBM Plex Sans", system-ui, sans-serif';

function font(size: number, weight = 600, family = DISPLAY): string {
  return `${weight} ${Math.round(size)}px ${family}`;
}

function text(
  ctx: CanvasRenderingContext2D,
  value: string,
  x: number,
  y: number,
  opts: {
    size: number;
    weight?: number;
    color?: string;
    rtl: boolean;
    align?: "start" | "center";
    family?: string;
    maxWidth?: number;
  },
) {
  ctx.save();
  ctx.font = font(opts.size, opts.weight ?? 600, opts.family);
  ctx.fillStyle = opts.color ?? "#ffffff";
  ctx.direction = opts.rtl ? "rtl" : "ltr";
  ctx.textAlign = opts.align === "center" ? "center" : opts.rtl ? "right" : "left";
  ctx.textBaseline = "alphabetic";
  ctx.fillText(value, x, y, opts.maxWidth);
  ctx.restore();
}

function cover(
  ctx: CanvasRenderingContext2D,
  source: CanvasImageSource,
  sw: number,
  sh: number,
  w: number,
  h: number,
  zoom: number,
  panX: number,
) {
  const scale = Math.max(w / sw, h / sh) * zoom;
  const dw = sw * scale;
  const dh = sh * scale;
  ctx.drawImage(source, (w - dw) / 2 + panX * (dw - w) * 0.5, (h - dh) / 2, dw, dh);
}

function gradient(ctx: CanvasRenderingContext2D, w: number, h: number) {
  const g = ctx.createLinearGradient(0, h * 0.45, 0, h);
  g.addColorStop(0, "rgba(11,17,18,0)");
  g.addColorStop(1, "rgba(11,17,18,0.86)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, w, h);
}

export interface Assets {
  images: Map<string, HTMLImageElement>;
  drone: HTMLVideoElement | null;
}

function drawMap(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  p: number,
  s: Scene,
  tx: Texts,
) {
  ctx.fillStyle = INK;
  ctx.fillRect(0, 0, w, h);
  const base = Math.min(w / VIEW.width, (h * 0.8) / VIEW.height);
  const target = s.lon != null && s.lat != null ? project([s.lon, s.lat]) : project([47.81, 30.51]);
  const zoom = 1 + easeOut(p) * 1.6;
  ctx.save();
  ctx.translate(w / 2, h / 2);
  ctx.scale(base * zoom, base * zoom);
  const cx = VIEW.width / 2 + (target[0] - VIEW.width / 2) * easeOut(p);
  const cy = VIEW.height / 2 + (target[1] - VIEW.height / 2) * easeOut(p);
  ctx.translate(-cx, -cy);
  ctx.lineCap = "round";
  for (const key of ["euphrates", "tigris", "shatt"] as const) {
    ctx.strokeStyle = key === "shatt" ? ACCENT : "rgba(255,255,255,0.35)";
    ctx.lineWidth = (key === "shatt" ? 3 : 2) / zoom;
    ctx.stroke(new Path2D(smoothPath(RIVERS[key])));
  }
  for (const city of CITIES) {
    const [x, y] = project(city.at);
    ctx.fillStyle = "rgba(255,255,255,0.7)";
    ctx.beginPath();
    ctx.arc(x, y, 3.2 / zoom, 0, Math.PI * 2);
    ctx.fill();
  }
  // property pin with a pulse
  const pulse = (p * 3) % 1;
  ctx.strokeStyle = `rgba(224,180,90,${1 - pulse})`;
  ctx.lineWidth = 2 / zoom;
  ctx.beginPath();
  ctx.arc(target[0], target[1], (6 + pulse * 18) / zoom, 0, Math.PI * 2);
  ctx.stroke();
  ctx.fillStyle = GOLD;
  ctx.beginPath();
  ctx.arc(target[0], target[1], 6 / zoom, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();

  const a = easeOut((p - 0.25) * 2);
  ctx.globalAlpha = a;
  const pad = w * 0.06;
  const x = tx.rtl ? w - pad : pad;
  text(ctx, tx.title, x, h - pad - w * 0.05, {
    size: w * 0.045,
    rtl: tx.rtl,
    maxWidth: w - pad * 2,
  });
  text(ctx, tx.place, x, h - pad, {
    size: w * 0.026,
    weight: 400,
    color: "#cfe0dc",
    rtl: tx.rtl,
    family: BODY,
  });
  if (s.approximate) {
    text(ctx, tx.approximate, x, pad + w * 0.02, {
      size: w * 0.018,
      weight: 400,
      color: "#9fb3ae",
      rtl: tx.rtl,
      family: BODY,
    });
  }
  ctx.globalAlpha = 1;
}

function drawPhoto(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  p: number,
  img: HTMLImageElement | undefined,
  index: number,
  tx: Texts,
) {
  ctx.fillStyle = INK;
  ctx.fillRect(0, 0, w, h);
  if (img && img.naturalWidth > 0) {
    cover(
      ctx,
      img,
      img.naturalWidth,
      img.naturalHeight,
      w,
      h,
      1 + p * 0.1,
      index % 2 ? p - 0.5 : 0.5 - p,
    );
  }
  gradient(ctx, w, h);
  const pad = w * 0.06;
  const x = tx.rtl ? w - pad : pad;
  if (index === 0) {
    text(ctx, tx.price, x, h - pad - w * 0.05, { size: w * 0.05, rtl: tx.rtl, color: "#ffffff" });
    text(ctx, tx.place, x, h - pad, {
      size: w * 0.024,
      weight: 400,
      color: "#e6efec",
      rtl: tx.rtl,
      family: BODY,
    });
  }
}

function drawFacts(ctx: CanvasRenderingContext2D, w: number, h: number, p: number, tx: Texts) {
  ctx.fillStyle = INK;
  ctx.fillRect(0, 0, w, h);
  const vertical = h > w;
  const items = tx.facts.slice(0, 4);
  const cols = vertical ? 1 : items.length;
  const cellW = vertical ? w * 0.8 : (w * 0.84) / cols;
  const cellH = vertical ? (h * 0.6) / items.length : h * 0.3;
  const x0 = vertical ? w * 0.1 : w * 0.08;
  const y0 = vertical ? h * 0.2 : h * 0.35;
  items.forEach((item, i) => {
    const a = easeOut(p * 3 - i * 0.35);
    ctx.globalAlpha = a;
    const cx = vertical ? x0 : tx.rtl ? x0 + (cols - 1 - i) * cellW : x0 + i * cellW;
    const cy = vertical ? y0 + i * cellH : y0;
    const anchorX = tx.rtl ? cx + cellW - w * 0.02 : cx + w * 0.02;
    text(ctx, item.value, anchorX, cy + cellH * 0.45 + (1 - a) * 20, {
      size: Math.min(w, h) * 0.07,
      rtl: tx.rtl,
      color: "#ffffff",
    });
    text(ctx, item.label, anchorX, cy + cellH * 0.45 + Math.min(w, h) * 0.06, {
      size: Math.min(w, h) * 0.028,
      weight: 400,
      color: "#9fb3ae",
      rtl: tx.rtl,
      family: BODY,
    });
  });
  ctx.globalAlpha = 1;
}

function drawNearby(ctx: CanvasRenderingContext2D, w: number, h: number, p: number, tx: Texts) {
  ctx.fillStyle = "#0f1a1b";
  ctx.fillRect(0, 0, w, h);
  const pad = w * 0.08;
  const x = tx.rtl ? w - pad : pad;
  const size = Math.min(w, h);
  text(ctx, tx.nearbyTitle, x, h * 0.2, { size: size * 0.06, rtl: tx.rtl });
  tx.nearby.forEach((row, i) => {
    const a = easeOut(p * 3 - i * 0.3);
    ctx.globalAlpha = a;
    const y = h * 0.34 + i * size * 0.12;
    text(ctx, row.label, x, y, {
      size: size * 0.036,
      weight: 500,
      rtl: tx.rtl,
      family: BODY,
      maxWidth: w * 0.6,
    });
    text(ctx, row.value, tx.rtl ? pad : w - pad, y, {
      size: size * 0.036,
      rtl: !tx.rtl,
      color: GOLD,
    });
  });
  ctx.globalAlpha = 1;
  text(ctx, tx.nearbySource, x, h - pad * 0.6, {
    size: size * 0.02,
    weight: 400,
    color: "#9fb3ae",
    rtl: tx.rtl,
    family: BODY,
  });
}

function drawDrone(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  video: HTMLVideoElement | null,
  tx: Texts,
) {
  ctx.fillStyle = INK;
  ctx.fillRect(0, 0, w, h);
  if (video && video.videoWidth > 0) {
    cover(ctx, video, video.videoWidth, video.videoHeight, w, h, 1, 0);
  }
  gradient(ctx, w, h);
  const pad = w * 0.06;
  const x = tx.rtl ? w - pad : pad;
  // location card
  text(ctx, tx.place, x, h - pad - w * 0.03, { size: w * 0.035, rtl: tx.rtl });
  if (tx.nearby[0]) {
    text(ctx, `${tx.nearby[0].label} · ${tx.nearby[0].value}`, x, h - pad, {
      size: w * 0.02,
      weight: 400,
      color: "#e6efec",
      rtl: tx.rtl,
      family: BODY,
    });
  }
  // compass (north up: the overlay is not geo-registered)
  const cx = tx.rtl ? pad + w * 0.02 : w - pad - w * 0.02;
  const cy = pad + w * 0.02;
  ctx.strokeStyle = "rgba(255,255,255,0.8)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.arc(cx, cy, w * 0.02, 0, Math.PI * 2);
  ctx.stroke();
  text(ctx, "N", cx, cy - w * 0.006, { size: w * 0.016, rtl: false, align: "center" });
  text(ctx, tx.droneNote, x, pad + w * 0.01, {
    size: w * 0.016,
    weight: 400,
    color: "#cfe0dc",
    rtl: tx.rtl,
    family: BODY,
  });
}

function drawCta(ctx: CanvasRenderingContext2D, w: number, h: number, p: number, tx: Texts) {
  const g = ctx.createLinearGradient(0, 0, w, h);
  g.addColorStop(0, "#0d3b37");
  g.addColorStop(1, INK);
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, w, h);
  ctx.globalAlpha = easeOut(p * 2);
  const size = Math.min(w, h);
  text(ctx, tx.brand, w / 2, h * 0.36, {
    size: size * 0.05,
    rtl: tx.rtl,
    align: "center",
    color: GOLD,
  });
  text(ctx, tx.ctaTitle, w / 2, h * 0.5, {
    size: size * 0.07,
    rtl: tx.rtl,
    align: "center",
    maxWidth: w * 0.9,
  });
  text(ctx, tx.ctaLine, w / 2, h * 0.6, {
    size: size * 0.032,
    weight: 400,
    rtl: tx.rtl,
    align: "center",
    color: "#cfe0dc",
    family: BODY,
  });
  text(ctx, tx.site, w / 2, h * 0.7, {
    size: size * 0.03,
    weight: 500,
    rtl: false,
    align: "center",
    color: "#ffffff",
    family: BODY,
  });
  ctx.globalAlpha = 1;
}

/** Draw the frame at time `t` (ms) of the timeline. */
export function drawFrame(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  t: number,
  timed: Timed[],
  assets: Assets,
  tx: Texts,
  isDemo: boolean,
) {
  const current = timed.find((s) => t >= s.start && t < s.end) ?? timed[timed.length - 1]!;
  const p = (t - current.start) / (current.end - current.start);
  const photoIndex =
    timed.filter((s) => s.scene.type === "photo" && s.start <= current.start).length - 1;
  switch (current.scene.type) {
    case "map_intro":
      drawMap(ctx, w, h, p, current.scene, tx);
      break;
    case "photo":
      drawPhoto(ctx, w, h, p, assets.images.get(current.scene.url ?? ""), photoIndex, tx);
      break;
    case "facts":
      drawFacts(ctx, w, h, p, tx);
      break;
    case "nearby":
      drawNearby(ctx, w, h, p, tx);
      break;
    case "drone":
      drawDrone(ctx, w, h, assets.drone, tx);
      break;
    case "cta":
      drawCta(ctx, w, h, p, tx);
      break;
  }
  // fade in from black at each scene start
  if (t - current.start < 300) {
    ctx.fillStyle = `rgba(0,0,0,${1 - (t - current.start) / 300})`;
    ctx.fillRect(0, 0, w, h);
  }
  if (isDemo) {
    const size = Math.min(w, h);
    ctx.save();
    ctx.fillStyle = "rgba(185,138,44,0.95)";
    const pillW = size * 0.12;
    const pillH = size * 0.045;
    const x = tx.rtl ? size * 0.03 : w - pillW - size * 0.03;
    ctx.beginPath();
    ctx.roundRect(x, size * 0.03, pillW, pillH, pillH / 2);
    ctx.fill();
    text(ctx, tx.demo, x + pillW / 2, size * 0.03 + pillH * 0.7, {
      size: size * 0.026,
      rtl: false,
      align: "center",
    });
    ctx.restore();
  }
}

export async function loadImages(urls: string[]): Promise<Map<string, HTMLImageElement>> {
  const map = new Map<string, HTMLImageElement>();
  await Promise.all(
    urls.map(
      (url) =>
        new Promise<void>((resolve) => {
          const img = new Image();
          img.decoding = "async";
          img.onload = () => {
            map.set(url, img);
            resolve();
          };
          img.onerror = () => resolve();
          img.src = url;
        }),
    ),
  );
  return map;
}

/** Record `totalMs` of frames from the canvas; resolves with the video blob. */
export function record(
  canvas: HTMLCanvasElement,
  totalMs: number,
  fps: number,
  draw: (t: number) => void,
  onProgress: (fraction: number) => void,
): Promise<{ blob: Blob; mimeType: string }> {
  const mimeType = pickMimeType((t) => MediaRecorder.isTypeSupported(t));
  if (!mimeType) return Promise.reject(new Error("MediaRecorder unsupported"));
  const stream = canvas.captureStream(fps);
  const recorder = new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 6_000_000 });
  const chunks: Blob[] = [];
  recorder.ondataavailable = (e) => {
    if (e.data.size > 0) chunks.push(e.data);
  };
  return new Promise((resolve, reject) => {
    recorder.onerror = () => reject(new Error("recording failed"));
    recorder.onstop = () =>
      resolve({ blob: new Blob(chunks, { type: mimeType.split(";")[0] }), mimeType });
    draw(0);
    recorder.start(250);
    const started = performance.now();
    const tick = () => {
      const t = performance.now() - started;
      if (t >= totalMs) {
        draw(totalMs - 1);
        onProgress(1);
        recorder.stop();
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      draw(t);
      onProgress(t / totalMs);
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
}
