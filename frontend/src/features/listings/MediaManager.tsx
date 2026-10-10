"use client";

import { useRouter } from "next/navigation";
import { type ChangeEvent, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import type { Dictionary } from "@/i18n";
import { apiFetch } from "@/lib/api/client";
import { describeError } from "@/lib/errors";
import type { Media, Property, PropertyDocument } from "@/types/property";

export function MediaManager({ dict, property }: { dict: Dictionary; property: Property }) {
  const router = useRouter();
  const f = dict.listingForm;
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const media = property.media;

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      router.refresh();
    } catch (err) {
      setError(describeError(dict, err));
    } finally {
      setBusy(false);
    }
  }

  async function onUpload(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    await run(async () => {
      for (const file of files) {
        const form = new FormData();
        form.append("file", file);
        form.append("kind", file.type.startsWith("video/") ? "VIDEO" : "IMAGE");
        await apiFetch<Media>(`/api/v1/properties/${property.id}/media`, {
          method: "POST",
          body: form,
        });
      }
    });
  }

  function move(index: number, delta: number) {
    const ids = media.map((m) => m.id);
    const target = index + delta;
    if (target < 0 || target >= ids.length) return;
    [ids[index], ids[target]] = [ids[target]!, ids[index]!];
    void run(() =>
      apiFetch(`/api/v1/properties/${property.id}/media/order`, {
        method: "PUT",
        body: { media_ids: ids },
      }),
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {error && <Alert tone="error">{error}</Alert>}
      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {media.map((m, i) => (
          <li key={m.id} className="overflow-hidden rounded-lg border border-sand-200 bg-sand-50">
            {m.kind === "VIDEO" ? (
              <video src={m.url} className="aspect-[4/3] w-full object-cover" controls />
            ) : (
              // eslint-disable-next-line @next/next/no-img-element -- served by our own API
              <img
                src={m.thumbnail_url ?? m.url}
                alt={m.caption ?? ""}
                loading="lazy"
                className="aspect-[4/3] w-full object-cover"
              />
            )}
            <div className="flex justify-between gap-1 p-1.5">
              <Button size="sm" variant="ghost" aria-label={f.moveUp} onClick={() => move(i, -1)}>
                ↑
              </Button>
              <Button size="sm" variant="ghost" aria-label={f.moveDown} onClick={() => move(i, 1)}>
                ↓
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="text-danger"
                onClick={() =>
                  run(() =>
                    apiFetch(`/api/v1/properties/${property.id}/media/${m.id}`, {
                      method: "DELETE",
                    }),
                  )
                }
              >
                {f.remove}
              </Button>
            </div>
          </li>
        ))}
      </ul>
      <label className="inline-flex w-fit cursor-pointer items-center gap-2 rounded-lg bg-brand-700 px-4 py-2 text-sm font-medium text-on-accent hover:bg-brand-600">
        {busy ? dict.auth.loading : f.uploadImage}
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp,video/mp4,video/webm"
          multiple
          className="sr-only"
          disabled={busy}
          onChange={onUpload}
        />
      </label>
      <p className="text-xs text-sand-500">{f.uploadHint}</p>
    </div>
  );
}

export function DocumentManager({
  dict,
  propertyId,
  documents,
}: {
  dict: Dictionary;
  propertyId: string;
  documents: PropertyDocument[];
}) {
  const router = useRouter();
  const f = dict.listingForm;
  const [docType, setDocType] = useState("TITLE_DEED");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("doc_type", docType);
      await apiFetch(`/api/v1/properties/${propertyId}/documents`, { method: "POST", body: form });
      router.refresh();
    } catch (err) {
      setError(describeError(dict, err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-sand-500">{f.documentsNote}</p>
      {error && <Alert tone="error">{error}</Alert>}
      <ul className="divide-y divide-sand-100 text-sm">
        {documents.map((d) => (
          <li key={d.id} className="flex items-center justify-between gap-3 py-2">
            <a href={`/api/v1/documents/${d.id}`} className="truncate text-accent underline">
              {d.filename}
            </a>
            <span className="text-xs text-sand-500">
              {dict.listing.docTypes[d.doc_type as keyof typeof dict.listing.docTypes]}
            </span>
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap items-center gap-3">
        <select
          value={docType}
          onChange={(e) => setDocType(e.target.value)}
          className="h-10 surface-1 rounded-2xl px-3 text-sm"
        >
          {Object.entries(dict.listing.docTypes).map(([code, label]) => (
            <option key={code} value={code}>
              {label}
            </option>
          ))}
        </select>
        <label className="inline-flex cursor-pointer items-center rounded-lg border border-sand-200 px-4 py-2 text-sm font-medium hover:border-brand-300">
          {busy ? dict.auth.loading : f.uploadDocument}
          <input
            type="file"
            accept="application/pdf,image/jpeg,image/png,image/webp"
            className="sr-only"
            disabled={busy}
            onChange={onUpload}
          />
        </label>
      </div>
    </div>
  );
}
