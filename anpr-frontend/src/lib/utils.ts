// =============================================================================
// lib/utils.ts — Utility Functions
// =============================================================================
// Central utility module. The `cn()` function merges Tailwind classes
// intelligently — duplicate/conflicting classes are resolved (e.g.,
// "p-4 p-8" → "p-8"). Used by every UI component for conditional styling.
// =============================================================================

import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge Tailwind CSS classes with conflict resolution.
 *
 * Combines `clsx` (conditional class joining) with `tailwind-merge`
 * (removes conflicting Tailwind utilities, keeping the last one).
 *
 * @example
 *   cn("p-4 bg-red-500", isActive && "bg-blue-500")
 *   // → "p-4 bg-blue-500"  (blue overrides red)
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format a number as a percentage string.
 */
export function formatConfidence(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

/**
 * Format milliseconds as a human-readable duration.
 */
export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}
