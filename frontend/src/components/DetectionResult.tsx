// =============================================================================
// components/DetectionResult.tsx — Detection Result Panel
// =============================================================================
// Displays the recognized plates in a clean card layout with confidence
// scores, timing breakdown, and individual plate details.
// =============================================================================

"use client";

import { motion } from "framer-motion";
import {
  ScanLine,
  Clock,
  Eye,
  Zap,
  Hash,
  ChevronRight,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { formatConfidence, formatDuration } from "@/lib/utils";
import type { ANPRResponse, PlateResult } from "@/types";

interface DetectionResultProps {
  result: ANPRResponse;
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
export function DetectionResult({ result }: DetectionResultProps) {
  const recognizedPlates = result.plates.filter((p) => p.plate_text);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="space-y-4"
    >
      {/* ── Timing Overview ──────────────────────────────────────────── */}
      <div className="grid grid-cols-3 gap-3">
        <TimingStat
          icon={<Eye className="h-4 w-4" />}
          label="Detection"
          value={formatDuration(result.timing.detection_ms)}
        />
        <TimingStat
          icon={<ScanLine className="h-4 w-4" />}
          label="OCR"
          value={formatDuration(result.timing.ocr_ms)}
        />
        <TimingStat
          icon={<Zap className="h-4 w-4" />}
          label="Total"
          value={formatDuration(result.timing.total_ms)}
          highlight
        />
      </div>

      {/* ── Plate Results ────────────────────────────────────────────── */}
      {recognizedPlates.length > 0 ? (
        <div className="space-y-3">
          {result.plates.map((plate, index) => (
            <PlateCard key={index} plate={plate} index={index} />
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="py-8 text-center">
            <ScanLine className="mx-auto mb-3 h-10 w-10 text-neutral-600" />
            <p className="text-sm text-neutral-400">
              {result.num_plates > 0
                ? "Plates detected but text could not be read"
                : "No plates detected in this image"}
            </p>
          </CardContent>
        </Card>
      )}
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function TimingStat({
  icon,
  label,
  value,
  highlight,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={`flex flex-col items-center rounded-xl border p-3 ${
        highlight
          ? "border-cyan-500/30 bg-cyan-500/5"
          : "border-white/10 bg-white/[0.02]"
      }`}
    >
      <div className={highlight ? "text-cyan-400" : "text-neutral-500"}>
        {icon}
      </div>
      <p className="mt-1 text-xs text-neutral-500">{label}</p>
      <p
        className={`text-sm font-semibold ${
          highlight ? "text-cyan-400" : "text-white"
        }`}
      >
        {value}
      </p>
    </div>
  );
}

function PlateCard({ plate, index }: { plate: PlateResult; index: number }) {
  const hasText = plate.plate_text.length > 0;

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.1 }}
    >
      <Card className={!hasText ? "opacity-50" : ""}>
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            {/* Plate number */}
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-500/15 text-cyan-400">
                <Hash className="h-4 w-4" />
              </div>
              <div>
                <p className="text-lg font-bold tracking-widest text-white font-mono">
                  {hasText ? plate.plate_text : "—"}
                </p>
                {plate.ocr_raw_text && plate.ocr_raw_text !== plate.plate_text && (
                  <p className="text-[10px] text-neutral-500">
                    Raw: {plate.ocr_raw_text}
                  </p>
                )}
              </div>
            </div>

            {/* Confidence badge */}
            <Badge
              variant={
                plate.combined_confidence > 0.3
                  ? "success"
                  : plate.combined_confidence > 0.1
                    ? "warning"
                    : "danger"
              }
            >
              {formatConfidence(plate.combined_confidence)}
            </Badge>
          </div>

          {/* Confidence bars */}
          {hasText && (
            <div className="mt-4 space-y-2">
              <ConfidenceRow
                label="Detection"
                value={plate.detection_confidence}
              />
              <ConfidenceRow label="OCR" value={plate.ocr_confidence} />
              <ConfidenceRow
                label="Combined"
                value={plate.combined_confidence}
                color="bg-cyan-500"
              />
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
}

function ConfidenceRow({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color?: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-20 text-[11px] text-neutral-500">{label}</span>
      <ProgressBar value={value * 100} className="flex-1" color={color} />
      <span className="w-12 text-right text-[11px] font-medium text-neutral-300">
        {formatConfidence(value)}
      </span>
    </div>
  );
}
