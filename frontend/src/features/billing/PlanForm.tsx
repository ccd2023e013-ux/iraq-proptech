"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/Button";
import type { Dictionary } from "@/i18n";
import { apiFetch } from "@/lib/api/client";
import { describeError } from "@/lib/errors";

const INPUT = "field";

export function PlanForm({ dict }: { dict: Dictionary }) {
  const router = useRouter();
  const b = dict.billing;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const element = event.currentTarget;
    const form = new FormData(element);
    const text = (k: string) => String(form.get(k) ?? "").trim();
    setBusy(true);
    setError(null);
    try {
      await apiFetch("/api/v1/admin/billing/plans", {
        method: "POST",
        body: {
          code: text("code"),
          kind: text("kind"),
          name_ar: text("name_ar"),
          name_en: text("name_en"),
          price_amount: text("price_amount"),
          currency: text("currency"),
          duration_days: Number(text("duration_days")),
          featured_credits: Number(text("featured_credits") || "0"),
          is_demo: form.get("is_demo") === "on",
        },
      });
      element.reset();
      router.refresh();
    } catch (err) {
      setError(describeError(dict, err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="grid gap-3 text-sm sm:grid-cols-2">
      <label className="flex flex-col gap-1">
        {b.code}
        <input name="code" required pattern="[a-z0-9_\-]+" dir="ltr" className={INPUT} />
      </label>
      <label className="flex flex-col gap-1">
        {dict.billing.kinds.SUBSCRIPTION} / {dict.billing.kinds.PROMOTION}
        <select name="kind" className={INPUT}>
          <option value="PROMOTION">{b.kinds.PROMOTION}</option>
          <option value="SUBSCRIPTION">{b.kinds.SUBSCRIPTION}</option>
        </select>
      </label>
      <label className="flex flex-col gap-1">
        {b.nameAr}
        <input name="name_ar" required className={INPUT} />
      </label>
      <label className="flex flex-col gap-1">
        {b.nameEn}
        <input name="name_en" required dir="ltr" className={INPUT} />
      </label>
      <label className="flex flex-col gap-1">
        {b.price}
        <input
          name="price_amount"
          required
          inputMode="decimal"
          pattern="[0-9]+(\.[0-9]{1,2})?"
          dir="ltr"
          className={INPUT}
        />
      </label>
      <label className="flex flex-col gap-1">
        IQD / USD
        <select name="currency" className={INPUT}>
          <option value="IQD">IQD</option>
          <option value="USD">USD</option>
        </select>
      </label>
      <label className="flex flex-col gap-1">
        {b.durationDays}
        <input name="duration_days" type="number" min={1} max={366} required className={INPUT} />
      </label>
      <label className="flex flex-col gap-1">
        {b.featuredCredits}
        <input name="featured_credits" type="number" min={0} max={1000} className={INPUT} />
      </label>
      <label className="flex items-center gap-2">
        <input type="checkbox" name="is_demo" defaultChecked />
        {b.markDemo}
      </label>
      <p className="text-xs text-sand-500 sm:col-span-2">{b.priceImmutable}</p>
      <div className="sm:col-span-2">
        <Button type="submit" loading={busy}>
          {b.create}
        </Button>
        {error && (
          <p role="alert" className="mt-2 text-danger">
            {error}
          </p>
        )}
      </div>
    </form>
  );
}
