// =============================================================================
// components/live/LiveDetectionOverlay.tsx — Real-time Bounding Box Overlay
// =============================================================================
// Draws bounding boxes and plate text labels over the live video feed.
// Positioned absolutely on top of the <video> element using percentage-based
// coordinates so it scales with any video resolution.
// =============================================================================

"use client";

import { AnimatePresence, motion } from "framer-motion";
import type { WSPlateResult } from "@/types";

interface LiveDetectionOverlayProps {
  plates: WSPlateResult[];
  imageWidth: number;
  imageHeight: number;
}

export function LiveDetectionOverlay({
  plates,
  imageWidth,
  imageHeight,
}: LiveDetectionOverlayProps) {
  if (!plates.length || !imageWidth || !imageHeight) return null;

  return (
    <div className="pointer-events-none absolute inset-0">
      <AnimatePresence>
        {plates.map((plate, i) => {
          const { bbox } = plate;
          if (!bbox) return null;

          // Convert pixel coords to percentages
          const left = (bbox.x_min / imageWidth) * 100;
          const top = (bbox.y_min / imageHeight) * 100;
          const width = ((bbox.x_max - bbox.x_min) / imageWidth) * 100;
          const height = ((bbox.y_max - bbox.y_min) / imageHeight) * 100;

          const confidence = (plate.confidence * 100).toFixed(0);
          const isHighConf = plate.confidence >= 0.7;

          return (
            <motion.div
              key={`${plate.plate_text}-${i}`}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              transition={{ duration: 0.2 }}
              className="absolute"
              style={{
                left: `${left}%`,
                top: `${top}%`,
                width: `${width}%`,
                height: `${height}%`,
              }}
            >
              {/* Bounding box border */}
              <div
                className={`absolute inset-0 rounded-sm border-2 ${
                  isHighConf
                    ? "border-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.4)]"
                    : "border-amber-400 shadow-[0_0_12px_rgba(251,191,36,0.4)]"
                }`}
              />

              {/* Corner accents */}
              <div
                className={`absolute -left-0.5 -top-0.5 h-3 w-3 border-l-2 border-t-2 rounded-tl-sm ${
                  isHighConf ? "border-emerald-300" : "border-amber-300"
                }`}
              />
              <div
                className={`absolute -right-0.5 -top-0.5 h-3 w-3 border-r-2 border-t-2 rounded-tr-sm ${
                  isHighConf ? "border-emerald-300" : "border-amber-300"
                }`}
              />
              <div
                className={`absolute -bottom-0.5 -left-0.5 h-3 w-3 border-b-2 border-l-2 rounded-bl-sm ${
                  isHighConf ? "border-emerald-300" : "border-amber-300"
                }`}
              />
              <div
                className={`absolute -bottom-0.5 -right-0.5 h-3 w-3 border-b-2 border-r-2 rounded-br-sm ${
                  isHighConf ? "border-emerald-300" : "border-amber-300"
                }`}
              />

              {/* Label */}
              <div
                className={`absolute -top-7 left-0 flex items-center gap-1.5 rounded-md px-2 py-0.5 text-[10px] font-bold tracking-wide shadow-lg ${
                  isHighConf
                    ? "bg-emerald-500/90 text-white"
                    : "bg-amber-500/90 text-black"
                }`}
              >
                {plate.plate_text || "—"}
                <span className="opacity-75">{confidence}%</span>
              </div>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
