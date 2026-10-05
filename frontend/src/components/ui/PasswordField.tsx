"use client";

import { useState } from "react";

import { TextField, type TextFieldProps } from "./TextField";

/** Password input with a show/hide control (the label stays the accessible name). */
export function PasswordField({
  showLabel,
  hideLabel,
  ...props
}: Omit<TextFieldProps, "type"> & { showLabel: string; hideLabel: string }) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <TextField {...props} type={visible ? "text" : "password"} className="[&_input]:pe-20" />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        aria-pressed={visible}
        className="absolute end-2 top-[2.1rem] h-8 rounded-full px-3 text-xs font-medium text-ink-2 hover:bg-fill-strong"
      >
        {visible ? hideLabel : showLabel}
      </button>
    </div>
  );
}
