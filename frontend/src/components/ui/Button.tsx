import type { ButtonHTMLAttributes } from "react";

import { Icon } from "./Icon";

type Variant = "primary" | "secondary" | "ghost" | "tertiary" | "glass" | "danger";
type Size = "sm" | "md" | "lg";

/**
 * Buttons per docs/DESIGN-DIRECTION.md §9: shape and weight follow importance.
 * primary = the one forward action (emerald fill) · secondary = outline ·
 * ghost/tertiary = text · glass = a control over the map or imagery ·
 * danger = critical outline that fills on hover.
 */
const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-accent-fill text-on-accent shadow-[inset_0_1px_0_rgb(255_255_255/0.18)] hover:bg-accent-fill-hover active:brightness-95",
  secondary:
    "bg-transparent text-ink shadow-[inset_0_0_0_1px_var(--hairline-strong)] hover:bg-fill active:bg-fill-strong",
  ghost: "text-ink-2 hover:bg-fill hover:text-ink active:bg-fill-strong",
  tertiary:
    "text-ink underline decoration-hairline-strong underline-offset-4 hover:decoration-current",
  glass: "surface-float text-ink hover:text-accent",
  danger:
    "text-danger shadow-[inset_0_0_0_1px_color-mix(in_srgb,var(--critical)_55%,transparent)] hover:bg-danger hover:text-white",
};

const SIZES: Record<Size, string> = {
  sm: "h-8 px-3 text-[13px] gap-1.5",
  md: "h-10 px-4 text-sm gap-2",
  lg: "h-12 px-5 text-[15px] gap-2",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  /** Spinner in place of the icon; the width does not change. */
  loading?: boolean;
  /** Brief confirmation state: a check replaces the leading icon. */
  success?: boolean;
  block?: boolean;
}

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  success = false,
  block = false,
  className = "",
  disabled,
  children,
  type = "button",
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      data-state={success ? "success" : loading ? "loading" : undefined}
      className={`press inline-flex select-none items-center justify-center rounded-[var(--radius-control)] font-medium whitespace-nowrap disabled:pointer-events-none disabled:opacity-40 ${VARIANTS[variant]} ${SIZES[size]} ${block ? "w-full" : ""} ${className}`}
      {...rest}
    >
      {loading && (
        <span
          aria-hidden
          className="size-4 animate-spin rounded-full border-2 border-current border-e-transparent"
        />
      )}
      {success && !loading && <Icon name="check" className="icon-swap size-4" strokeWidth={2.2} />}
      {children}
    </button>
  );
}
