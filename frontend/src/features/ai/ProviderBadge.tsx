import type { Dictionary } from "@/i18n";

/**
 * Says exactly where an AI answer came from. The mock provider is labelled as
 * a simulation so it is never mistaken for a real language model; statistical
 * analyses say they use platform data only.
 */
export function providerLabel(dict: Dictionary, provider: string, model?: string): string {
  if (provider === "mock") return dict.ai.providerMock;
  if (provider === "platform") return dict.ai.providerPlatform;
  return `${dict.ai.providerLive} (${provider}${model ? ` · ${model}` : ""})`;
}

export function ProviderBadge({
  dict,
  provider,
  model,
}: {
  dict: Dictionary;
  provider: string;
  model?: string;
}) {
  const tone =
    provider === "mock"
      ? "bg-gold-100 text-gold-700"
      : provider === "platform"
        ? "bg-sand-100 text-sand-700"
        : "bg-brand-50 text-brand-800";
  return (
    <span
      data-ai-provider={provider}
      className={`inline-block rounded px-1.5 py-0.5 text-[11px] font-medium ${tone}`}
    >
      {providerLabel(dict, provider, model)}
    </span>
  );
}
