"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";
import { apiFetch } from "@/lib/api/client";
import { describeError } from "@/lib/errors";
import type { AIEnvelope } from "@/types/ai";

import { ProviderBadge } from "./ProviderBadge";

/** On-demand AI summary of the listing's declared facts (never invents facts). */
export function PropertySummary({
  dict,
  locale,
  propertyId,
}: {
  dict: Dictionary;
  locale: Locale;
  propertyId: string;
}) {
  const a = dict.ai;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [envelope, setEnvelope] = useState<AIEnvelope<{
    summary: string;
    bullets: string[];
  }> | null>(null);

  async function summarize() {
    setBusy(true);
    setError(null);
    try {
      setEnvelope(await apiFetch(`/api/v1/ai/properties/${propertyId}/summary?language=${locale}`));
    } catch (err) {
      setError(describeError(dict, err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title={`${a.summary} · ${a.badge}`}>
      {envelope ? (
        <div className="flex flex-col gap-2" data-testid="ai-summary">
          <ProviderBadge dict={dict} provider={envelope.provider} model={envelope.model} />
          <p className="leading-7 text-sand-900">{envelope.result.summary}</p>
          {envelope.result.bullets?.length > 0 && (
            <ul className="list-disc ps-5 text-sm text-sand-700">
              {envelope.result.bullets.map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
          )}
          <p className="text-xs text-sand-500">{envelope.methodology}</p>
        </div>
      ) : (
        <div className="flex flex-col items-start gap-2">
          <Button size="sm" variant="secondary" loading={busy} onClick={summarize}>
            {a.summarize}
          </Button>
          {error && <p className="text-sm text-danger">{error}</p>}
        </div>
      )}
    </Card>
  );
}
