/** Theme choice shared by the server layout and the client toggle. */
export type ThemeChoice = "system" | "light" | "dark";
export const THEME_COOKIE = "theme";
/** MAKAN's premium default; light and the device setting stay one tap away. */
export const DEFAULT_THEME: ThemeChoice = "dark";
const ORDER: ThemeChoice[] = ["dark", "light", "system"];

export function parseTheme(value: string | undefined | null): ThemeChoice {
  return value === "light" || value === "dark" || value === "system" ? value : DEFAULT_THEME;
}

export function nextTheme(current: ThemeChoice): ThemeChoice {
  return ORDER[(ORDER.indexOf(current) + 1) % ORDER.length] as ThemeChoice;
}
