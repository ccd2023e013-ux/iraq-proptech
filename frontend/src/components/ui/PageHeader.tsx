import type { ReactNode } from "react";

/**
 * The top of every page: title, an optional lede, and the page's own actions
 * at the end. One size and rhythm across the product, so pages read as one
 * product — the content below decides its own composition.
 */
export function PageHeader({
  title,
  lede,
  actions,
  context,
  size = "lg",
  id,
}: {
  title: ReactNode;
  lede?: ReactNode;
  actions?: ReactNode;
  /** A line above the title that places the page (e.g. a back link). */
  context?: ReactNode;
  /** "lg" for top-level pages, "md" for tools and settings. */
  size?: "lg" | "md";
  id?: string;
}) {
  return (
    <header
      className={`flex flex-col gap-5 border-b border-hairline md:flex-row md:items-end md:justify-between ${size === "lg" ? "pt-10 pb-6 md:pt-14 md:pb-8" : "pt-6 pb-4 md:pt-10 md:pb-6"}`}
    >
      <div className="flex min-w-0 flex-col gap-3">
        {context && <div className="meta">{context}</div>}
        <h1 id={id} className={`${size === "lg" ? "display-lg" : "display-md"} text-ink`}>
          {title}
        </h1>
        {lede && <div className="lede">{lede}</div>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}
