// =============================================================================
// components/StatsCards.tsx — Analytics Summary Cards
// =============================================================================
// Top-level dashboard statistics — total scans, plates found, avg time, etc.
// Displayed as a horizontal row of glassmorphism cards.
// =============================================================================

"use client";

import { motion } from "framer-motion";
import { ScanLine, Clock, Hash, TrendingUp } from "lucide-react";
import type { HistoryEntry } from "@/types";

interface StatsCardsProps {
  history: HistoryEntry[];
}

export function StatsCards({ history }: StatsCardsProps) {
  const totalScans = history.length;
  const totalPlates = history.reduce((sum, h) => sum + h.plates.length, 0);
  const recognizedPlates = history.reduce(
    (sum, h) => sum + h.plates.filter((p) => p.plate_text).length,
    0
  );
  const avgTime =
    totalScans > 0
      ? history.reduce((sum, h) => sum + h.timing.total_ms, 0) / totalScans
      : 0;

  const stats = [
    {
      label: "Total Scans",
      value: totalScans.toString(),
      icon: ScanLine,
      color: "from-cyan-500 to-blue-600",
      shadowColor: "shadow-cyan-500/20",
    },
    {
      label: "Plates Found",
      value: totalPlates.toString(),
      icon: Hash,
      color: "from-emerald-500 to-teal-600",
      shadowColor: "shadow-emerald-500/20",
    },
    {
      label: "Recognized",
      value: recognizedPlates.toString(),
      icon: TrendingUp,
      color: "from-violet-500 to-purple-600",
      shadowColor: "shadow-violet-500/20",
    },
    {
      label: "Avg. Time",
      value: avgTime > 0 ? `${(avgTime / 1000).toFixed(2)}s` : "—",
      icon: Clock,
      color: "from-amber-500 to-orange-600",
      shadowColor: "shadow-amber-500/20",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      {stats.map((stat, index) => (
        <motion.div
          key={stat.label}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: index * 0.1 }}
          className={`group relative overflow-hidden rounded-2xl border border-white/10 bg-white/5 p-5 backdrop-blur-xl transition-all duration-300 hover:border-white/20 hover:bg-white/[0.08]`}
        >
          {/* Gradient background glow */}
          <div
            className={`absolute -right-4 -top-4 h-24 w-24 rounded-full bg-gradient-to-br ${stat.color} opacity-10 blur-2xl transition-opacity duration-300 group-hover:opacity-20`}
          />

          <div className="relative">
            <div
              className={`flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br ${stat.color} shadow-lg ${stat.shadowColor}`}
            >
              <stat.icon className="h-5 w-5 text-white" />
            </div>
            <p className="mt-3 text-2xl font-bold text-white">{stat.value}</p>
            <p className="text-xs text-neutral-500">{stat.label}</p>
          </div>
        </motion.div>
      ))}
    </div>
  );
}
