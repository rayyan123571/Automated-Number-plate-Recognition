// =============================================================================
// app/live/page.tsx — Live ANPR Detection Page
// =============================================================================
// Full-screen live detection dashboard:
//   • Left panel: webcam/video feed with real-time bounding box overlays
//   • Right panel: detection stats, latest plate, session log
//   • FPS control slider (0.5–5 FPS)
//   • Connect/disconnect WebSocket controls
//   • Auto-invalidates React Query cache so history + analytics stay current
//
// Data flow:
//   Camera → canvas.toDataURL() → WebSocket → FastAPI → YOLO+OCR → JSON
//   → overlay + results panel + SQLite persist → React Query invalidation
// =============================================================================

"use client";

import { useState, useCallback, useRef } from "react";
import { motion } from "framer-motion";
import {
  Radio,
  Play,
  Pause,
  Settings2,
  Wifi,
  WifiOff,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { CameraCapture } from "@/components/live/CameraCapture";
import { LiveDetectionOverlay } from "@/components/live/LiveDetectionOverlay";
import { LiveResultsPanel } from "@/components/live/LiveResultsPanel";
import { useWebSocket } from "@/hooks/useWebSocket";
import { detectionKeys } from "@/hooks/useDetections";

export default function LivePage() {
  const queryClient = useQueryClient();
  const {
    state,
    lastResult,
    allResults,
    fps: detectionFps,
    connect,
    disconnect,
    sendFrame,
  } = useWebSocket();

  const [isCapturing, setIsCapturing] = useState(false);
  const [targetFps, setTargetFps] = useState(1);
  const [showSettings, setShowSettings] = useState(false);
  const framesSentRef = useRef(0);

  // ── Frame handler — send to WebSocket + invalidate queries ──────────
  const handleFrame = useCallback(
    (base64: string) => {
      sendFrame(base64);
      framesSentRef.current++;

      // Invalidate detection history every 5 frames so analytics stays fresh
      if (framesSentRef.current % 5 === 0) {
        queryClient.invalidateQueries({ queryKey: detectionKeys.all });
      }
    },
    [sendFrame, queryClient]
  );

  // ── Start live detection ────────────────────────────────────────────
  const handleStart = useCallback(() => {
    console.log("[Live] handleStart called — connecting WS and enabling capture");
    connect();
    setIsCapturing(true);
  }, [connect]);

  // ── Stop live detection ─────────────────────────────────────────────
  const handleStop = useCallback(() => {
    setIsCapturing(false);
    disconnect();
    // Final invalidation so history is up-to-date
    queryClient.invalidateQueries({ queryKey: detectionKeys.all });
  }, [disconnect, queryClient]);

  // ── Auto-start detection when camera/video source becomes ready ─────
  const handleSourceReady = useCallback(() => {
    if (!isCapturing) {
      handleStart();
    }
  }, [isCapturing, handleStart]);

  const isConnected = state === "connected";

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* ── Page Header ────────────────────────────────────────────── */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"
        >
          <div>
            <h1 className="flex items-center gap-2.5 text-2xl font-bold text-white">
              <Radio className="h-6 w-6 text-cyan-400" />
              Live Detection
            </h1>
            <p className="mt-1 text-sm text-neutral-400">
              Real-time number plate recognition via WebSocket
            </p>
          </div>

          <div className="flex items-center gap-3">
            {/* Settings toggle */}
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setShowSettings(!showSettings)}
              className="h-9 w-9"
            >
              <Settings2 className="h-4 w-4" />
            </Button>

            {/* Connection toggle */}
            {!isConnected || !isCapturing ? (
              <Button onClick={handleStart} size="sm">
                <Play className="mr-1.5 h-3.5 w-3.5" />
                Start Detection
              </Button>
            ) : (
              <Button variant="danger" onClick={handleStop} size="sm">
                <Pause className="mr-1.5 h-3.5 w-3.5" />
                Stop
              </Button>
            )}

            {/* Connection indicator */}
            <Badge
              variant={
                isConnected
                  ? "success"
                  : state === "connecting"
                  ? "warning"
                  : "danger"
              }
            >
              {isConnected ? (
                <Wifi className="mr-1 h-3 w-3" />
              ) : (
                <WifiOff className="mr-1 h-3 w-3" />
              )}
              {state}
            </Badge>
          </div>
        </motion.div>

        {/* ── Settings Panel (collapsible) ───────────────────────────── */}
        {showSettings && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
          >
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Capture Settings</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-4">
                  <label className="text-sm text-neutral-400">
                    Frame Rate:
                  </label>
                  <input
                    type="range"
                    min="0.5"
                    max="5"
                    step="0.5"
                    value={targetFps}
                    onChange={(e) => setTargetFps(parseFloat(e.target.value))}
                    className="h-2 w-48 cursor-pointer appearance-none rounded-lg bg-white/10 accent-cyan-500"
                  />
                  <span className="min-w-[3rem] text-sm font-medium text-white">
                    {targetFps} FPS
                  </span>
                  <span className="text-xs text-neutral-500">
                    (Lower = less CPU, higher = faster detection)
                  </span>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* ── Main Content: Video + Results ──────────────────────────── */}
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Left: Video Feed with Overlay */}
          <div className="lg:col-span-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-sm">
                  <Radio className="h-4 w-4 text-cyan-400" />
                  Video Feed
                  {isCapturing && (
                    <Badge variant="danger" className="ml-2">
                      <div className="mr-1 h-1.5 w-1.5 animate-pulse rounded-full bg-white" />
                      LIVE
                    </Badge>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="relative">
                  <CameraCapture
                    fps={targetFps}
                    onFrame={handleFrame}
                    isCapturing={isCapturing}
                    onSourceReady={handleSourceReady}
                  />

                  {/* Bounding box overlay */}
                  {lastResult && lastResult.plates.length > 0 && (
                    <LiveDetectionOverlay
                      plates={lastResult.plates}
                      imageWidth={lastResult.image_width}
                      imageHeight={lastResult.image_height}
                    />
                  )}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Right: Results Panel */}
          <div className="lg:col-span-1">
            <LiveResultsPanel
              state={state}
              lastResult={lastResult}
              allResults={allResults}
              fps={detectionFps}
            />
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
