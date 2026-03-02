// =============================================================================
// hooks/useDetections.ts — React Query Hooks for Detection API
// =============================================================================
// Custom hooks wrapping React Query for all detection-related data fetching.
// Components use these hooks instead of calling the API service directly.
//
// WHY HOOKS OVER DIRECT API CALLS?
//   • Automatic caching, deduplication, and background refresh.
//   • Consistent loading/error states across the app.
//   • Pagination handled with keepPreviousData (no flash on page change).
//   • Easy invalidation after mutations (e.g., clear history).
// =============================================================================

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getDetections,
  searchDetections,
  clearDetections,
} from "@/services/anprService";

// ── Query Keys ───────────────────────────────────────────────────────────────
// Structured keys enable granular cache invalidation.
export const detectionKeys = {
  all: ["detections"] as const,
  list: (limit: number, offset: number) =>
    [...detectionKeys.all, "list", limit, offset] as const,
  search: (plate: string, limit: number, offset: number) =>
    [...detectionKeys.all, "search", plate, limit, offset] as const,
};

// ── Paginated Detections ─────────────────────────────────────────────────────
export function useDetections(limit: number = 20, offset: number = 0) {
  return useQuery({
    queryKey: detectionKeys.list(limit, offset),
    queryFn: () => getDetections(limit, offset),
    placeholderData: (prev) => prev, // Keep previous page visible while loading next
  });
}

// ── Search Detections ────────────────────────────────────────────────────────
export function useSearchDetections(
  plate: string,
  limit: number = 20,
  offset: number = 0
) {
  return useQuery({
    queryKey: detectionKeys.search(plate, limit, offset),
    queryFn: () => searchDetections(plate, limit, offset),
    enabled: plate.trim().length > 0, // Only fire when there's a search term
    placeholderData: (prev) => prev,
  });
}

// ── Clear All Detections ─────────────────────────────────────────────────────
export function useClearDetections() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: clearDetections,
    onSuccess: () => {
      // Invalidate all detection queries so they refetch fresh data
      queryClient.invalidateQueries({ queryKey: detectionKeys.all });
    },
  });
}
