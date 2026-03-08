// =============================================================================
// types/index.ts — TypeScript Type Definitions
// =============================================================================
// Mirrors the Pydantic schemas from the FastAPI backend exactly.
// Having strong types ensures compile-time safety and IDE autocompletion
// when working with API responses.
// =============================================================================

/** Pixel-coordinate bounding box for a single detection. */
export interface BoundingBox {
  x_min: number;
  y_min: number;
  x_max: number;
  y_max: number;
}

/** A single recognized license plate with text + detection metadata. */
export interface PlateResult {
  plate_text: string;
  ocr_raw_text: string;
  detection_confidence: number;
  ocr_confidence: number;
  combined_confidence: number;
  bbox: BoundingBox;
  class_id: number;
  class_name: string;
  access_status?: string | null;
  alert?: string | null;
}

/** Per-stage processing time breakdown. */
export interface TimingInfo {
  detection_ms: number;
  ocr_ms: number;
  total_ms: number;
}

/** Full ANPR pipeline response from POST /detect. */
export interface ANPRResponse {
  success: boolean;
  message: string;
  num_plates: number;
  plates: PlateResult[];
  timing: TimingInfo;
  image_width: number;
  image_height: number;
}

/** Health check response from GET /health. */
export interface HealthResponse {
  status: string;
  app_name: string;
  version: string;
  model_loaded: boolean;
  ocr_loaded: boolean;
}

/** Detection history entry (stored client-side). */
export interface HistoryEntry {
  id: string;
  timestamp: Date;
  fileName: string;
  plates: PlateResult[];
  timing: TimingInfo;
  imageUrl: string;
}

// ─── Database-backed detection record (from GET /detections) ────────────────

/** Single detection record from the SQLite database. */
export interface DetectionRecord {
  id: string;
  plate_text: string;
  confidence: number;
  detection_confidence: number;
  ocr_confidence: number;
  image_path: string | null;
  bbox: {
    x_min: number;
    y_min: number;
    x_max: number;
    y_max: number;
  };
  image_width: number;
  image_height: number;
  camera_location: string | null;
  processing_time: number;
  detected_at: string; // ISO 8601 timestamp
}

/** Paginated response from GET /detections. */
export interface DetectionListResponse {
  total: number;
  limit: number;
  offset: number;
  results: DetectionRecord[];
}

// ─── WebSocket real-time detection ──────────────────────────────────────────

/** A single plate from a WebSocket detection frame. */
export interface WSPlateResult {
  plate_text: string;
  confidence: number;
  detection_confidence: number;
  ocr_confidence: number;
  bbox: BoundingBox;
}

/** Full WebSocket detection response for a single frame. */
export interface WSDetectionResult {
  success: boolean;
  error?: string;
  num_plates: number;
  plates: WSPlateResult[];
  timing: TimingInfo;
  frame_time_ms: number;
  image_width: number;
  image_height: number;
  timestamp: string;
}

/** WebSocket connection state. */
export type WSConnectionState = "connecting" | "connected" | "disconnected" | "error";

// ─── Access Control / Security Dashboard types ──────────────────────────────

/** Authorized vehicle record. */
export interface AuthorizedVehicle {
  id: number;
  plate_number: string;
  owner_name: string;
  vehicle_type: string | null;
  department: string | null;
  created_at: string;
}

/** Payload for adding a new authorized vehicle. */
export interface VehicleCreatePayload {
  plate_number: string;
  owner_name: string;
  vehicle_type?: string;
  department?: string;
}

/** Unauthorized log entry. */
export interface UnauthorizedLogEntry {
  id: number;
  plate_number: string;
  detected_at: string;
  location: string | null;
}

/** Camera record. */
export interface CameraRecord {
  id: number;
  camera_name: string;
  location: string;
  ip_address: string | null;
  created_at: string;
}

/** Dashboard summary stats. */
export interface DashboardStats {
  total_detections: number;
  authorized_vehicles: number;
  unauthorized_alerts: number;
  active_cameras: number;
}

/** Vehicle access check result. */
export interface VehicleCheckResult {
  plate: string;
  status: "AUTHORIZED" | "UNAUTHORIZED";
}
