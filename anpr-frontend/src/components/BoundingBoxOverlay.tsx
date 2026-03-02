// =============================================================================
// components/BoundingBoxOverlay.tsx — Bounding Box Overlay on Image
// =============================================================================
// Draws bounding boxes on top of the preview image using absolute positioning.
// Boxes scale responsively as the image container resizes.
//
// HOW IT WORKS:
//   The image is displayed in a container. Each bounding box is an absolutely
//   positioned <div> whose top/left/width/height are calculated as percentages
//   of the original image dimensions. This ensures boxes remain aligned
//   regardless of the display size.
// =============================================================================

"use client";

import { useRef, useState, useEffect } from "react";
import { motion } from "framer-motion";
import type { PlateResult } from "@/types";
import { formatConfidence } from "@/lib/utils";

interface BoundingBoxOverlayProps {
  imageUrl: string;
  plates: PlateResult[];
  imageWidth: number;
  imageHeight: number;
}

export function BoundingBoxOverlay({
  imageUrl,
  plates,
  imageWidth,
  imageHeight,
}: BoundingBoxOverlayProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [displaySize, setDisplaySize] = useState({ width: 0, height: 0 });

  // Track the rendered image size for accurate box scaling
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setDisplaySize({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });

    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={containerRef}
      className="relative overflow-hidden rounded-2xl border border-white/10 bg-black/50"
    >
      {/* Base image */}
      <img
        src={imageUrl}
        alt="Detection result"
        className="block h-auto w-full max-h-[500px] object-contain"
      />

      {/* Bounding box overlays */}
      {plates.map((plate, index) => {
        const { bbox } = plate;

        // Calculate percentage positions relative to original image
        const leftPct = (bbox.x_min / imageWidth) * 100;
        const topPct = (bbox.y_min / imageHeight) * 100;
        const widthPct = ((bbox.x_max - bbox.x_min) / imageWidth) * 100;
        const heightPct = ((bbox.y_max - bbox.y_min) / imageHeight) * 100;

        return (
          <motion.div
            key={index}
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: index * 0.15, duration: 0.4 }}
            className="absolute"
            style={{
              left: `${leftPct}%`,
              top: `${topPct}%`,
              width: `${widthPct}%`,
              height: `${heightPct}%`,
            }}
          >
            {/* Box border */}
            <div className="absolute inset-0 rounded-sm border-2 border-cyan-400 bg-cyan-400/10 shadow-[0_0_15px_rgba(34,211,238,0.3)]" />

            {/* Label above box */}
            <motion.div
              initial={{ opacity: 0, y: 5 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.15 + 0.2 }}
              className="absolute -top-7 left-0 flex items-center gap-1.5 whitespace-nowrap"
            >
              <span className="rounded-md bg-cyan-500 px-2 py-0.5 text-[10px] font-bold text-white shadow-lg shadow-cyan-500/30">
                {plate.plate_text || "No text"}
              </span>
              <span className="rounded-md bg-black/70 px-1.5 py-0.5 text-[10px] text-cyan-300 backdrop-blur-sm">
                {formatConfidence(plate.detection_confidence)}
              </span>
            </motion.div>
          </motion.div>
        );
      })}
    </div>
  );
}
