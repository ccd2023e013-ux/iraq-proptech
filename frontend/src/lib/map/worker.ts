/**
 * Same-origin URL of MapLibre's web worker for a given library version.
 *
 * The file is copied there from node_modules by scripts/copy-maplibre-worker.mjs
 * (before `next dev` / `next build`). Versioned name: a deploy that changes the
 * library can never pair a new main bundle with a cached old worker.
 */
export function maplibreWorkerUrl(version: string): string {
  if (!/^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$/.test(version)) {
    throw new Error(`unexpected maplibre-gl version: ${version}`);
  }
  return `/maplibre/maplibre-gl-worker-${version}.mjs`;
}
