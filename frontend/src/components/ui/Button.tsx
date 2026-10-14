import type { ButtonHTMLAttributes } from "react";

import { Icon } from "./Icon";

type Variant = "primary" | "secondary" | "ghost" | "tertiary" | "glass" | "danger";
type Size = "sm" | "md" | "lg";

/**
 * Buttons per docs/REDESIGN-RECOVERY.md §3: height and fill follow importance.
 * The look lives in globals.css (.btn, .btn-*) so links styled as actions use
 * the very same classes. primary = the one forward action (emerald) ·
 * secondary = a raised neutral · ghost/tertiary = quiet text · glass = a
 * control over the map or imagery · danger = critical outline.
 */
const VARIANTS: Record<Variant, string> = {
  primary: "btn-primary",
  secondary: "btn-secondary",
  ghost: "btn-quiet",
  tertiary:
    "text-ink underline decoration-hairline-strong underline-offset-4 hover:decoration-current",
  glass: "surface-float text-ink hover:text-accent",
  danger: "btn-danger",
};

const SIZES: Record<Size, string> = {
  sm: "btn-sm",
  md: "",
  lg: "btn-lg",
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
      className={`btn ${VARIANTS[variant]} ${SIZES[size]} ${block ? "w-full" : ""} ${className}`}
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
