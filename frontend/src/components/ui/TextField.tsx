"use client";

import { type InputHTMLAttributes, type ReactNode, useId } from "react";

export interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  hint?: ReactNode;
  error?: string | null;
}

export function TextField({ label, hint, error, className = "", id, ...rest }: TextFieldProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const describedBy = [hint ? `${inputId}-hint` : null, error ? `${inputId}-error` : null]
    .filter(Boolean)
    .join(" ");
  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      <label htmlFor={inputId} className="text-sm font-medium text-ink">
        {label}
      </label>
      <input
        id={inputId}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy || undefined}
        className={`h-12 rounded-[var(--radius-control)] bg-fill px-4 text-ink ring-1 ring-inset transition duration-[var(--duration-quick)] placeholder:text-ink-3 focus:bg-surface focus:ring-2 focus:ring-accent focus:outline-none ${error ? "ring-danger" : "ring-transparent"}`}
        {...rest}
      />
      {hint && !error && (
        <p id={`${inputId}-hint`} className="text-xs text-sand-500">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${inputId}-error`} className="text-xs text-danger" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
