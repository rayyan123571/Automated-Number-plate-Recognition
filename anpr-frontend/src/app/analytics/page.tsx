// =============================================================================
// app/analytics/page.tsx — Analytics Dashboard (React Query + Recharts)
// =============================================================================
// Premium admin dashboard that visualises all detection data:
//   • DB-backed stats cards (total, avg confidence, processing, high-conf %)
//   • Recharts analytics (confidence trend line + daily bar chart)
//   • Full detection table with search, pagination, and skeleton loading
//   • Clear-all mutation with confirmation
//
// All data flows: SQLite → FastAPI → React Query cache → Components
// =============================================================================

"use client";

import { useState, useCallback } from "react";
import { motion } from "framer-motion";
import {
  BarChart3,
  Search,
  Trash2,
  RefreshCw,
  Database,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Button } from "@/components/ui/Button";
import { DBStatsCards } from "@/components/dashboard/DBStatsCards";
import { AnalyticsCharts } from "@/components/dashboard/AnalyticsCharts";
import { DetectionTable } from "@/components/dashboard/DetectionTable";
import {
  useDetections,
  useSearchDetections,
  useClearDetections,
  detectionKeys,
} from "@/hooks/useDetections";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const PAGE_SIZE = 10;
const DEBOUNCE_MS = 500;

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function AnalyticsPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);
  const [searchInput, setSearchInput] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [debounceTimer, setDebounceTimer] = useState<NodeJS.Timeout | null>(
    null
  );

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

  // Always fetch ALL records for stats + charts (max 500)
  const allQuery = useDetections(500, 0);

  // Paginated list (either normal or search)
  const listQuery = useDetections(PAGE_SIZE, page * PAGE_SIZE);
  const searchQuery = useSearchDetections(
    debouncedSearch,
    PAGE_SIZE,
    page * PAGE_SIZE
  );

  // Pick whichever query is active for the table
  const activeQuery = isSearching ? searchQuery : listQuery;
  const records = activeQuery.data?.results ?? [];
  const total = activeQuery.data?.total ?? 0;

  // All records for stats & charts
  const allRecords = allQuery.data?.results ?? [];

  // ── Mutations ───────────────────────────────────────────────────────
  const clearMutation = useClearDetections();

  const handleClear = useCallback(() => {
    if (!confirm("Delete ALL detection history? This cannot be undone.")) return;
    clearMutation.mutate();
  }, [clearMutation]);

  const handleRefresh = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: detectionKeys.all });
  }, [queryClient]);

  // ── Page navigation ─────────────────────────────────────────────────
  const handlePageChange = useCallback((newPage: number) => {
    setPage(newPage);
    // Scroll to top of table smoothly
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  return (
    <DashboardLayout>
      <div className="space-y-8">
        {/* ── Page Header ──────────────────────────────────────────────── */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"
        >
          <div>
            <h1 className="flex items-center gap-2.5 text-2xl font-bold text-white">
              <BarChart3 className="h-6 w-6 text-cyan-400" />
              Analytics Dashboard
            </h1>
            <p className="mt-1 text-sm text-neutral-400">
              Real-time insights from{" "}
              <span className="font-medium text-cyan-400">
                {allQuery.data?.total ?? "–"}
              </span>{" "}
              detection records
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleRefresh}
              disabled={allQuery.isFetching}
            >
              <RefreshCw
                className={`mr-1.5 h-3.5 w-3.5 ${
                  allQuery.isFetching ? "animate-spin" : ""
                }`}
              />
              Refresh
            </Button>
            {(allQuery.data?.total ?? 0) > 0 && (
              <Button
                variant="danger"
                size="sm"
                onClick={handleClear}
                disabled={clearMutation.isPending}
              >
                <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                {clearMutation.isPending ? "Clearing…" : "Clear All"}
              </Button>
            )}
          </div>
        </motion.div>

        {/* ── Stats Cards ──────────────────────────────────────────────── */}
        <DBStatsCards records={allRecords} isLoading={allQuery.isLoading} />

        {/* ── Charts ───────────────────────────────────────────────────── */}
        <AnalyticsCharts records={allRecords} />

        {/* ── Search Bar ───────────────────────────────────────────────── */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="flex items-center gap-3"
        >
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-neutral-500" />
            <input
              type="text"
              placeholder="Search plate numbers..."
              value={searchInput}
              onChange={(e) => handleSearchChange(e.target.value)}
              className="w-full rounded-xl border border-white/10 bg-white/5 py-2.5 pl-10 pr-4 text-sm text-neutral-300 outline-none placeholder:text-neutral-600 transition-colors focus:border-cyan-500/50 focus:bg-white/[0.07]"
            />
            {isSearching && (
              <button
                onClick={() => {
                  setSearchInput("");
                  setDebouncedSearch("");
                  setPage(0);
                }}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-500 hover:text-neutral-300"
              >
                ×
              </button>
            )}
          </div>
          <div className="flex items-center gap-2 text-xs text-neutral-500">
            <Database className="h-3.5 w-3.5" />
            <span>
              {total} result{total !== 1 && "s"}
              {isSearching && " found"}
            </span>
          </div>
        </motion.div>

        {/* ── Detection Table ──────────────────────────────────────────── */}
        <DetectionTable
          records={records}
          total={total}
          page={page}
          pageSize={PAGE_SIZE}
          isLoading={activeQuery.isLoading}
          onPageChange={handlePageChange}
        />
      </div>
    </DashboardLayout>
  );
}
