/** Theme choice shared by the server layout and the client toggle. */
export type ThemeChoice = "system" | "light" | "dark";
export const THEME_COOKIE = "theme";
const ORDER: ThemeChoice[] = ["system", "light", "dark"];

export function parseTheme(value: string | undefined | null): ThemeChoice {
  return value === "light" || value === "dark" ? value : "system";
}

export function nextTheme(current: ThemeChoice): ThemeChoice {
  return ORDER[(ORDER.indexOf(current) + 1) % ORDER.length] as ThemeChoice;
}
