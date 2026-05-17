// =============================================================================
// components/Dashboard.tsx — Main Dashboard Orchestrator
// =============================================================================
// Client component that manages global state and coordinates all other
// components: upload, detection, results, history, stats.
//
// STATE MANAGEMENT:
//   All state lives here (lifted state pattern). Children receive data
//   via props and communicate back via callbacks. No external state
//   library needed for this scale.
//
// FLOW:
//   1. User uploads image → ImageUpload calls onImageSelect
//   2. Dashboard sends image to API → detectPlates()
//   3. API returns ANPRResponse → stored in `result` + `history`
//   4. BoundingBoxOverlay renders boxes on the preview
//   5. DetectionResult shows plate texts + confidence
//   6. HistoryTable records all past detections
//   7. StatsCards aggregate analytics from history
// =============================================================================

"use client";

import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Upload, ScanLine, Loader2, Sparkles, MapPin, Receipt, ShieldAlert } from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { ImageUpload } from "@/components/ImageUpload";
import { BoundingBoxOverlay } from "@/components/BoundingBoxOverlay";
import { DetectionResult } from "@/components/DetectionResult";
import { StatsCards } from "@/components/StatsCards";
import { HistoryTable } from "@/components/HistoryTable";
import { detectPlates } from "@/services/anprService";
import type { ANPRResponse, HistoryEntry } from "@/types";

function FeaturePill({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-1 text-[11px] font-medium text-cyan-300">
      {icon}
      {label}
    </span>
  );
}

export function Dashboard() {
  // ── State ──────────────────────────────────────────────────────────────
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [result, setResult] = useState<ANPRResponse | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [currentFile, setCurrentFile] = useState<File | null>(null);

  // ── Image selection handler ────────────────────────────────────────────
  const handleImageSelect = useCallback(
    async (file: File, preview: string) => {
      setPreviewUrl(preview);
      setCurrentFile(file);
      setResult(null);
      setError(null);
      setIsProcessing(true);

      try {
        const response = await detectPlates(file);
        setResult(response);

        // Add to history
        const entry: HistoryEntry = {
          id: crypto.randomUUID(),
          timestamp: new Date(),
          fileName: file.name,
          plates: response.plates,
          timing: response.timing,
          imageUrl: preview,
        };
        setHistory((prev) => [entry, ...prev]);

        // Toast notification
        if (response.num_plates > 0) {
          toast.success(`Detected ${response.num_plates} plate(s) successfully!`);
        } else {
          toast.info("Image analyzed, but no plates were detected.");
        }

      } catch (err) {
        const msg = err instanceof Error ? err.message : "An unexpected error occurred";
        setError(msg);
        toast.error(`Detection Failed: ${msg}`);
      } finally {
        setIsProcessing(false);
      }
    },
    []
  );

  // ── Clear current detection ────────────────────────────────────────────
  const handleClear = useCallback(() => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    setResult(null);
    setError(null);
    setCurrentFile(null);
  }, [previewUrl]);

  // ── Re-view history entry ──────────────────────────────────────────────
  const handleHistorySelect = useCallback((entry: HistoryEntry) => {
    setPreviewUrl(entry.imageUrl);
    setResult({
      success: true,
      message: "",
      num_plates: entry.plates.length,
      plates: entry.plates,
      timing: entry.timing,
      image_width: 0,
      image_height: 0,
    });
    setError(null);
  }, []);

  // ── Render ─────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6">
      {/* ── Hero header ──────────────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-cyan-500/10 via-blue-600/5 to-transparent p-6 sm:p-8"
      >
        <div className="absolute -right-10 -top-10 h-40 w-40 rounded-full bg-cyan-500/10 blur-3xl" />
        <div className="absolute -bottom-12 -left-10 h-40 w-40 rounded-full bg-blue-600/10 blur-3xl" />
        <div className="relative">
          <div className="flex items-center gap-2 text-xs uppercase tracking-widest text-cyan-400">
            <Sparkles className="h-3.5 w-3.5" />
            Pakistan-Optimised ANPR
          </div>
          <h1 className="mt-2 text-2xl font-bold text-white sm:text-3xl">
            Detect, identify &amp; flag every plate on Pakistan&apos;s roads
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-neutral-400">
            Upload a vehicle image and our YOLOv8 + EasyOCR pipeline returns the plate
            text, the issuing province &amp; city, a tamper-check score, and an
            auto-challan if the vehicle violates a tracked rule.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <FeaturePill icon={<MapPin className="h-3 w-3" />} label="Province + City" />
            <FeaturePill icon={<ShieldAlert className="h-3 w-3" />} label="Fake / Tampered Detection" />
            <FeaturePill icon={<Receipt className="h-3 w-3" />} label="Auto-Challan" />
          </div>
        </div>
      </motion.div>

      {/* ── Stats Row ───────────────────────────────────────────────────── */}
      <StatsCards history={history} />

      {/* ── Main Content Grid ───────────────────────────────────────────── */}
      <div className="grid gap-6 lg:grid-cols-5">
        {/* Left column: Upload + Preview (3/5 width) */}
        <div className="space-y-6 lg:col-span-3">
          {/* Upload card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Upload className="h-4 w-4 text-cyan-400" />
                Upload Image
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ImageUpload
                onImageSelect={handleImageSelect}
                isProcessing={isProcessing}
                currentPreview={null}
                onClear={handleClear}
              />
            </CardContent>
          </Card>

          {/* Preview + Bounding Boxes */}
          <AnimatePresence>
            {previewUrl && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
              >
                <Card>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle className="flex items-center gap-2">
                        <ScanLine className="h-4 w-4 text-cyan-400" />
                        Detection Preview
                      </CardTitle>
                      {isProcessing && (
                        <div className="flex items-center gap-2 text-sm text-cyan-400">
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Analyzing...
                        </div>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent>
                    {isProcessing ? (
                      <div className="relative overflow-hidden rounded-2xl border border-white/10">
                        <img
                          src={previewUrl}
                          alt="Processing"
                          className="w-full max-h-[500px] object-contain opacity-50"
                        />
                        {/* Scanning Laser Animation */}
                        <motion.div
                          className="absolute left-0 right-0 h-0.5 bg-cyan-400 shadow-[0_0_15px_3px_rgba(34,211,238,0.7)] z-10"
                          initial={{ top: "0%" }}
                          animate={{ top: ["0%", "100%", "0%"] }}
                          transition={{ duration: 2.5, repeat: Infinity, ease: "linear" }}
                        />
                        <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/40 backdrop-blur-sm">
                          <Spinner size="lg" />
                          <p className="mt-4 text-sm font-medium text-white">
                            Fetching number plate...
                          </p>
                          <p className="mt-1 text-xs text-neutral-400">
                            Detection → Crop → OCR → Result
                          </p>
                        </div>
                      </div>
                    ) : result ? (
                      <BoundingBoxOverlay
                        imageUrl={previewUrl}
                        plates={result.plates}
                        imageWidth={result.image_width}
                        imageHeight={result.image_height}
                      />
                    ) : (
                      <img
                        src={previewUrl}
                        alt="Preview"
                        className="w-full max-h-[500px] rounded-2xl border border-white/10 object-contain"
                      />
                    )}
                  </CardContent>
                </Card>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Error display */}
          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="rounded-2xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-400"
              >
                <p className="font-medium">Detection Failed</p>
                <p className="mt-1 text-red-400/80">{error}</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Right column: Results + History (2/5 width) */}
        <div className="space-y-6 lg:col-span-2">
          {/* Detection results */}
          <AnimatePresence>
            {result && !isProcessing && (
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
              >
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <ScanLine className="h-4 w-4 text-cyan-400" />
                      Recognition Results
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <DetectionResult result={result} />
                  </CardContent>
                </Card>
              </motion.div>
            )}
          </AnimatePresence>

          {/* History table */}
          <HistoryTable
            history={history}
            onClear={() => setHistory([])}
            onSelect={handleHistorySelect}
          />
        </div>
      </div>
    </div>
  );
}
