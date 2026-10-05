import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-accent-fill text-white shadow-soft hover:bg-accent-fill-hover disabled:opacity-50 disabled:shadow-none",
  secondary:
    "bg-surface text-ink ring-1 ring-inset ring-hairline-strong hover:ring-accent/50 hover:text-accent disabled:opacity-50",
  ghost: "text-ink-2 hover:bg-fill hover:text-ink disabled:opacity-50",
  danger: "bg-danger text-white hover:opacity-90 disabled:opacity-50",
};

const SIZES: Record<Size, string> = {
  sm: "h-8 px-3 text-sm",
  md: "h-10 px-4 text-sm",
  lg: "h-12 px-6 text-base",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  block?: boolean;
}

/** Pill-shaped buttons with a pressed state; the label stays visible while loading. */
export function Button({
  variant = "primary",
  size = "md",
  loading = false,
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
      className={`inline-flex select-none items-center justify-center gap-2 rounded-full font-medium transition duration-[var(--duration-quick)] ease-[var(--ease-out-soft)] active:scale-[0.98] disabled:cursor-not-allowed ${VARIANTS[variant]} ${SIZES[size]} ${block ? "w-full" : ""} ${className}`}
      {...rest}
    >
      {loading && (
        <span
          aria-hidden
          className="size-4 animate-spin rounded-full border-2 border-current border-e-transparent"
        />
      )}
      {children}
    </button>
  );
}
