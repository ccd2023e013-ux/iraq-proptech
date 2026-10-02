/**
 * Comparison selection, kept per browser (a convenience, not account data).
 * Every storage access is guarded: private mode or blocked storage simply
 * means an empty selection.
 */

export const MAX_COMPARE = 4;
const KEY = "compare:ids";
const EVENT = "compare-change";

export function readCompare(): string[] {
  try {
    const raw = window.localStorage.getItem(KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed)
      ? parsed.filter((v): v is string => typeof v === "string").slice(0, MAX_COMPARE)
      : [];
  } catch {
    return [];
  }
}

function write(ids: string[]): void {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(ids));
  } catch {
    // storage unavailable: selection lives only for this event
  }
  window.dispatchEvent(new CustomEvent(EVENT, { detail: ids }));
}

/** Toggle an id; returns the new selection (oldest dropped when full). */
export function toggleCompare(id: string, current: string[] = readCompare()): string[] {
  const next = current.includes(id)
    ? current.filter((v) => v !== id)
    : [...current, id].slice(-MAX_COMPARE);
  write(next);
  return next;
}

export function clearCompare(): void {
  write([]);
}

export function onCompareChange(listener: (ids: string[]) => void): () => void {
  const handler = (event: Event) => listener((event as CustomEvent<string[]>).detail);
  const storage = (event: StorageEvent) => event.key === KEY && listener(readCompare());
  window.addEventListener(EVENT, handler);
  window.addEventListener("storage", storage);
  return () => {
    window.removeEventListener(EVENT, handler);
    window.removeEventListener("storage", storage);
  };
}
