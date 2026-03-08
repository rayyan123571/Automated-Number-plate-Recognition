import axios from "axios";
import type {
  AuthorizedVehicle,
  VehicleCreatePayload,
  UnauthorizedLogEntry,
  CameraRecord,
  DashboardStats,
  VehicleCheckResult,
} from "@/types";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  timeout: 15000,
  headers: { Accept: "application/json" },
});

// ─── Dashboard Stats ────────────────────────────────────────────────────────

export async function getDashboardStats(): Promise<DashboardStats> {
  const { data } = await api.get<DashboardStats>("/vehicles/stats/summary");
  return data;
}

// ─── Authorized Vehicles ────────────────────────────────────────────────────

export async function getAuthorizedVehicles(): Promise<AuthorizedVehicle[]> {
  const { data } = await api.get<AuthorizedVehicle[]>("/vehicles/list");
  return data;
}

export async function addAuthorizedVehicle(
  payload: VehicleCreatePayload
): Promise<AuthorizedVehicle> {
  const { data } = await api.post<AuthorizedVehicle>("/vehicles/add", payload);
  return data;
}

export async function deleteAuthorizedVehicle(id: number): Promise<void> {
  await api.delete(`/vehicles/${id}`);
}

export async function checkVehicle(
  plate: string
): Promise<VehicleCheckResult> {
  const { data } = await api.get<VehicleCheckResult>(
    `/vehicles/check/${encodeURIComponent(plate)}`
  );
  return data;
}

// ─── Unauthorized Logs ──────────────────────────────────────────────────────

export async function getUnauthorizedLogs(
  limit = 50,
  offset = 0
): Promise<UnauthorizedLogEntry[]> {
  const { data } = await api.get<UnauthorizedLogEntry[]>("/unauthorized/logs", {
    params: { limit, offset },
  });
  return data;
}

// ─── Cameras ────────────────────────────────────────────────────────────────

export async function getCameras(): Promise<CameraRecord[]> {
  const { data } = await api.get<CameraRecord[]>("/cameras/list");
  return data;
}

export async function addCamera(payload: {
  camera_name: string;
  location: string;
  ip_address?: string;
}): Promise<CameraRecord> {
  const { data } = await api.post<CameraRecord>("/cameras/add", payload);
  return data;
}

export async function deleteCamera(id: number): Promise<void> {
  await api.delete(`/cameras/${id}`);
}
