# Cloudflare (frontend hosting option) — decision record

The online-development brief asked to prefer **Cloudflare Pages** for the
Next.js frontend "if technically appropriate". It is **not used for now**;
the frontend runs as the same Docker image on Render (or any container host).

## Why not Cloudflare Pages/Workers today

| Requirement of this frontend | On Cloudflare |
| --- | --- |
| Next.js 15 server rendering, middleware, route handlers | Needs the OpenNext Cloudflare adapter (`@opennextjs/cloudflare`) and a Workers build; the older `next-on-pages` path for Pages is deprecated |
| Streaming request-body proxy (`/api/v1/*` → API, `duplex: "half"`, multipart uploads up to 100 MB) | Workers' request-size and CPU limits on the free plan are far below a 100 MB video upload |
| One artifact for every environment (`output: "standalone"` Docker image) | Would require a second, Cloudflare-specific build to maintain and test |

Adopting it would add a platform-specific adapter and build to the codebase
for a temporary host — the technical debt the brief asks to avoid. The
Docker image already runs unchanged in Codespaces, CI, Render and on the
production PC.

## Where Cloudflare *is* useful (free, no code changes)

- **Cloudflare Tunnel** (`cloudflared`) to publish the production PC without
  opening router ports — documented in
  [MIGRATE-TO-LOCAL-PC.md](MIGRATE-TO-LOCAL-PC.md#4-publish-safely). It is a
  TLS-terminating proxy in front of the frontend, so keep
  `TRUSTED_PROXY_HOPS=1`.
- **R2** as S3-compatible media storage (`STORAGE_BACKEND=s3`,
  `S3_ENDPOINT_URL=https://<account>.r2.cloudflarestorage.com`).
- DNS for a custom domain.

## Revisit when

- The frontend no longer needs large uploads through its own origin (e.g.
  direct-to-bucket presigned uploads), and
- OpenNext's Cloudflare adapter is mature enough to justify a second build in
  CI.

Vercel Hobby is another zero-config option for Next.js, but its terms limit
it to non-commercial use, so it is not recommended for a business platform.
