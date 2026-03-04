// =============================================================================
// components/providers/QueryProvider.tsx — React Query Provider
// =============================================================================
// WHY REACT QUERY OVER useEffect?
//   • Automatic caching → avoids redundant network requests.
//   • Background refetching → data stays fresh without manual polling.
//   • Built-in loading / error / success states → cleaner components.
//   • Automatic retries with exponential backoff on failure.
//   • Stale-while-revalidate pattern → instant UI + background update.
//   • Deduplication → multiple components requesting the same data
//     trigger only one HTTP call.
//   • Pagination helpers (keepPreviousData) → no flash on page change.
//
// This provider must wrap the entire app so every component can use
// useQuery / useMutation hooks.
// =============================================================================

"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export function QueryProvider({ children }: { children: React.ReactNode }) {
  // Create a stable QueryClient instance per-session (not per-render).
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,       // Data is "fresh" for 30s
            gcTime: 5 * 60_000,      // Garbage-collect after 5 min
            retry: 2,                // Retry failed requests twice
            refetchOnWindowFocus: true, // Refresh when tab regains focus
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
