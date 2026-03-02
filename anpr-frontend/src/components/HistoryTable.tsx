// =============================================================================
// components/HistoryTable.tsx — Detection History Table
// =============================================================================
// Displays a table of past detection results stored in client-side state.
// Shows timestamp, filename, detected plates, and processing time.
// =============================================================================

"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Clock, FileImage, Trash2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { formatDuration } from "@/lib/utils";
import type { HistoryEntry } from "@/types";

interface HistoryTableProps {
  history: HistoryEntry[];
  onClear: () => void;
  onSelect: (entry: HistoryEntry) => void;
}

export function HistoryTable({ history, onClear, onSelect }: HistoryTableProps) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-cyan-400" />
            Detection History
          </CardTitle>
          {history.length > 0 && (
            <Button variant="ghost" size="sm" onClick={onClear}>
              <Trash2 className="h-3.5 w-3.5" />
              Clear
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {history.length === 0 ? (
          <div className="py-8 text-center">
            <FileImage className="mx-auto mb-3 h-10 w-10 text-neutral-700" />
            <p className="text-sm text-neutral-500">No detections yet</p>
            <p className="text-xs text-neutral-600">
              Upload an image to get started
            </p>
          </div>
        ) : (
          <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1 custom-scrollbar">
            <AnimatePresence>
              {history.map((entry, index) => (
                <motion.div
                  key={entry.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 20 }}
                  transition={{ delay: index * 0.05 }}
                  onClick={() => onSelect(entry)}
                  className="group flex cursor-pointer items-center gap-4 rounded-xl border border-white/5 bg-white/[0.02] px-4 py-3 transition-all duration-200 hover:border-white/10 hover:bg-white/[0.05]"
                >
                  {/* Thumbnail */}
                  <div className="h-10 w-10 flex-shrink-0 overflow-hidden rounded-lg border border-white/10">
                    <img
                      src={entry.imageUrl}
                      alt={entry.fileName}
                      className="h-full w-full object-cover"
                    />
                  </div>

                  {/* Details */}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-neutral-200 truncate">
                      {entry.fileName}
                    </p>
                    <p className="text-[10px] text-neutral-500">
                      {entry.timestamp.toLocaleTimeString()} ·{" "}
                      {formatDuration(entry.timing.total_ms)}
                    </p>
                  </div>

                  {/* Plate badges */}
                  <div className="flex flex-wrap gap-1">
                    {entry.plates
                      .filter((p) => p.plate_text)
                      .slice(0, 3)
                      .map((plate, i) => (
                        <Badge key={i} variant="info">
                          {plate.plate_text}
                        </Badge>
                      ))}
                    {entry.plates.filter((p) => p.plate_text).length === 0 && (
                      <Badge variant="danger">No text</Badge>
                    )}
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
