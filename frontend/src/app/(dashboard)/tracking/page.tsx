// =============================================================================
// app/tracking/page.tsx — Live Vehicle Tracking + Auto-Challan Dashboard
// =============================================================================
// Polls /tracking/active every 2 s and renders the in-memory vehicle tracker
// state. Shows active tracks, frame counts, unauthorized counts, challan flags.
// =============================================================================

"use client";

import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import {
  Car,
  RefreshCw,
  Trash2,
  AlertTriangle,
  ShieldCheck,
  Receipt,
  Clock,
  MapPin,
  Eye,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { getActiveTracks, resetTracker } from "@/services/anprService";
import type { VehicleTrack } from "@/types";

const POLL_INTERVAL_MS = 2000;

export default function TrackingPage() {
  const [tracks, setTracks] = useState<VehicleTrack[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchTracks = useCallback(async () => {
    try {
      const res = await getActiveTracks();
      setTracks(res.tracks);
      setError(null);
    } catch (e: any) {
      setError(e?.message ?? "Failed to fetch tracks");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTracks();
    if (!autoRefresh) return;
    const id = setInterval(fetchTracks, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [autoRefresh, fetchTracks]);

  const handleReset = useCallback(async () => {
    if (!confirm("Reset the tracker? All active tracks + challan state will be cleared.")) return;
    await resetTracker();
    fetchTracks();
  }, [fetchTracks]);

  const totalChallans = tracks.filter((t) => t.challan_issued).length;
  const totalUnauth = tracks.reduce((s, t) => s + t.unauthorized_count, 0);

  return (
    <div className="space-y-8">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"
      >
        <div>
          <h1 className="flex items-center gap-2.5 text-2xl font-bold text-white">
            <Car className="h-6 w-6 text-cyan-400" />
            Vehicle Tracking &amp; Auto-Challan
          </h1>
          <p className="mt-1 text-sm text-neutral-400">
            Live state of the in-memory vehicle tracker. Tracks expire after 60s of inactivity.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setAutoRefresh((v) => !v)}
          >
            <RefreshCw
              className={`mr-1.5 h-3.5 w-3.5 ${autoRefresh ? "animate-spin text-cyan-400" : ""}`}
            />
            {autoRefresh ? "Live" : "Paused"}
          </Button>
          <Button variant="ghost" size="sm" onClick={fetchTracks}>
            Refresh
          </Button>
          <Button variant="danger" size="sm" onClick={handleReset}>
            <Trash2 className="mr-1.5 h-3.5 w-3.5" />
            Reset
          </Button>
        </div>
      </motion.div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          label="Active Tracks"
          value={tracks.length}
          icon={<Car className="h-5 w-5" />}
          tone="cyan"
        />
        <StatCard
          label="Unauthorized Hits"
          value={totalUnauth}
          icon={<AlertTriangle className="h-5 w-5" />}
          tone="orange"
        />
        <StatCard
          label="Auto-Challans Issued"
          value={totalChallans}
          icon={<Receipt className="h-5 w-5" />}
          tone="red"
        />
      </div>

      {/* Track list */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Eye className="h-4 w-4 text-cyan-400" />
            Active Tracks
          </CardTitle>
        </CardHeader>
        <CardContent>
          {error && (
            <p className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
              {error}
            </p>
          )}

          {loading ? (
            <div className="flex justify-center py-8">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-cyan-500 border-t-transparent" />
            </div>
          ) : tracks.length === 0 ? (
            <div className="py-10 text-center text-sm text-neutral-500">
              No active tracks. Upload an image or start a live stream to populate.
            </div>
          ) : (
            <div className="space-y-3">
              {tracks.map((t) => (
                <TrackRow key={t.track_id} track={t} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function StatCard({
  label,
  value,
  icon,
  tone,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
  tone: "cyan" | "orange" | "red";
}) {
  const tones = {
    cyan: "border-cyan-500/30 bg-cyan-500/5 text-cyan-400",
    orange: "border-orange-500/30 bg-orange-500/5 text-orange-400",
    red: "border-red-500/30 bg-red-500/5 text-red-400",
  } as const;
  return (
    <div
      className={`flex items-center justify-between rounded-2xl border p-5 ${tones[tone]}`}
    >
      <div>
        <p className="text-xs uppercase tracking-widest text-neutral-500">
          {label}
        </p>
        <p className="mt-2 text-3xl font-bold text-white">{value}</p>
      </div>
      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-white/5">
        {icon}
      </div>
    </div>
  );
}

function TrackRow({ track }: { track: VehicleTrack }) {
  const ageSec = Math.max(0, Math.round(Date.now() / 1000 - track.last_seen));
  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      className="flex flex-wrap items-center gap-3 rounded-xl border border-white/10 bg-white/[0.02] px-4 py-3 hover:bg-white/[0.04]"
    >
      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-cyan-500/15 text-cyan-400">
        <Car className="h-4 w-4" />
      </div>
      <div className="flex-1 min-w-[200px]">
        <p className="font-mono text-base font-bold tracking-wider text-white">
          {track.stable_plate || "—"}
        </p>
        <p className="text-[10px] text-neutral-500">
          ID: {track.track_id} · {track.frame_count} frames
        </p>
      </div>

      <div className="flex items-center gap-1.5 text-xs text-neutral-400">
        <MapPin className="h-3.5 w-3.5" /> {track.location}
      </div>

      <div className="flex items-center gap-1.5 text-xs text-neutral-400">
        <Clock className="h-3.5 w-3.5" /> {ageSec}s ago
      </div>

      {track.unauthorized_count > 0 ? (
        <Badge variant="danger">
          {track.unauthorized_count}× UNAUTH
        </Badge>
      ) : (
        <Badge variant="success">
          <ShieldCheck className="mr-1 inline h-3 w-3" />
          Clear
        </Badge>
      )}

      {track.challan_issued && (
        <Badge variant="danger">
          <Receipt className="mr-1 inline h-3 w-3" />
          CHALLAN
        </Badge>
      )}
    </motion.div>
  );
}
