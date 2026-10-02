import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/** Liveness of the web service plus the deployed commit (Render: RENDER_GIT_COMMIT). */
export function GET() {
  const commit = process.env.RENDER_GIT_COMMIT || process.env.GIT_COMMIT || null;
  return NextResponse.json(
    { status: "ok", service: "web", commit: commit ? commit.slice(0, 40) : null },
    { headers: { "Cache-Control": "no-store" } },
  );
}
