// =============================================================================
// services/anprService.ts — API Client for the FastAPI Backend
// =============================================================================
// Encapsulates all HTTP communication with the ANPR backend.
//
// WHY AXIOS OVER FETCH?
//   • Automatic JSON parsing
//   • Request/response interceptors for logging & auth
//   • Timeout support out of the box
//   • Better error handling (network errors vs HTTP errors)
//   • FormData handling (file uploads) with progress events
//
// ARCHITECTURE:
//   Components call this service — they never make raw HTTP calls.
//   If the backend URL changes, only this file is updated.
// =============================================================================

import axios, { AxiosError } from "axios";
import type { ANPRResponse, HealthResponse, DetectionListResponse } from "@/types";

// ---------------------------------------------------------------------------
// Axios Instance — configured once, used everywhere
// ---------------------------------------------------------------------------
const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  timeout: 60000, // 60s — OCR can be slow on CPU
  headers: {
    Accept: "application/json",
  },
});

// ---------------------------------------------------------------------------
// API Functions
// ---------------------------------------------------------------------------

/**
 * Check if the backend is healthy and models are loaded.
 */
export async function checkHealth(): Promise<HealthResponse> {
  const { data } = await api.get<HealthResponse>("/health");
  return data;
}

/**
 * Upload an image and run the full ANPR pipeline.
 *
 * @param file - Image file to analyze
 * @param onProgress - Optional upload progress callback (0–100)
 * @returns Full ANPR response with plate texts, bounding boxes, timing
 */
export async function detectPlates(
  file: File,
  onProgress?: (percent: number) => void
): Promise<ANPRResponse> {
  const formData = new FormData();
  formData.append("file", file);

  try {
    const { data } = await api.post<ANPRResponse>("/detect", formData, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const percent = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          onProgress(percent);
        }
      },
    });
    return data;
  } catch (error) {
    if (error instanceof AxiosError) {
      // Extract backend error message if available
      const detail =
        error.response?.data?.detail || error.response?.data?.error;
      throw new Error(
        detail || `API Error: ${error.response?.status || "Network error"}`
      );
    }
    throw error;
  }
}

/**
 * Fetch paginated detection history from the database.
 */
export async function getDetections(
  limit: number = 20,
  offset: number = 0
): Promise<DetectionListResponse> {
  const { data } = await api.get<DetectionListResponse>("/detections", {
    params: { limit, offset },
  });
  return data;
}

/**
 * Search detections by plate text (case-insensitive partial match).
 */
export async function searchDetections(
  plate: string,
  limit: number = 20,
  offset: number = 0
): Promise<DetectionListResponse> {
  const { data } = await api.get<DetectionListResponse>(
    "/detections/search",
    { params: { plate, limit, offset } }
  );
  return data;
}

/**
 * Delete all detection history.
 */
export async function clearDetections(): Promise<void> {
  await api.delete("/detections");
}
