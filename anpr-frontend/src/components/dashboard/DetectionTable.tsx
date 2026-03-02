// =============================================================================
// components/dashboard/DetectionTable.tsx — Premium Detection History Table
// =============================================================================
// Displays detection records from the SQLite database in a professional
// data table with sorting, pagination, loading skeletons, and empty states.
// =============================================================================

"use client";

import { motion, AnimatePresence } from "framer-motion";
import {
  ChevronLeft,
  ChevronRight,
  ScanLine,
  ArrowUpDown,
  Calendar,
  Gauge,
  Timer,
  Hash,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ProgressBar } from "@/components/ui/ProgressBar";
import type { DetectionRecord } from "@/types";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
interface DetectionTableProps {
  records: DetectionRecord[];
  total: number;
  page: number;
  pageSize: number;
  isLoading: boolean;
  onPageChange: (page: number) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export function DetectionTable({
  records,
  total,
  page,
  pageSize,
  isLoading,
  onPageChange,
}: DetectionTableProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="space-y-4">
      {/* ── Column headers ────────────────────────────────────────────── */}
      <div className="hidden sm:grid sm:grid-cols-12 gap-4 px-4 py-2 text-[11px] font-semibold uppercase tracking-wider text-neutral-500">
        <div className="col-span-3 flex items-center gap-1">
          <Hash className="h-3 w-3" />
          Plate
        </div>
        <div className="col-span-3 flex items-center gap-1">
          <Gauge className="h-3 w-3" />
          Confidence
        </div>
        <div className="col-span-2 flex items-center gap-1">
          <Timer className="h-3 w-3" />
          Time
        </div>
        <div className="col-span-2 flex items-center gap-1">
          <ArrowUpDown className="h-3 w-3" />
          Scores
        </div>
        <div className="col-span-2 flex items-center gap-1">
          <Calendar className="h-3 w-3" />
          Date
        </div>
      </div>

      {/* ── Divider ───────────────────────────────────────────────────── */}
      <div className="border-t border-white/5" />

      {/* ── Loading skeleton ──────────────────────────────────────────── */}
      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="animate-pulse rounded-xl border border-white/5 bg-white/[0.02] px-4 py-4"
            >
              <div className="grid grid-cols-12 gap-4 items-center">
                <div className="col-span-3">
                  <div className="h-5 w-20 rounded-full bg-white/10" />
                </div>
                <div className="col-span-3">
                  <div className="h-3 w-full rounded-full bg-white/10" />
                </div>
                <div className="col-span-2">
                  <div className="h-4 w-14 rounded bg-white/10" />
                </div>
                <div className="col-span-2">
                  <div className="h-4 w-16 rounded bg-white/10" />
                </div>
                <div className="col-span-2">
                  <div className="h-4 w-20 rounded bg-white/10" />
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : records.length === 0 ? (
        /* ── Empty state ──────────────────────────────────────────────── */
        <div className="py-20 text-center">
          <ScanLine className="mx-auto mb-4 h-12 w-12 text-neutral-700" />
          <p className="text-sm font-medium text-neutral-400">
            No detections found
          </p>
          <p className="mt-1 text-xs text-neutral-600">
            Upload an image on the Dashboard to get started
          </p>
        </div>
      ) : (
        /* ── Data rows ────────────────────────────────────────────────── */
        <div className="space-y-1.5">
          <AnimatePresence mode="popLayout">
            {records.map((record, index) => (
              <motion.div
                key={record.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ delay: index * 0.03, duration: 0.25 }}
                className="group grid grid-cols-1 sm:grid-cols-12 gap-2 sm:gap-4 items-center rounded-xl border border-white/5 bg-white/[0.02] px-4 py-3.5 transition-all duration-200 hover:border-white/10 hover:bg-white/[0.05]"
              >
                {/* Plate text */}
                <div className="sm:col-span-3 flex items-center gap-2">
                  {record.plate_text ? (
                    <Badge variant="info" className="font-mono text-xs tracking-wider">
                      {record.plate_text}
                    </Badge>
                  ) : (
                    <Badge variant="danger" className="text-xs">
                      No text
                    </Badge>
                  )}
                  <span className="hidden text-[10px] text-neutral-600 sm:inline">
                    {record.id.slice(0, 8)}
                  </span>
                </div>

                {/* Combined confidence bar */}
                <div className="sm:col-span-3">
                  <div className="flex items-center gap-2">
                    <ProgressBar
                      value={Math.round(record.confidence * 100)}
                      className="h-2"
                    />
                    <span className="w-10 text-right text-xs font-medium text-neutral-300">
                      {(record.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>

                {/* Processing time */}
                <div className="sm:col-span-2">
                  <span className="text-xs text-neutral-400">
                    {(record.processing_time / 1000).toFixed(2)}s
                  </span>
                </div>

                {/* Det / OCR scores */}
                <div className="sm:col-span-2 flex gap-2">
                  <span className="text-[11px] text-neutral-500">
                    Det {(record.detection_confidence * 100).toFixed(0)}%
                  </span>
                  <span className="text-[11px] text-neutral-500">
                    OCR {(record.ocr_confidence * 100).toFixed(0)}%
                  </span>
                </div>

                {/* Date */}
                <div className="sm:col-span-2">
                  <span className="text-xs text-neutral-500">
                    {new Date(record.detected_at).toLocaleDateString(undefined, {
                      month: "short",
                      day: "numeric",
                    })}{" "}
                    <span className="text-neutral-600">
                      {new Date(record.detected_at).toLocaleTimeString(undefined, {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                  </span>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}

      {/* ── Pagination ────────────────────────────────────────────────── */}
      {total > pageSize && (
        <div className="flex items-center justify-between border-t border-white/5 pt-4">
          <p className="text-xs text-neutral-500">
            Showing {page * pageSize + 1}–
            {Math.min((page + 1) * pageSize, total)} of {total}
          </p>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onPageChange(page - 1)}
              disabled={page === 0}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>

            {/* Page numbers */}
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              const startPage = Math.max(
                0,
                Math.min(page - 2, totalPages - 5)
              );
              const p = startPage + i;
              if (p >= totalPages) return null;
              return (
                <Button
                  key={p}
                  variant={p === page ? "default" : "ghost"}
                  size="sm"
                  onClick={() => onPageChange(p)}
                  className="h-8 w-8 p-0 text-xs"
                >
                  {p + 1}
                </Button>
              );
            })}

            <Button
              variant="ghost"
              size="sm"
              onClick={() => onPageChange(page + 1)}
              disabled={page >= totalPages - 1}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
