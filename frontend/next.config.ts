import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV !== "production";

// Map tiles/styles are runtime-configurable (MAP_STYLE_URL), so images, fonts
// and fetches may come from any https origin; scripts may not. (No third-party
// script origin at all since MapLibre 6: its worker is served by this site and
// Arabic labels need no RTL-text plugin from unpkg any more.)
// Next.js needs inline scripts for hydration; the dev server also needs eval
// and its websocket.
const contentSecurityPolicy = [
  "default-src 'self'",
  // 'wasm-unsafe-eval' allows WebAssembly but not JS eval (kept until it is verified
  // that no MapLibre 6 decoder needs WebAssembly; it was added for the RTL plugin).
  `script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval' blob:${isDev ? " 'unsafe-eval'" : ""}`,
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
