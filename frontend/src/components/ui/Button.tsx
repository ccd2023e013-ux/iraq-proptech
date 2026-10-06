import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost" | "glass" | "danger";
type Size = "sm" | "md" | "lg";

const VARIANTS: Record<Variant, string> = {
  // Emerald is the one confident colour: actions that move the user forward.
  primary:
    "bg-accent-fill text-on-accent shadow-[inset_0_1px_0_rgb(255_255_255/0.25),0_1px_2px_rgb(0_0_0/0.2)] hover:bg-accent-fill-hover disabled:opacity-50 disabled:shadow-none",
  secondary: "surface-1 text-ink hover:text-accent disabled:opacity-50",
  ghost: "text-ink-2 hover:bg-fill hover:text-ink disabled:opacity-50",
  // For controls that sit over the map or imagery.
  glass: "surface-float text-ink hover:text-accent disabled:opacity-50",
  danger: "bg-danger text-white hover:opacity-90 disabled:opacity-50",
};

const SIZES: Record<Size, string> = {
  sm: "h-8 px-3.5 text-[13px]",
  md: "h-10 px-4.5 text-sm",
  lg: "h-12 px-6 text-[15px]",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  block?: boolean;
}

/**
 * Pill buttons with a physical press (slight compression) and quick colour
 * response; the label stays visible while loading.
 */
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
      className={`press inline-flex select-none items-center justify-center gap-2 rounded-full font-medium whitespace-nowrap disabled:cursor-not-allowed ${VARIANTS[variant]} ${SIZES[size]} ${block ? "w-full" : ""} ${className}`}
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
