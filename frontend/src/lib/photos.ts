/** A glyph for a property type, for the place plate shown instead of a photo
 * (see features/properties/PhotoSet and PlacePlate). */
export function typeGlyph(code: string): "home" | "building" | "area" | "grid" {
  if (["APARTMENT", "BUILDING", "OFFICE"].includes(code)) return "building";
  if (["LAND", "FARM", "ORCHARD"].includes(code)) return "area";
  if (["SHOP", "WAREHOUSE", "FACTORY", "COMMERCIAL", "OTHER"].includes(code)) return "grid";
  return "home";
}
