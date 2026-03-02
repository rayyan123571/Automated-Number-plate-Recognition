// =============================================================================
// components/dashboard/DBStatsCards.tsx — Database-backed analytics stats
// =============================================================================
// Computes key metrics from DetectionRecord[] fetched via React Query:
//   • Total Detections  — count of all records
//   • Avg Confidence    — mean of combined confidence
//   • Avg Processing    — mean processing time in seconds
//   • High Confidence   — % of records with confidence ≥ 0.8
//
// Premium glassmorphism cards with animated counters.
// =============================================================================

"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import { Hash, Target, Timer, Sparkles } from "lucide-react";
import { Card, CardContent } from "@/components/ui/Card";
import type { DetectionRecord } from "@/types";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
interface DBStatsCardsProps {
  records: DetectionRecord[];
  isLoading?: boolean;
}

// ---------------------------------------------------------------------------
// Single stat card
// ---------------------------------------------------------------------------
function StatCard({
  icon: Icon,
  label,
  value,
  suffix,
  colorClass,
  bgClass,
  delay,
  isLoading,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  suffix?: string;
  colorClass: string;
  bgClass: string;
  delay: number;
  isLoading?: boolean;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay, duration: 0.4, ease: "easeOut" }}
    >
      <Card className="group relative overflow-hidden transition-transform hover:scale-[1.02]">
        <CardContent className="flex items-center gap-4 p-5">
          {/* Icon */}
          <div
            className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${bgClass}`}
          >
            <Icon className={`h-5 w-5 ${colorClass}`} />
          </div>

          {/* Text */}
          <div className="min-w-0">
            <p className="text-[11px] font-medium uppercase tracking-wider text-neutral-500">
              {label}
            </p>
            {isLoading ? (
              <div className="mt-1 h-7 w-20 animate-pulse rounded-md bg-white/5" />
            ) : (
              <p className="mt-0.5 text-2xl font-bold tracking-tight text-white">
                {value}
                {suffix && (
                  <span className="ml-0.5 text-sm font-medium text-neutral-400">
                    {suffix}
                  </span>
                )}
              </p>
            )}
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export function DBStatsCards({ records, isLoading }: DBStatsCardsProps) {
  const stats = useMemo(() => {
    const total = records.length;
    if (total === 0) {
      return {
        total: 0,
        avgConfidence: 0,
        avgProcessing: 0,
        highConfidenceRate: 0,
      };
    }

    const avgConfidence =
      records.reduce((sum, r) => sum + r.confidence, 0) / total;

    const withTime = records.filter((r) => r.processing_time != null);
    const avgProcessing =
      withTime.length > 0
        ? withTime.reduce((sum, r) => sum + (r.processing_time ?? 0), 0) /
          withTime.length
        : 0;

    const highConfidence = records.filter((r) => r.confidence >= 0.8).length;
    const highConfidenceRate = (highConfidence / total) * 100;

    return { total, avgConfidence, avgProcessing, highConfidenceRate };
  }, [records]);

  const cards = [
    {
      icon: Hash,
      label: "Total Detections",
      value: stats.total.toString(),
      colorClass: "text-cyan-400",
      bgClass: "bg-cyan-500/10",
    },
    {
      icon: Target,
      label: "Avg Confidence",
      value: (stats.avgConfidence * 100).toFixed(1),
      suffix: "%",
      colorClass: "text-violet-400",
      bgClass: "bg-violet-500/10",
    },
    {
      icon: Timer,
      label: "Avg Processing",
      value: stats.avgProcessing.toFixed(2),
      suffix: "s",
      colorClass: "text-amber-400",
      bgClass: "bg-amber-500/10",
    },
    {
      icon: Sparkles,
      label: "High Confidence",
      value: stats.highConfidenceRate.toFixed(0),
      suffix: "%",
      colorClass: "text-emerald-400",
      bgClass: "bg-emerald-500/10",
    },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((card, i) => (
        <StatCard
          key={card.label}
          {...card}
          delay={i * 0.08}
          isLoading={isLoading}
        />
      ))}
    </div>
  );
}
