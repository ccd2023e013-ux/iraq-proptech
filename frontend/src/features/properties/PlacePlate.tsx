import { Icon } from "@/components/ui/Icon";
import { typeGlyph } from "@/lib/photos";

/**
 * Shown where a listing has no photograph of its own in this view (none at
 * all, or a demo photo already shown above): the place, set as type, with the
 * property type's glyph. It says what is known instead of repeating a picture.
 */
export function PlacePlate({
  type,
  place,
  label,
  size = "md",
  className = "",
}: {
  type: string;
  place?: string;
  /** Spoken description (the plate is otherwise decorative). */
  label?: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const glyph = typeGlyph(type);
  return (
    <div
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      className={`relative flex size-full flex-col justify-between overflow-hidden bg-fill text-ink-3 ${
        size === "sm" ? "p-2" : size === "lg" ? "p-6" : "p-4"
      } ${className}`}
    >
      <Icon
        name={glyph}
        className={size === "sm" ? "size-5" : size === "lg" ? "size-8" : "size-6"}
        strokeWidth={1.4}
      />
      {place && size !== "sm" && (
        <span
          className={`font-display leading-tight font-medium text-ink-2 ${
            size === "lg" ? "text-3xl" : "text-lg"
          }`}
        >
          {place}
        </span>
      )}
    </div>
  );
}
