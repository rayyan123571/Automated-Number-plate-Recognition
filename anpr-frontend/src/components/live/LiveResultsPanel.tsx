// =============================================================================
// components/live/LiveResultsPanel.tsx — Real-time Detection Results Sidebar
// =============================================================================
// Displays the latest detection results, live stats, and a scrolling
// history of all plates detected during the current session.
// =============================================================================

"use client";

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ScanLine,
  Timer,
  Gauge,
  Volume2,
  VolumeX,
  Zap,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ProgressBar } from "@/components/ui/ProgressBar";
import type { WSDetectionResult, WSConnectionState } from "@/types";

interface LiveResultsPanelProps {
  state: WSConnectionState;
  lastResult: WSDetectionResult | null;
  allResults: WSDetectionResult[];
  fps: number;
}

export function LiveResultsPanel({
  state,
  lastResult,
  allResults,
  fps,
}: LiveResultsPanelProps) {
  const [soundEnabled, setSoundEnabled] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const prevPlateRef = useRef<string>("");

  // ── Play alert sound on new plate detection ─────────────────────────
  useEffect(() => {
    if (!soundEnabled || !lastResult?.plates?.length) return;

    const newPlate = lastResult.plates[0]?.plate_text || "";
    if (newPlate && newPlate !== prevPlateRef.current) {
      prevPlateRef.current = newPlate;
      // Use Web Audio API for a short beep (no external file needed)
      try {
        const ctx = new AudioContext();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.frequency.value = 880;
        gain.gain.value = 0.1;
        osc.start();
        osc.stop(ctx.currentTime + 0.12);
      } catch {
        // Audio not supported
      }
    }
  }, [soundEnabled, lastResult]);

  const totalDetected = allResults.reduce(
    (sum, r) => sum + r.num_plates,
    0
  );

  return (
    <div className="space-y-4">
      {/* ── Connection Status ────────────────────────────────────────── */}
      <Card>
        <CardContent className="flex items-center justify-between p-4">
          <div className="flex items-center gap-3">
            <div
              className={`h-2.5 w-2.5 rounded-full ${
                state === "connected"
                  ? "bg-emerald-400 shadow-lg shadow-emerald-400/50 animate-pulse"
                  : state === "connecting"
                  ? "bg-amber-400 animate-pulse"
                  : "bg-neutral-600"
              }`}
            />
            <span className="text-sm font-medium text-white capitalize">
              {state}
            </span>
          </div>
          <button
            onClick={() => setSoundEnabled(!soundEnabled)}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-neutral-400 hover:bg-white/10 hover:text-white transition-colors"
            title={soundEnabled ? "Mute alerts" : "Enable alerts"}
          >
            {soundEnabled ? (
              <Volume2 className="h-4 w-4 text-cyan-400" />
            ) : (
              <VolumeX className="h-4 w-4" />
            )}
          </button>
        </CardContent>
      </Card>

      {/* ── Live Stats ───────────────────────────────────────────────── */}
      <div className="grid grid-cols-3 gap-3">
        <Card>
          <CardContent className="p-3 text-center">
            <Zap className="mx-auto mb-1 h-4 w-4 text-cyan-400" />
            <p className="text-lg font-bold text-white">{fps}</p>
            <p className="text-[10px] uppercase tracking-wider text-neutral-500">
              FPS
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3 text-center">
            <ScanLine className="mx-auto mb-1 h-4 w-4 text-violet-400" />
            <p className="text-lg font-bold text-white">{totalDetected}</p>
            <p className="text-[10px] uppercase tracking-wider text-neutral-500">
              Plates
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3 text-center">
            <Timer className="mx-auto mb-1 h-4 w-4 text-amber-400" />
            <p className="text-lg font-bold text-white">
              {lastResult?.frame_time_ms
                ? `${(lastResult.frame_time_ms / 1000).toFixed(1)}s`
                : "—"}
            </p>
            <p className="text-[10px] uppercase tracking-wider text-neutral-500">
              Latency
            </p>
          </CardContent>
        </Card>
      </div>

      {/* ── Current Detection ────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm">
            <Gauge className="h-4 w-4 text-cyan-400" />
            Latest Detection
          </CardTitle>
        </CardHeader>
        <CardContent>
          {lastResult?.plates?.length ? (
            <AnimatePresence mode="popLayout">
              {lastResult.plates.map((plate, i) => (
                <motion.div
                  key={`${plate.plate_text}-${i}-${lastResult.timestamp}`}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 20 }}
                  className="space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-2xl font-bold tracking-wider text-white font-mono">
                      {plate.plate_text || "—"}
                    </span>
                    <Badge
                      variant={
                        plate.confidence >= 0.7
                          ? "success"
                          : plate.confidence >= 0.4
                          ? "warning"
                          : "danger"
                      }
                    >
                      {(plate.confidence * 100).toFixed(0)}%
                    </Badge>
                  </div>
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between text-xs text-neutral-400">
                      <span>Detection</span>
                      <span>
                        {(plate.detection_confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                    <ProgressBar
                      value={plate.detection_confidence * 100}
                      className="h-1.5"
                    />
                    <div className="flex items-center justify-between text-xs text-neutral-400">
                      <span>OCR</span>
                      <span>
                        {(plate.ocr_confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                    <ProgressBar
                      value={plate.ocr_confidence * 100}
                      className="h-1.5"
                    />
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          ) : (
            <p className="py-4 text-center text-sm text-neutral-600">
              {state === "connected"
                ? "Waiting for detection…"
                : "Connect to start detecting"}
            </p>
          )}
        </CardContent>
      </Card>

      {/* ── Live History ─────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm">
            <ScanLine className="h-4 w-4 text-cyan-400" />
            Session Log
            {allResults.length > 0 && (
              <Badge variant="info">{allResults.length}</Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="max-h-[280px] space-y-1.5 overflow-y-auto pr-1 custom-scrollbar">
            {allResults.length === 0 ? (
              <p className="py-4 text-center text-xs text-neutral-600">
                Detected plates will appear here
              </p>
            ) : (
              <AnimatePresence>
                {allResults.slice(0, 20).map((result, i) => {
                  const plate = result.plates[0];
                  if (!plate) return null;
                  return (
                    <motion.div
                      key={`${result.timestamp}-${i}`}
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      className="flex items-center justify-between rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2"
                    >
                      <div className="flex items-center gap-2">
                        <Badge variant="info" className="font-mono text-[10px]">
                          {plate.plate_text || "—"}
                        </Badge>
                        <span className="text-[10px] text-neutral-600">
                          {new Date(result.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                      <span className="text-[10px] font-medium text-neutral-400">
                        {(plate.confidence * 100).toFixed(0)}%
                      </span>
                    </motion.div>
                  );
                })}
              </AnimatePresence>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
