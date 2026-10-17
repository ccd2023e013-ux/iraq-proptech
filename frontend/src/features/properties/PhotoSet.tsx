"use client";

import {
  type ReactNode,
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";

/**
 * One photograph, one appearance per view (docs/ART-DIRECTION.md, principle 6).
 *
 * DEMO listings share a small library of representative photos, and each
 * listing stores its own copy, so a repeated photo cannot be recognised by its
 * URL. Inside a <PhotoSet>, every <SetPhoto> fingerprints its loaded image
 * (a 64-bit difference hash of a 9×8 greyscale thumbnail, drawn in the
 * browser) and shows it only when no earlier photo in the set has the same
 * fingerprint; a repeat shows its place plate instead. Earlier = lower
 * `index`, i.e. reading order. Until the earlier photos are known, the plate
 * shows and the photo waits (it fades in once cleared).
 */
export class PhotoRegistry {
  private hashes = new Map<number, string | null>();
  private listeners = new Set<() => void>();
  version = 0;

  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  set(index: number, hash: string | null) {
    if (this.hashes.get(index) === hash && this.hashes.has(index)) return;
    this.hashes.set(index, hash);
    this.version++;
    for (const l of this.listeners) l();
  }

  /** "show" | "repeat" | "wait" for the photo at `index` with `hash`. */
  decide(index: number, hash: string | null | undefined): "show" | "repeat" | "wait" {
    if (hash === undefined) return "wait";
    if (hash === null) return "show";
    for (let i = 0; i < index; i++) {
      // Slots are contiguous from 0 and every slot registers (a slot without
      // a photo registers null), so an unknown earlier slot is still loading.
      if (!this.hashes.has(i)) return "wait";
      if (this.hashes.get(i) === hash) return "repeat";
    }
    return "show";
  }
}

const SetContext = createContext<PhotoRegistry | null>(null);

export function PhotoSet({ children }: { children: ReactNode }) {
  const [registry] = useState(() => new PhotoRegistry());
  return <SetContext.Provider value={registry}>{children}</SetContext.Provider>;
}

export function differenceHash(img: HTMLImageElement): string | null {
  try {
    const canvas = document.createElement("canvas");
    canvas.width = 9;
    canvas.height = 8;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) return null;
    ctx.drawImage(img, 0, 0, 9, 8);
    const d = ctx.getImageData(0, 0, 9, 8).data;
    const grey = (x: number, y: number) => {
      const i = (y * 9 + x) * 4;
      return d[i]! * 0.299 + d[i + 1]! * 0.587 + d[i + 2]! * 0.114;
    };
    let bits = "";
    for (let y = 0; y < 8; y++)
      for (let x = 0; x < 8; x++) bits += grey(x, y) > grey(x + 1, y) ? "1" : "0";
    return bits;
  } catch {
    return null; // e.g. a cross-origin image: treat it as unique
  }
}

const noop = () => () => undefined;

/**
 * A photo inside a <PhotoSet>; outside one it is a plain photo. `plate` is
 * what shows while the photo is pending, failed, or a repeat.
 */
export function SetPhoto({
  src,
  index,
  plate,
  className = "",
  alt = "",
  overlay,
}: {
  src: string | null;
  index?: number;
  plate: ReactNode;
  className?: string;
  alt?: string;
  /** Shown over the photo only while the photo itself is shown. */
  overlay?: ReactNode;
}) {
  const registry = useContext(SetContext);
  const ref = useRef<HTMLImageElement>(null);
  const [hash, setHash] = useState<string | null | undefined>(undefined);
  const [failed, setFailed] = useState(false);
  useSyncExternalStore(
    registry?.subscribe ?? noop,
    () => registry?.version ?? 0,
    () => 0,
  );

  useEffect(() => {
    if (!src && registry && index !== undefined) registry.set(index, null);
  }, [src, registry, index]);

  function onLoad() {
    const img = ref.current;
    const h = img && img.naturalWidth > 0 ? differenceHash(img) : null;
    setHash(h);
    if (registry && index !== undefined) registry.set(index, h);
  }

  // Cached images can finish before hydration and never fire onLoad.
  useEffect(() => {
    const img = ref.current;
    if (img?.complete && img.naturalWidth > 0 && hash === undefined) onLoad();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [src]);

  if (!src || failed) return <>{plate}</>;
  const verdict =
    registry && index !== undefined
      ? registry.decide(index, hash)
      : hash === undefined
        ? "wait"
        : "show";
  return (
    <>
      {verdict !== "show" && plate}
      {verdict !== "repeat" && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          ref={ref}
          src={src}
          alt={alt}
          decoding="async"
          onLoad={onLoad}
          onError={() => {
            setFailed(true);
            if (registry && index !== undefined) registry.set(index, null);
          }}
          className={`absolute inset-0 size-full object-cover transition-opacity duration-[var(--duration-slow)] ${
            verdict === "show" ? "opacity-100" : "opacity-0"
          } ${className}`}
        />
      )}
      {verdict === "show" && overlay}
    </>
  );
}
