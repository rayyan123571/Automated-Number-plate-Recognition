// =============================================================================
// components/ImageUpload.tsx — Drag & Drop Image Upload Component
// =============================================================================
// Handles image selection via drag-and-drop or file picker.
// Validates file type and size before accepting.
// Shows a live preview of the selected image.
// Triggers the ANPR detection pipeline when an image is selected.
//
// Features:
//   • Drag & drop zone with visual feedback
//   • File type validation (JPEG, PNG, WebP, BMP)
//   • File size validation (max 10 MB)
//   • Animated transitions (Framer Motion)
//   • Upload progress indicator
//   • Error state display
// =============================================================================

"use client";

import { useCallback, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Upload, ImageIcon, X, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const ACCEPTED_TYPES = [
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/bmp",
];
const MAX_SIZE_MB = 10;
const MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024;

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
interface ImageUploadProps {
  onImageSelect: (file: File, previewUrl: string) => void;
  isProcessing: boolean;
  currentPreview: string | null;
  onClear: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export function ImageUpload({
  onImageSelect,
  isProcessing,
  currentPreview,
  onClear,
}: ImageUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── File validation ───────────────────────────────────────────────────
  const validateFile = useCallback((file: File): string | null => {
    if (!ACCEPTED_TYPES.includes(file.type)) {
      return `Invalid file type: ${file.type}. Accepted: JPEG, PNG, WebP, BMP.`;
    }
    if (file.size > MAX_SIZE_BYTES) {
      return `File too large: ${(file.size / 1024 / 1024).toFixed(1)} MB. Max: ${MAX_SIZE_MB} MB.`;
    }
    return null;
  }, []);

  // ── Handle file selection ─────────────────────────────────────────────
  const handleFile = useCallback(
    (file: File) => {
      setError(null);
      const validationError = validateFile(file);
      if (validationError) {
        setError(validationError);
        return;
      }
      const previewUrl = URL.createObjectURL(file);
      onImageSelect(file, previewUrl);
    },
    [validateFile, onImageSelect]
  );

  // ── Drag & drop handlers ──────────────────────────────────────────────
  const handleDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (!isProcessing) setIsDragging(true);
    },
    [isProcessing]
  );

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);
      if (isProcessing) return;

      const files = e.dataTransfer.files;
      if (files.length > 0) {
        handleFile(files[0]);
      }
    },
    [isProcessing, handleFile]
  );

  // ── Click to upload ───────────────────────────────────────────────────
  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        handleFile(files[0]);
      }
      // Reset input so re-selecting the same file triggers onChange
      e.target.value = "";
    },
    [handleFile]
  );

  const openFilePicker = () => {
    if (!isProcessing) fileInputRef.current?.click();
  };

  // ── Render ────────────────────────────────────────────────────────────
  return (
    <div className="space-y-4">
      <AnimatePresence mode="wait">
        {currentPreview ? (
          /* ── Preview state ──────────────────────────────────────── */
          <motion.div
            key="preview"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="relative overflow-hidden rounded-2xl border border-white/10"
          >
            <img
              src={currentPreview}
              alt="Upload preview"
              className="h-auto w-full object-contain max-h-[400px] bg-black/50"
            />
            {!isProcessing && (
              <Button
                variant="ghost"
                size="icon"
                onClick={onClear}
                className="absolute right-3 top-3 bg-black/50 hover:bg-black/80"
              >
                <X className="h-4 w-4" />
              </Button>
            )}
          </motion.div>
        ) : (
          /* ── Drop zone state ────────────────────────────────────── */
          <motion.div
            key="dropzone"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={openFilePicker}
            className={cn(
              "group relative flex min-h-[280px] cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed transition-all duration-300",
              isDragging
                ? "border-cyan-400 bg-cyan-500/10 scale-[1.02]"
                : "border-white/20 bg-white/[0.02] hover:border-white/40 hover:bg-white/[0.04]",
              isProcessing && "pointer-events-none opacity-50"
            )}
          >
            {/* Animated icon */}
            <motion.div
              animate={{
                y: isDragging ? -8 : 0,
                scale: isDragging ? 1.1 : 1,
              }}
              transition={{ type: "spring", stiffness: 300, damping: 20 }}
              className="mb-4"
            >
              <div
                className={cn(
                  "flex h-16 w-16 items-center justify-center rounded-2xl transition-colors duration-300",
                  isDragging
                    ? "bg-cyan-500/20 text-cyan-400"
                    : "bg-white/5 text-neutral-500 group-hover:text-neutral-300"
                )}
              >
                {isDragging ? (
                  <ImageIcon className="h-7 w-7" />
                ) : (
                  <Upload className="h-7 w-7" />
                )}
              </div>
            </motion.div>

            <p className="text-sm font-medium text-neutral-300">
              {isDragging ? "Drop image here" : "Drag & drop an image"}
            </p>
            <p className="mt-1 text-xs text-neutral-500">
              or click to browse · JPEG, PNG, WebP, BMP · Max {MAX_SIZE_MB}MB
            </p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Error display ──────────────────────────────────────────────── */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="flex items-center gap-2 rounded-xl bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400"
          >
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            {error}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept={ACCEPTED_TYPES.join(",")}
        onChange={handleInputChange}
        className="hidden"
      />
    </div>
  );
}
