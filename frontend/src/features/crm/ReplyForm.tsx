"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/Button";
import type { Dictionary } from "@/i18n";
import { apiFetch } from "@/lib/api/client";
import { describeError } from "@/lib/errors";

export function ReplyForm({ dict, conversationId }: { dict: Dictionary; conversationId: string }) {
  const router = useRouter();
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!body.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/api/v1/conversations/${conversationId}/messages`, {
        method: "POST",
        body: { body: body.trim() },
      });
      setBody("");
      router.refresh();
    } catch (err) {
      setError(describeError(dict, err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-2">
      {error && <p className="text-sm text-danger">{error}</p>}
      <div className="flex gap-2">
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder={dict.messages.reply}
          aria-label={dict.messages.reply}
          rows={2}
          maxLength={4000}
          className="flex-1 rounded-lg border border-sand-200 px-3 py-2 text-sm"
        />
        <Button type="submit" loading={busy}>
          {dict.messages.send}
        </Button>
      </div>
    </form>
  );
}
