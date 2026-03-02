// =============================================================================
// components/live/CameraCapture.tsx — Webcam / Video Frame Capture
// =============================================================================
// Captures frames from the user's webcam or an uploaded video file.
//
// Architecture:
//   <video> → hidden <canvas> → toDataURL("image/jpeg") → base64 string
//   Frames are sent at a configurable interval (default 1 FPS).
//
// Memory management:
//   • Canvas is reused (not recreated) every frame.
//   • Object URLs are revoked when video source changes.
//   • MediaStream tracks are stopped on unmount.
//   • requestAnimationFrame + timestamp gating instead of setInterval
//     for smooth, battery-friendly capture.
// =============================================================================

"use client";

import {
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
  forwardRef,
} from "react";
import { Camera, VideoIcon, Square, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/Button";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export interface CameraCaptureRef {
  captureFrame: () => string | null;
}

interface CameraCaptureProps {
  /** Frames per second to send (default: 1). Range 0.5 – 5. */
  fps?: number;
  /** Called with base64 JPEG whenever a frame is captured. */
  onFrame?: (base64: string) => void;
  /** Whether capture loop is running. */
  isCapturing: boolean;
  /** Width of the video element (CSS). */
  width?: number;
  /** Additional class names. */
  className?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export const CameraCapture = forwardRef<CameraCaptureRef, CameraCaptureProps>(
  function CameraCapture(
    { fps = 1, onFrame, isCapturing, width = 640, className },
    ref
  ) {
    const videoRef = useRef<HTMLVideoElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const rafRef = useRef<number>(0);
    const lastCaptureRef = useRef<number>(0);
    const videoUrlRef = useRef<string | null>(null);

    const [source, setSource] = useState<"camera" | "video" | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [videoReady, setVideoReady] = useState(false);

    const captureInterval = 1000 / Math.max(0.5, Math.min(fps, 5));

    // ── Expose captureFrame to parent via ref ─────────────────────────
    useImperativeHandle(ref, () => ({
      captureFrame: () => captureCurrentFrame(),
    }));

    // ── Capture a single frame to base64 JPEG ────────────────────────
    const captureCurrentFrame = useCallback((): string | null => {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas || video.paused || video.ended) return null;

      canvas.width = video.videoWidth || 640;
      canvas.height = video.videoHeight || 480;

      const ctx = canvas.getContext("2d");
      if (!ctx) return null;

      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      return canvas.toDataURL("image/jpeg", 0.8);
    }, []);

    // ── Frame capture loop ────────────────────────────────────────────
    useEffect(() => {
      if (!isCapturing || !videoReady || !onFrame) return;

      let running = true;

      const tick = (now: number) => {
        if (!running) return;

        if (now - lastCaptureRef.current >= captureInterval) {
          lastCaptureRef.current = now;
          const frame = captureCurrentFrame();
          if (frame) onFrame(frame);
        }

        rafRef.current = requestAnimationFrame(tick);
      };

      rafRef.current = requestAnimationFrame(tick);

      return () => {
        running = false;
        cancelAnimationFrame(rafRef.current);
      };
    }, [isCapturing, videoReady, onFrame, captureInterval, captureCurrentFrame]);

    // ── Start webcam ──────────────────────────────────────────────────
    const startCamera = useCallback(async () => {
      setError(null);
      stopStream();

      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            width: { ideal: 1280 },
            height: { ideal: 720 },
            facingMode: "environment", // Prefer rear camera on mobile
          },
          audio: false,
        });

        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.play();
        }
        setSource("camera");
        setVideoReady(true);
      } catch (err) {
        const msg =
          err instanceof DOMException && err.name === "NotAllowedError"
            ? "Camera access denied. Please allow camera permissions."
            : "Could not access camera. Check if another app is using it.";
        setError(msg);
      }
    }, []);

    // ── Load video file ───────────────────────────────────────────────
    const loadVideo = useCallback((file: File) => {
      setError(null);
      stopStream();

      if (videoUrlRef.current) {
        URL.revokeObjectURL(videoUrlRef.current);
      }

      const url = URL.createObjectURL(file);
      videoUrlRef.current = url;

      if (videoRef.current) {
        videoRef.current.srcObject = null;
        videoRef.current.src = url;
        videoRef.current.play();
      }
      setSource("video");
      setVideoReady(true);
    }, []);

    // ── Stop all streams ──────────────────────────────────────────────
    const stopStream = useCallback(() => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }
      if (videoRef.current) {
        videoRef.current.srcObject = null;
        videoRef.current.src = "";
      }
      setVideoReady(false);
      setSource(null);
    }, []);

    // ── Cleanup on unmount ────────────────────────────────────────────
    useEffect(() => {
      return () => {
        cancelAnimationFrame(rafRef.current);
        stopStream();
        if (videoUrlRef.current) {
          URL.revokeObjectURL(videoUrlRef.current);
        }
      };
    }, [stopStream]);

    // ── Handle video file input ───────────────────────────────────────
    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file && file.type.startsWith("video/")) {
        loadVideo(file);
      } else {
        setError("Please select a valid video file.");
      }
    };

    return (
      <div className={className}>
        {/* Hidden canvas for frame capture */}
        <canvas ref={canvasRef} className="hidden" />

        {/* Video element */}
        <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-black">
          <video
            ref={videoRef}
            className="block w-full"
            style={{ maxWidth: width }}
            muted
            playsInline
            loop={source === "video"}
            onLoadedData={() => setVideoReady(true)}
          />

          {/* No source placeholder */}
          {!source && (
            <div className="flex flex-col items-center justify-center gap-4 py-20 px-6">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-white/5">
                <Camera className="h-8 w-8 text-neutral-600" />
              </div>
              <p className="text-sm text-neutral-500 text-center">
                Start your webcam or load a video file to begin live detection
              </p>
            </div>
          )}

          {/* Capture indicator */}
          {isCapturing && videoReady && (
            <div className="absolute left-3 top-3 flex items-center gap-2 rounded-lg bg-red-500/90 px-2.5 py-1 backdrop-blur-sm">
              <div className="h-2 w-2 animate-pulse rounded-full bg-white" />
              <span className="text-[10px] font-bold uppercase tracking-wider text-white">
                Live
              </span>
            </div>
          )}
        </div>

        {/* Error display */}
        {error && (
          <div className="mt-3 flex items-center gap-2 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-2.5">
            <AlertCircle className="h-4 w-4 shrink-0 text-red-400" />
            <p className="text-xs text-red-300">{error}</p>
          </div>
        )}

        {/* Controls */}
        <div className="mt-4 flex flex-wrap items-center gap-3">
          {!source ? (
            <>
              <Button onClick={startCamera} size="sm">
                <Camera className="mr-1.5 h-3.5 w-3.5" />
                Start Webcam
              </Button>
              <label>
                <input
                  type="file"
                  accept="video/*"
                  onChange={handleFileChange}
                  className="hidden"
                />
                <span
                  className="inline-flex cursor-pointer items-center justify-center gap-2 rounded-xl font-medium transition-all duration-200 bg-white/10 text-white hover:bg-white/20 border border-white/10 h-8 px-3 text-xs active:scale-[0.98]"
                >
                  <VideoIcon className="mr-1.5 h-3.5 w-3.5" />
                  Load Video
                </span>
              </label>
            </>
          ) : (
            <Button variant="danger" size="sm" onClick={stopStream}>
              <Square className="mr-1.5 h-3 w-3" />
              Stop
            </Button>
          )}
        </div>
      </div>
    );
  }
);
