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
      ? "bg-gold-100 text-gold-700 shadow-[inset_0_0_0_1px_var(--gold-line)]"
      : provider === "platform"
        ? "bg-fill text-ink-2"
        : "bg-accent-tint text-accent";
  return (
    <span
      data-ai-provider={provider}
      className={`inline-block rounded-[var(--radius-tag)] px-2 py-0.5 text-[12px] leading-5 font-medium ${tone}`}
    >
      {providerLabel(dict, provider, model)}
    </span>
  );
}
