import Link from "next/link";
import { notFound } from "next/navigation";

import { ReplyForm } from "@/features/crm/ReplyForm";
import { formatDateTime } from "@/features/crm/labels";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { ApiError } from "@/lib/api/client";
import { serverApiFetch } from "@/lib/api/server";
import { requireUser } from "@/lib/auth/guard";
import type { ChatMessage, Conversation } from "@/types/crm";

export const dynamic = "force-dynamic";

export default async function ThreadPage({ params }: { params: Promise<{ id: string }> }) {
  await requireUser();
  const { id } = await params;
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const m = dict.messages;
  let messages: ChatMessage[];
  try {
    messages = await serverApiFetch<ChatMessage[]>(
      `/api/v1/conversations/${encodeURIComponent(id)}/messages`,
    );
  } catch (error) {
    if (error instanceof ApiError && [404, 422].includes(error.status)) notFound();
    throw error;
  }
  const conversation = (await serverApiFetch<Conversation[]>("/api/v1/me/conversations")).find(
    (c) => c.id === id,
  );

  return (
    <div className="page flex flex-col gap-4 pb-8">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Link href="/messages" className="text-sm text-accent">
          {m.back}
        </Link>
        {conversation?.lead_id && (
          <Link
            href={`/dashboard/crm/leads/${conversation.lead_id}`}
            className="text-sm text-accent"
          >
            {m.openLead}
          </Link>
        )}
      </div>
      {conversation?.property && (
        <h1 className="text-lg font-bold text-brand-900">
          <Link href={`/properties/${conversation.property.id}`} className="hover:underline">
            {locale === "en" && conversation.property.title_en
              ? conversation.property.title_en
              : conversation.property.title_ar}
          </Link>
        </h1>
      )}
      <ol className="flex flex-col gap-3">
        {messages.map((msg) => (
          <li key={msg.id} className={`flex ${msg.mine ? "justify-start" : "justify-end"}`}>
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm ${msg.mine ? "bg-brand-700 text-on-accent" : "border border-sand-200 bg-surface text-sand-900"}`}
            >
              <p className="whitespace-pre-line">{msg.body}</p>
              <p className={`mt-1 text-[11px] ${msg.mine ? "text-brand-100" : "text-sand-500"}`}>
                {msg.mine ? m.you : msg.sender?.full_name} ·{" "}
                {formatDateTime(msg.created_at, locale)}
              </p>
            </div>
          </li>
        ))}
      </ol>
      <ReplyForm dict={dict} conversationId={id} />
    </div>
  );
}
