import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV !== "production";

// Map tiles/styles are runtime-configurable (MAP_STYLE_URL), so images, fonts
// and fetches may come from any https origin; scripts may not (except the
// MapLibre RTL-text plugin, loaded by the map's blob workers from unpkg).
// Next.js needs inline scripts for hydration; the dev server also needs eval
// and its websocket.
const contentSecurityPolicy = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline' blob: https://unpkg.com${isDev ? " 'unsafe-eval'" : ""}`,
  "worker-src 'self' blob:",
  "child-src 'self' blob:",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https:",
  "font-src 'self' data: https:",
  `connect-src 'self' https:${isDev ? " ws: http://localhost:*" : ""}`,
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const nextConfig: NextConfig = {
  // Self-contained server bundle: runs in Docker, Codespaces, or any Node host.
  output: "standalone",
  reactStrictMode: true,
  poweredByHeader: false,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: contentSecurityPolicy },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(self)" },
        ],
      },
    ];
  },
};

export default nextConfig;
