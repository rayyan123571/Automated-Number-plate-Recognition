// =============================================================================
// app/history/page.tsx — Detection History Page (React Query)
// =============================================================================
// Full-featured history page powered by React Query hooks.
// Replaces the previous useEffect-based implementation with:
//   • React Query caching & background refresh
//   • Debounced search (500ms)
//   • Clear-all mutation with cache invalidation
//   • Skeleton loading states
//   • Animated row transitions
// =============================================================================

"use client";

import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Clock,
  Search,
  Trash2,
  ChevronLeft,
  ChevronRight,
  ScanLine,
  Database,
  RefreshCw,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  useDetections,
  useSearchDetections,
  useClearDetections,
  detectionKeys,
} from "@/hooks/useDetections";

const PAGE_SIZE = 15;
const DEBOUNCE_MS = 500;

export default function HistoryPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);
  const [searchInput, setSearchInput] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [debounceTimer, setDebounceTimer] = useState<NodeJS.Timeout | null>(null);

  // Debounced search handler
  const handleSearchChange = useCallback(
    (value: string) => {
      setSearchInput(value);
      setPage(0);
      if (debounceTimer) clearTimeout(debounceTimer);
      const timer = setTimeout(() => setDebouncedSearch(value.trim()), DEBOUNCE_MS);
      setDebounceTimer(timer);
    },
    [debounceTimer]
  );

  // ── Queries ─────────────────────────────────────────────────────────
  const isSearching = debouncedSearch.length > 0;
  const listQuery = useDetections(PAGE_SIZE, page * PAGE_SIZE);
  const searchQueryHook = useSearchDetections(
    debouncedSearch,
    PAGE_SIZE,
    page * PAGE_SIZE
  );

  const activeQuery = isSearching ? searchQueryHook : listQuery;
  const records = activeQuery.data?.results ?? [];
  const total = activeQuery.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const isLoading = activeQuery.isLoading;

  // ── Mutations ───────────────────────────────────────────────────────
  const clearMutation = useClearDetections();

  const handleClear = useCallback(() => {
    if (!confirm("Delete all detection history?")) return;
    clearMutation.mutate();
  }, [clearMutation]);

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-bold text-white">
              <Database className="h-6 w-6 text-cyan-400" />
              Detection History
            </h1>
            <p className="mt-1 text-sm text-neutral-400">
              {total} record{total !== 1 && "s"} stored in database
            </p>
          </div>

          <div className="flex items-center gap-3">
            {/* Search */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-neutral-500" />
              <input
                type="text"
                placeholder="Search plates..."
                value={searchInput}
                onChange={(e) => handleSearchChange(e.target.value)}
                className="w-48 rounded-xl border border-white/10 bg-white/5 py-2 pl-9 pr-3 text-sm text-neutral-300 outline-none placeholder:text-neutral-600 focus:border-cyan-500/50 sm:w-56"
              />
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() =>
                queryClient.invalidateQueries({ queryKey: detectionKeys.all })
              }
              disabled={activeQuery.isFetching}
            >
              <RefreshCw
                className={`h-3.5 w-3.5 ${
                  activeQuery.isFetching ? "animate-spin" : ""
                }`}
              />
            </Button>
            {total > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleClear}
                disabled={clearMutation.isPending}
              >
                <Trash2 className="mr-1 h-3.5 w-3.5" />
                Clear All
              </Button>
            )}
          </div>
        </div>

        {/* Table */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-cyan-400" />
              Records
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              /* Skeleton loading */
              <div className="space-y-2">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-4 rounded-xl border border-white/5 bg-white/[0.02] px-4 py-3"
                  >
                    <div className="flex-1 space-y-2">
                      <div className="h-4 w-24 animate-pulse rounded bg-white/5" />
                      <div className="h-3 w-40 animate-pulse rounded bg-white/5" />
                    </div>
                    <div className="h-5 w-12 animate-pulse rounded bg-white/5" />
                  </div>
                ))}
              </div>
            ) : records.length === 0 ? (
              <div className="py-16 text-center">
                <ScanLine className="mx-auto mb-3 h-10 w-10 text-neutral-700" />
                <p className="text-sm text-neutral-500">
                  {isSearching
                    ? "No plates matching your search"
                    : "No detections yet"}
                </p>
                <p className="text-xs text-neutral-600">
                  {isSearching
                    ? "Try a different search term"
                    : "Upload an image on the Dashboard to get started"}
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                <AnimatePresence mode="popLayout">
                  {records.map((record, index) => (
                    <motion.div
                      key={record.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -10 }}
                      transition={{ delay: index * 0.03 }}
                      className="flex items-center gap-4 rounded-xl border border-white/5 bg-white/[0.02] px-4 py-3 transition-all duration-200 hover:border-white/10 hover:bg-white/[0.05]"
                    >
                      {/* Plate text */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          {record.plate_text ? (
                            <Badge variant="info">{record.plate_text}</Badge>
                          ) : (
                            <Badge variant="danger">No text</Badge>
                          )}
                          <span className="text-[10px] text-neutral-600">
                            {record.id.slice(0, 8)}...
                          </span>
                        </div>
                        <p className="mt-1 text-[10px] text-neutral-500">
                          {new Date(record.detected_at).toLocaleString()} ·{" "}
                          {(record.processing_time / 1000).toFixed(2)}s
                        </p>
                      </div>

                      {/* Confidence scores */}
                      <div className="hidden flex-col items-end gap-0.5 sm:flex">
                        <span className="text-xs text-neutral-400">
                          Det: {(record.detection_confidence * 100).toFixed(0)}%
                        </span>
                        <span className="text-xs text-neutral-400">
                          OCR: {(record.ocr_confidence * 100).toFixed(0)}%
                        </span>
                      </div>

                      {/* Combined badge */}
                      <Badge
                        variant={
                          record.confidence >= 0.7
                            ? "success"
                            : record.confidence >= 0.4
                            ? "warning"
                            : "danger"
                        }
                      >
                        {(record.confidence * 100).toFixed(0)}%
                      </Badge>
                    </motion.div>
                  ))}
                </AnimatePresence>
              </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="mt-4 flex items-center justify-between border-t border-white/5 pt-4">
                <p className="text-xs text-neutral-500">
                  Page {page + 1} of {totalPages}
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setPage((p) => Math.max(0, p - 1))}
                    disabled={page === 0}
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      setPage((p) => Math.min(totalPages - 1, p + 1))
                    }
                    disabled={page >= totalPages - 1}
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
