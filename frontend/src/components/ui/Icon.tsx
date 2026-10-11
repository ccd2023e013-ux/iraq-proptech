import type { SVGProps } from "react";

/**
 * MAKAN icon family: one 24-unit grid, 1.75 stroke, round caps and joins,
 * no fills except where a state needs one (heart). Every icon in the product
 * comes from here so the set stays coherent.
 */
const PATHS = {
  search: ["M10.5 18a7.5 7.5 0 1 1 0-15 7.5 7.5 0 0 1 0 15Z", "m16 16 4.5 4.5"],
  map: ["M9 4 3.5 6v14L9 18l6 2 5.5-2V4L15 6 9 4Z", "M9 4v14M15 6v14"],
  layers: [
    "m12 3.5 8.5 4.75L12 13 3.5 8.25 12 3.5Z",
    "m3.5 12.25 8.5 4.75 8.5-4.75",
    "m3.5 16.25 8.5 4.25 8.5-4.25",
  ],
  home: ["M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-4.5v-6h-5v6H5a1 1 0 0 1-1-1v-9.5Z"],
  grid: ["M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z"],
  pin: [
    "M12 21s7-5.6 7-11.5a7 7 0 1 0-14 0C5 15.4 12 21 12 21Z",
    "M12 12a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z",
  ],
  locate: [
    "M12 19a7 7 0 1 0 0-14 7 7 0 0 0 0 14Z",
    "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z",
    "M12 2v3M12 19v3M2 12h3M19 12h3",
  ],
  draw: ["M5 18 9 6l10 4-6 9-8-1Z", "M5 18h0M9 6h0M19 10h0M13 19h0"],
  list: ["M9 6h11M9 12h11M9 18h11", "M4.5 6h.01M4.5 12h.01M4.5 18h.01"],
  // Analysis: a measured frame around a focus point (no robots, no brains).
  insight: [
    "M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3",
    "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z",
  ],
  market: ["M4 20V10M10 20V4M16 20v-7M22 20H2"],
  future: ["M3 20h18", "M5 20v-6l4-3v9M9 20V8l5-4v16M14 20v-9l5 3v6"],
  heart: [
    "M12 20.5s-7.5-4.6-9.2-9.1C1.6 8 3.7 4.5 7.1 4.5c2 0 3.4 1 4.9 2.9 1.5-1.9 2.9-2.9 4.9-2.9 3.4 0 5.5 3.5 4.3 6.9-1.7 4.5-9.2 9.1-9.2 9.1Z",
  ],
  bookmark: ["M6.5 3.5h11a1 1 0 0 1 1 1V21l-6.5-4-6.5 4V4.5a1 1 0 0 1 1-1Z"],
  filter: [
    "M4 7h10M18 7h2M4 17h4M12 17h8",
    "M16 9a2 2 0 1 0 0-4 2 2 0 0 0 0 4ZM10 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z",
  ],
  settings: [
    "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z",
    "M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z",
  ],
  arrow: ["M5 12h14M13 6l6 6-6 6"],
  chevron: ["m9 6 6 6-6 6"],
  "chevron-down": ["m6 9 6 6 6-6"],
  close: ["M6 6l12 12M18 6 6 18"],
  plus: ["M12 5v14M5 12h14"],
  menu: ["M4 8h16M4 16h16"],
  bell: ["M6 9a6 6 0 1 1 12 0c0 6 2.5 7.5 2.5 7.5h-17S6 15 6 9Z", "M10 20a2.2 2.2 0 0 0 4 0"],
  user: ["M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z", "M4.5 20.5a7.5 7.5 0 0 1 15 0"],
  sun: [
    "M12 16.5a4.5 4.5 0 1 0 0-9 4.5 4.5 0 0 0 0 9Z",
    "M12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4 6 18M18 6l1.4-1.4",
  ],
  moon: ["M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5Z"],
  bed: [
    "M3 18V7M3 14h18v4M21 14v-2.5A2.5 2.5 0 0 0 18.5 9H11v5",
    "M7 12a1.75 1.75 0 1 0 0-3.5A1.75 1.75 0 0 0 7 12Z",
  ],
  bath: [
    "M4 12h16v2.5A4.5 4.5 0 0 1 15.5 19h-7A4.5 4.5 0 0 1 4 14.5V12Z",
    "M6 12V6a2 2 0 0 1 3.7-1M7 19l-1 2M17 19l1 2",
  ],
  area: ["M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5"],
  check: ["m5 12.5 4.5 4.5L19 7.5"],
  info: ["M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z", "M12 11v5M12 8h.01"],
  alert: ["M12 3.5 21.5 20h-19L12 3.5Z", "M12 10v4.5M12 17.5h.01"],
  refresh: [
    "M20 11a8 8 0 0 0-14.6-4.5L4 8",
    "M4 4v4h4M4 13a8 8 0 0 0 14.6 4.5L20 16",
    "M20 20v-4h-4",
  ],
  back: ["M19 12H5M11 6l-6 6 6 6"],
  // 3D buildings: an isometric block.
  cube: ["M12 3 4 7.5v9L12 21l8-4.5v-9L12 3Z", "M4 7.5 12 12l8-4.5M12 12v9"],
} as const;

export type IconName = keyof typeof PATHS;

/** Icons that point somewhere mirror in right-to-left layouts. */
const DIRECTIONAL: ReadonlySet<IconName> = new Set<IconName>(["arrow", "chevron", "back"]);

export function Icon({
  name,
  className = "size-5",
  strokeWidth = 1.75,
  ...rest
}: { name: IconName; strokeWidth?: number } & Omit<SVGProps<SVGSVGElement>, "name">) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={DIRECTIONAL.has(name) ? `${className} rtl:-scale-x-100` : className}
      {...rest}
    >
      {PATHS[name].map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  );
}
