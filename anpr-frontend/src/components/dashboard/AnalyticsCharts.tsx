// =============================================================================
// components/dashboard/AnalyticsCharts.tsx — Recharts Analytics Panel
// =============================================================================
// Two responsive charts powered by Recharts:
//   1. Line chart  → Confidence trend over time
//   2. Bar chart   → Detections per day
//
// Data is computed from the raw DetectionRecord[] passed as props.
// Charts use the same dark theme as the rest of the dashboard.
// =============================================================================

"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { TrendingUp, BarChart3 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import type { DetectionRecord } from "@/types";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
interface AnalyticsChartsProps {
  records: DetectionRecord[];
}

// ---------------------------------------------------------------------------
// Custom tooltip (shared)
// ---------------------------------------------------------------------------
function ChartTooltip({
  active,
  payload,
  label,
  valueLabel,
  valueSuffix,
}: {
  active?: boolean;
  payload?: Array<{ name?: string; value?: number; color?: string }>;
  label?: string;
  valueLabel?: string;
  valueSuffix?: string;
}) {
  if (!active || !payload?.length) return null;

  return (
    <div className="rounded-xl border border-white/10 bg-neutral-900/95 px-4 py-3 shadow-2xl backdrop-blur-xl">
      <p className="mb-1 text-[11px] font-medium text-neutral-400">{label}</p>
      {payload.map((entry, i) => (
        <p key={i} className="text-sm font-semibold text-white">
          {valueLabel ?? entry.name}:{" "}
          <span style={{ color: entry.color }}>
            {typeof entry.value === "number"
              ? entry.value.toFixed(entry.value < 2 ? 1 : 0)
              : entry.value}
            {valueSuffix ?? ""}
          </span>
        </p>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export function AnalyticsCharts({ records }: AnalyticsChartsProps) {
  // ── Confidence trend data ─────────────────────────────────────────────
  const confidenceData = useMemo(() => {
    if (records.length === 0) return [];

    // Take the most recent 30 records, sorted oldest → newest for chart
    return [...records]
      .sort(
        (a, b) =>
          new Date(a.detected_at).getTime() -
          new Date(b.detected_at).getTime()
      )
      .slice(-30)
      .map((r, i) => ({
        index: i + 1,
        label: new Date(r.detected_at).toLocaleTimeString(undefined, {
          hour: "2-digit",
          minute: "2-digit",
        }),
        confidence: +(r.confidence * 100).toFixed(1),
        detection: +(r.detection_confidence * 100).toFixed(1),
        ocr: +(r.ocr_confidence * 100).toFixed(1),
      }));
  }, [records]);

  // ── Detections per day data ───────────────────────────────────────────
  const dailyData = useMemo(() => {
    if (records.length === 0) return [];

    const countMap = new Map<string, number>();
    for (const r of records) {
      const day = new Date(r.detected_at).toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
      });
      countMap.set(day, (countMap.get(day) ?? 0) + 1);
    }

    // Convert map to sorted array (most recent last)
    return Array.from(countMap.entries())
      .slice(-14) // Last 14 days
      .map(([day, count]) => ({ day, count }));
  }, [records]);

  if (records.length === 0) {
    return (
      <div className="grid gap-6 lg:grid-cols-2">
        {[0, 1].map((i) => (
          <Card key={i}>
            <CardContent className="flex min-h-[280px] items-center justify-center">
              <p className="text-sm text-neutral-600">
                Charts will appear after first detection
              </p>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {/* ── Confidence Trend (Line) ──────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <TrendingUp className="h-4 w-4 text-cyan-400" />
              Confidence Trend
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[240px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={confidenceData}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="rgba(255,255,255,0.05)"
                  />
                  <XAxis
                    dataKey="label"
                    tick={{ fill: "#737373", fontSize: 10 }}
                    axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                    tickLine={false}
                  />
                  <YAxis
                    domain={[0, 100]}
                    tick={{ fill: "#737373", fontSize: 10 }}
                    axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                    tickLine={false}
                    tickFormatter={(v) => `${v}%`}
                  />
                  <Tooltip
                    content={
                      <ChartTooltip valueSuffix="%" />
                    }
                  />
                  <Line
                    type="monotone"
                    dataKey="confidence"
                    name="Combined"
                    stroke="#06b6d4"
                    strokeWidth={2}
                    dot={{ r: 3, fill: "#06b6d4" }}
                    activeDot={{ r: 5, fill: "#06b6d4" }}
                  />
                  <Line
                    type="monotone"
                    dataKey="detection"
                    name="Detection"
                    stroke="#8b5cf6"
                    strokeWidth={1.5}
                    strokeDasharray="5 5"
                    dot={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="ocr"
                    name="OCR"
                    stroke="#10b981"
                    strokeWidth={1.5}
                    strokeDasharray="5 5"
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-3 flex items-center justify-center gap-5 text-[11px] text-neutral-500">
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-4 rounded-full bg-cyan-500" />
                Combined
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-4 rounded-full bg-violet-500" />
                Detection
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-4 rounded-full bg-emerald-500" />
                OCR
              </span>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* ── Detections per Day (Bar) ─────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <BarChart3 className="h-4 w-4 text-cyan-400" />
              Detections per Day
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[240px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={dailyData}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="rgba(255,255,255,0.05)"
                  />
                  <XAxis
                    dataKey="day"
                    tick={{ fill: "#737373", fontSize: 10 }}
                    axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                    tickLine={false}
                  />
                  <YAxis
                    allowDecimals={false}
                    tick={{ fill: "#737373", fontSize: 10 }}
                    axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                    tickLine={false}
                  />
                  <Tooltip
                    content={
                      <ChartTooltip valueLabel="Detections" />
                    }
                  />
                  <Bar
                    dataKey="count"
                    name="Detections"
                    fill="url(#barGradient)"
                    radius={[6, 6, 0, 0]}
                    maxBarSize={40}
                  />
                  <defs>
                    <linearGradient
                      id="barGradient"
                      x1="0"
                      y1="0"
                      x2="0"
                      y2="1"
                    >
                      <stop offset="0%" stopColor="#06b6d4" stopOpacity={0.9} />
                      <stop
                        offset="100%"
                        stopColor="#3b82f6"
                        stopOpacity={0.6}
                      />
                    </linearGradient>
                  </defs>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
