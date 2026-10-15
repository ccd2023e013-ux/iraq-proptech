/**
 * Navigate with a same-document View Transition: the element named with
 * `view-transition-name` on the current page (e.g. the map preview's photo)
 * morphs into the element with the same name on the next page (the detail
 * page's hero). It is a progressive enhancement:
 *
 *  - no View Transitions support, or the reader asked for reduced motion →
 *    a plain client navigation (instant, history intact);
 *  - the transition waits for the next page to mark itself ready
 *    (`data-vt-ready="<key>"`), at most `timeoutMs`, so a slow page never
 *    freezes the screen.
 *
 * The caller keeps a real link (`<a href>`) and calls this only for plain
 * left clicks, so new-tab, copy-link and keyboard behaviour are unchanged.
 */

type StartViewTransition = (update: () => Promise<void>) => { finished: Promise<void> };

export function canTransition(): boolean {
  if (typeof document === "undefined") return false;
  const start = (document as unknown as { startViewTransition?: StartViewTransition })
    .startViewTransition;
  return (
    typeof start === "function" && !window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

/** True for a click the browser would handle as "open here" (no modifiers). */
export function isPlainClick(event: {
  button: number;
  metaKey: boolean;
  ctrlKey: boolean;
  shiftKey: boolean;
  altKey: boolean;
  defaultPrevented: boolean;
}): boolean {
  return (
    !event.defaultPrevented &&
    event.button === 0 &&
    !event.metaKey &&
    !event.ctrlKey &&
    !event.shiftKey &&
    !event.altKey
  );
}

export function navigateWithTransition(
  push: (href: string) => void,
  href: string,
  readyKey: string,
  timeoutMs = 2500,
): void {
  if (!canTransition()) {
    push(href);
    return;
  }
  const start = (document as unknown as { startViewTransition: StartViewTransition })
    .startViewTransition;
  start.call(
    document,
    () =>
      new Promise<void>((resolve) => {
        push(href);
        const t0 = performance.now();
        const wait = () => {
          const ready = document.querySelector(`[data-vt-ready="${CSS.escape(readyKey)}"]`);
          if (ready || performance.now() - t0 > timeoutMs) resolve();
          else requestAnimationFrame(wait);
        };
        requestAnimationFrame(wait);
      }),
  );
}
