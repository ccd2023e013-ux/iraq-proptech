// Copies MapLibre's web worker into public/ so the site serves it itself.
//
// maplibre-gl 6 is ESM-only and starts its worker from a URL computed at run
// time next to its own module (import.meta.url). Once Next.js bundles the
// library into /_next/static/chunks/, nothing is served at that URL and the
// map never draws ("Worker failed to load"). The worker is a single
// self-contained ES module, so it is copied to public/maplibre/ under a
// versioned name and the map points MapLibre at it with setWorkerUrl()
// (src/lib/map/worker.ts). Same origin, so the CSP's `worker-src 'self'`
// already allows it. Runs before `next dev` and `next build` (pre-scripts).
import { copyFileSync, mkdirSync, readFileSync, rmSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { version } = JSON.parse(readFileSync(require.resolve("maplibre-gl/package.json"), "utf8"));
const source = require.resolve("maplibre-gl/dist/maplibre-gl-worker.mjs");

const target = join(dirname(fileURLToPath(import.meta.url)), "..", "public", "maplibre");
rmSync(target, { recursive: true, force: true }); // drop workers of older versions
mkdirSync(target, { recursive: true });
copyFileSync(source, join(target, `maplibre-gl-worker-${version}.mjs`));
console.log(`maplibre worker ${version} → public/maplibre/`);
