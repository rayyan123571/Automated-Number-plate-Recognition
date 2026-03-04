// =============================================================================
// hooks/useWebSocket.ts — WebSocket Hook for Real-time ANPR Detection
// =============================================================================
// Manages a persistent WebSocket connection to ws://host/ws/detect.
//
// Features:
//   • Auto-reconnect with exponential backoff (1s → 2s → 4s → max 10s)
//   • Keepalive pings every 15s to detect stale connections
//   • Typed message parsing (WSDetectionResult)
//   • Connection state tracking for UI indicators
//   • Clean teardown on unmount
//
// Usage:
//   const { state, lastResult, sendFrame, connect, disconnect } = useWebSocket();
//   sendFrame(base64EncodedJPEG);
// =============================================================================

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { WSDetectionResult, WSConnectionState } from "@/types";

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
const WS_URL =
  (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
    .replace(/^http/, "ws") + "/ws/detect";

const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 10000;
const PING_INTERVAL_MS = 15000;

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------
export function useWebSocket() {
  const [state, setState] = useState<WSConnectionState>("disconnected");
  const [lastResult, setLastResult] = useState<WSDetectionResult | null>(null);
  const [allResults, setAllResults] = useState<WSDetectionResult[]>([]);
  const [fps, setFps] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempt = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const frameCount = useRef(0);
  const fpsTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const intentionalClose = useRef(false);

  // ── Cleanup timers ──────────────────────────────────────────────────
  const clearTimers = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
    if (pingTimer.current) {
      clearInterval(pingTimer.current);
      pingTimer.current = null;
    }
    if (fpsTimer.current) {
      clearInterval(fpsTimer.current);
      fpsTimer.current = null;
    }
  }, []);

  // ── Connect ─────────────────────────────────────────────────────────
  const connect = useCallback(() => {
    // Don't reconnect if already connected or connecting
    if (
      wsRef.current &&
      (wsRef.current.readyState === WebSocket.OPEN ||
        wsRef.current.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    intentionalClose.current = false;
    setState("connecting");

    console.log("[WS] Connecting to:", WS_URL);
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("[WS] Connected successfully!");
      setState("connected");
      reconnectAttempt.current = 0;

      // Start keepalive pings
      pingTimer.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send("ping");
        }
      }, PING_INTERVAL_MS);

      // Start FPS counter
      frameCount.current = 0;
      fpsTimer.current = setInterval(() => {
        setFps(frameCount.current);
        frameCount.current = 0;
      }, 1000);
    };

    ws.onmessage = (event) => {
      const text = event.data as string;

      // Ignore pong responses
      if (text === "pong") return;

      try {
        const result = JSON.parse(text) as WSDetectionResult;
        setLastResult(result);
        frameCount.current++;

        // Keep last 50 results for live history
        if (result.success && result.num_plates > 0) {
          setAllResults((prev) => [result, ...prev].slice(0, 50));
        }
      } catch {
        // Non-JSON message — ignore
      }
    };

    ws.onclose = (event) => {
      console.log("[WS] Connection closed. Code:", event.code, "Reason:", event.reason, "Intentional:", intentionalClose.current);
      clearTimers();

      if (intentionalClose.current) {
        setState("disconnected");
        return;
      }

      setState("disconnected");

      // Auto-reconnect with exponential backoff
      const delay = Math.min(
        RECONNECT_BASE_MS * Math.pow(2, reconnectAttempt.current),
        RECONNECT_MAX_MS
      );
      reconnectAttempt.current++;
      reconnectTimer.current = setTimeout(connect, delay);
    };

    ws.onerror = (event) => {
      console.error("[WS] Error occurred:", event);
      setState("error");
      // onclose will fire after onerror and handle reconnect
    };
  }, [clearTimers]);

  // ── Disconnect ──────────────────────────────────────────────────────
  const disconnect = useCallback(() => {
    intentionalClose.current = true;
    clearTimers();

    if (wsRef.current) {
      if (wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send("close");
      }
      wsRef.current.close();
      wsRef.current = null;
    }

    setState("disconnected");
    setLastResult(null);
    setFps(0);
  }, [clearTimers]);

  // ── Send frame ──────────────────────────────────────────────────────
  const sendFrame = useCallback((base64Data: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(base64Data);
    } else {
      console.log("[WS] Cannot send frame. WS state:", wsRef.current?.readyState, "Expected:", WebSocket.OPEN);
    }
  }, []);

  // ── Cleanup on unmount ──────────────────────────────────────────────
  useEffect(() => {
    return () => {
      intentionalClose.current = true;
      clearTimers();
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [clearTimers]);

  return {
    state,
    lastResult,
    allResults,
    fps,
    connect,
    disconnect,
    sendFrame,
  };
}
