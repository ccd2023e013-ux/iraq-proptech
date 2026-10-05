import type { Locale } from "@/i18n/config";

import { CITIES, RIVERS, VIEW, project, smoothPath } from "./riverGeometry";

/**
 * The hero illustration: Iraq drawn by its rivers. The Tigris and Euphrates
 * draw themselves once, meet at Qurna and become the Shatt al-Arab, which
 * leads to Basra — the launch market. Cities show live listing counts.
 * Schematic only: no borders, approximate positions.
 */
export function RiverMap({
  locale,
  counts,
  caption,
  animate = true,
}: {
  locale: Locale;
  counts: Record<string, number>;
  caption: string;
  /** Draw the rivers once on load (hero); static elsewhere. */
  animate?: boolean;
}) {
  return (
    <figure className="relative w-full">
      <svg
        viewBox={`-20 -10 ${VIEW.width + 60} ${VIEW.height + 30}`}
        className="h-auto w-full"
        direction="ltr"
        role="img"
        aria-label={caption || undefined}
      >
        <defs>
          <radialGradient id="basra-glow">
            <stop offset="0%" stopColor="var(--spatial-fill)" stopOpacity="0.35" />
            <stop offset="100%" stopColor="var(--spatial-fill)" stopOpacity="0" />
          </radialGradient>
        </defs>
        {(["euphrates", "tigris"] as const).map((river) => (
          <path
            key={river}
            d={smoothPath(RIVERS[river])}
            pathLength={1}
            className={animate ? "river-path" : undefined}
            fill="none"
            stroke="var(--ink-3)"
            strokeOpacity="0.55"
            strokeWidth="2"
            strokeLinecap="round"
          />
        ))}
        <path
          d={smoothPath(RIVERS.shatt)}
          pathLength={1}
          className={animate ? "river-path" : undefined}
          style={{ animationDelay: "1.6s" }}
          fill="none"
          stroke="var(--spatial-fill)"
          strokeWidth="3.5"
          strokeLinecap="round"
        />
        {CITIES.map((city) => {
          const [x, y] = project(city.at);
          const basra = city.slug === "basra";
          const count = counts[city.slug];
          const dx = city.side === "left" ? -12 : 12;
          const anchor = city.side === "left" ? "end" : "start";
          return (
            <g key={city.slug}>
              {basra && <circle cx={x} cy={y} r="42" fill="url(#basra-glow)" />}
              <circle
                cx={x}
                cy={y}
                r={basra ? 6.5 : 4}
                fill={basra ? "var(--spatial-fill)" : "var(--surface)"}
                stroke={basra ? "var(--surface)" : "var(--ink-2)"}
                strokeWidth={basra ? 2.5 : 1.6}
              />
              <text
                x={x + dx}
                y={y - 2}
                textAnchor={anchor}
                className="font-display"
                fontSize={basra ? 19 : 14}
                fontWeight={basra ? 650 : 500}
                fill="var(--ink)"
              >
                {locale === "ar" ? city.ar : city.en}
              </text>
              {count !== undefined && (
                <text
                  x={x + dx}
                  y={y + 15}
                  textAnchor={anchor}
                  fontSize="11.5"
                  fill="var(--ink-3)"
                  className="tabular"
                >
                  {count.toLocaleString(locale === "ar" ? "ar-IQ-u-nu-latn" : "en-US")}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      {caption && (
        <figcaption className="mt-2 text-center text-xs text-ink-3">{caption}</figcaption>
      )}
    </figure>
  );
}
