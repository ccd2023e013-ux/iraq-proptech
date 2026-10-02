import "server-only";

import { ApiError } from "@/lib/api/client";
import { serverApiFetch } from "@/lib/api/server";
import { getCurrentUser } from "@/lib/auth/session";
import type { PropertyCard } from "@/types/property";

export interface SearchResult {
  items: PropertyCard[];
  total: number;
  page: number;
  page_size: number;
  /** The validated, canonical filters the API actually applied. */
  filters: Record<string, unknown>;
}

export async function runSearch(query: string): Promise<SearchResult | { error: string }> {
  try {
    return await serverApiFetch<SearchResult>(`/api/v1/search/properties?${query}`);
  } catch (error) {
    if (error instanceof ApiError) return { error: error.code };
    throw error;
  }
}

/** IDs the signed-in user has saved (empty when signed out). */
export async function favoriteIds(): Promise<Set<string>> {
  const me = await getCurrentUser();
  if (!me || !me.permissions.includes("favorites.manage")) return new Set();
  try {
    return new Set(await serverApiFetch<string[]>("/api/v1/me/favorites/ids"));
  } catch {
    return new Set();
  }
}
