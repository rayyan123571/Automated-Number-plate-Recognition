"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ShieldCheck,
  ShieldAlert,
  Car,
  Camera,
  Plus,
  Trash2,
  Search,
  AlertTriangle,
  CheckCircle,
  Clock,
  MapPin,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import { cn, formatConfidence } from "@/lib/utils";

import {
  getDashboardStats,
  getAuthorizedVehicles,
  addAuthorizedVehicle,
  deleteAuthorizedVehicle,
  getUnauthorizedLogs,
  checkVehicle,
} from "@/services/securityService";
import { getDetections } from "@/services/anprService";

import type {
  DashboardStats,
  VehicleCheckResult,
  DetectionRecord,
} from "@/types";

// ─── Stats Cards ────────────────────────────────────────────────────────────

function SecurityStatsCards({ stats }: { stats: DashboardStats | undefined }) {
  const cards = [
    {
      label: "Total Vehicles Detected",
      value: stats?.total_detections ?? 0,
      icon: Car,
      gradient: "from-blue-500/20 to-cyan-500/20",
      iconColor: "text-cyan-400",
    },
    {
      label: "Authorized Vehicles",
      value: stats?.authorized_vehicles ?? 0,
      icon: ShieldCheck,
      gradient: "from-emerald-500/20 to-green-500/20",
      iconColor: "text-emerald-400",
    },
    {
      label: "Unauthorized Alerts",
      value: stats?.unauthorized_alerts ?? 0,
      icon: ShieldAlert,
      gradient: "from-red-500/20 to-rose-500/20",
      iconColor: "text-red-400",
    },
    {
      label: "Active Cameras",
      value: stats?.active_cameras ?? 0,
      icon: Camera,
      gradient: "from-purple-500/20 to-violet-500/20",
      iconColor: "text-purple-400",
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {cards.map((c, i) => (
        <motion.div
          key={c.label}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.08 }}
        >
          <Card className={cn("bg-gradient-to-br", c.gradient)}>
            <CardContent className="flex items-center gap-4 p-5">
              <div className={cn("rounded-xl bg-white/5 p-3", c.iconColor)}>
                <c.icon className="h-6 w-6" />
              </div>
              <div>
                <p className="text-2xl font-bold text-white">{c.value}</p>
                <p className="text-xs text-neutral-400">{c.label}</p>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      ))}
    </div>
  );
}

// ─── Live Detection / Check Panel ───────────────────────────────────────────

function LiveCheckPanel() {
  const [plate, setPlate] = useState("");
  const [result, setResult] = useState<VehicleCheckResult | null>(null);

  const mutation = useMutation({
    mutationFn: (p: string) => checkVehicle(p),
    onSuccess: (data) => setResult(data),
  });

  const handleCheck = () => {
    if (!plate.trim()) return;
    mutation.mutate(plate.trim());
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-white">
          <Search className="h-5 w-5 text-cyan-400" />
          Live Plate Check
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Enter plate number (e.g. LEA1234)"
            value={plate}
            onChange={(e) => setPlate(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && handleCheck()}
            className="flex-1 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder-neutral-500 outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/30"
            maxLength={20}
          />
          <Button onClick={handleCheck} disabled={mutation.isPending || !plate.trim()}>
            {mutation.isPending ? <Spinner size="sm" /> : "Check"}
          </Button>
        </div>

        <AnimatePresence mode="wait">
          {result && (
            <motion.div
              key={result.plate + result.status}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className={cn(
                "rounded-xl border p-4",
                result.status === "AUTHORIZED"
                  ? "border-emerald-500/30 bg-emerald-500/10"
                  : "border-red-500/30 bg-red-500/10"
              )}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {result.status === "AUTHORIZED" ? (
                    <CheckCircle className="h-6 w-6 text-emerald-400" />
                  ) : (
                    <AlertTriangle className="h-6 w-6 text-red-400" />
                  )}
                  <div>
                    <p className="text-lg font-bold text-white font-mono">
                      {result.plate}
                    </p>
                    <p className="text-xs text-neutral-400">
                      {result.status === "AUTHORIZED"
                        ? "Access Granted"
                        : "Unauthorized Vehicle Detected"}
                    </p>
                  </div>
                </div>
                <Badge
                  variant={result.status === "AUTHORIZED" ? "success" : "danger"}
                >
                  {result.status}
                </Badge>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </CardContent>
    </Card>
  );
}

// ─── Unauthorized Vehicles Table ────────────────────────────────────────────

function UnauthorizedTable() {
  const { data: logs, isLoading } = useQuery({
    queryKey: ["unauthorized-logs"],
    queryFn: () => getUnauthorizedLogs(50, 0),
    refetchInterval: 10000,
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-white">
          <ShieldAlert className="h-5 w-5 text-red-400" />
          Unauthorized Vehicles
          {logs && logs.length > 0 && (
            <Badge variant="danger" className="ml-2">{logs.length}</Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex justify-center py-8"><Spinner /></div>
        ) : !logs || logs.length === 0 ? (
          <p className="py-8 text-center text-sm text-neutral-500">
            No unauthorized vehicles detected yet.
          </p>
        ) : (
          <div className="max-h-[300px] overflow-y-auto scrollbar-thin">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-neutral-900/90 backdrop-blur">
                <tr className="border-b border-white/10 text-left text-xs uppercase tracking-wider text-neutral-500">
                  <th className="px-3 py-2">Plate</th>
                  <th className="px-3 py-2">Location</th>
                  <th className="px-3 py-2">Time</th>
                  <th className="px-3 py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log, i) => (
                  <motion.tr
                    key={log.id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.03 }}
                    className="border-b border-white/5 hover:bg-white/5"
                  >
                    <td className="px-3 py-2.5 font-mono font-medium text-red-400">
                      {log.plate_number}
                    </td>
                    <td className="px-3 py-2.5 text-neutral-400">
                      <span className="flex items-center gap-1">
                        <MapPin className="h-3 w-3" />
                        {log.location || "Unknown"}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-neutral-400">
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {new Date(log.detected_at).toLocaleString()}
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      <Badge variant="danger">ALERT</Badge>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ─── Authorized Vehicles Management ─────────────────────────────────────────

function AuthorizedVehiclesPanel() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    plate_number: "",
    owner_name: "",
    vehicle_type: "",
    department: "",
  });

  const { data: vehicles, isLoading } = useQuery({
    queryKey: ["authorized-vehicles"],
    queryFn: getAuthorizedVehicles,
  });

  const addMutation = useMutation({
    mutationFn: addAuthorizedVehicle,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["authorized-vehicles"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-stats"] });
      setForm({ plate_number: "", owner_name: "", vehicle_type: "", department: "" });
      setShowForm(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteAuthorizedVehicle,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["authorized-vehicles"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-stats"] });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.plate_number.trim() || !form.owner_name.trim()) return;
    addMutation.mutate({
      plate_number: form.plate_number,
      owner_name: form.owner_name,
      vehicle_type: form.vehicle_type || undefined,
      department: form.department || undefined,
    });
  };

  const inputClass =
    "w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder-neutral-500 outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/30";

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2 text-white">
          <ShieldCheck className="h-5 w-5 text-emerald-400" />
          Authorized Vehicles
          {vehicles && (
            <Badge variant="success" className="ml-2">{vehicles.length}</Badge>
          )}
        </CardTitle>
        <Button size="sm" onClick={() => setShowForm(!showForm)}>
          <Plus className="h-4 w-4" />
          {showForm ? "Cancel" : "Add Vehicle"}
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Add Form */}
        <AnimatePresence>
          {showForm && (
            <motion.form
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden"
              onSubmit={handleSubmit}
            >
              <div className="grid grid-cols-1 gap-3 rounded-xl border border-white/10 bg-white/5 p-4 sm:grid-cols-2">
                <input
                  type="text"
                  placeholder="Plate Number *"
                  value={form.plate_number}
                  onChange={(e) =>
                    setForm({ ...form, plate_number: e.target.value.toUpperCase() })
                  }
                  className={inputClass}
                  maxLength={20}
                  required
                />
                <input
                  type="text"
                  placeholder="Owner Name *"
                  value={form.owner_name}
                  onChange={(e) => setForm({ ...form, owner_name: e.target.value })}
                  className={inputClass}
                  maxLength={100}
                  required
                />
                <input
                  type="text"
                  placeholder="Vehicle Type (Car, Bike, etc.)"
                  value={form.vehicle_type}
                  onChange={(e) => setForm({ ...form, vehicle_type: e.target.value })}
                  className={inputClass}
                  maxLength={50}
                />
                <input
                  type="text"
                  placeholder="Department"
                  value={form.department}
                  onChange={(e) => setForm({ ...form, department: e.target.value })}
                  className={inputClass}
                  maxLength={100}
                />
                <div className="sm:col-span-2">
                  <Button type="submit" disabled={addMutation.isPending} className="w-full">
                    {addMutation.isPending ? <Spinner size="sm" /> : "Add Authorized Vehicle"}
                  </Button>
                  {addMutation.isError && (
                    <p className="mt-2 text-xs text-red-400">
                      {(addMutation.error as Error).message || "Failed to add vehicle."}
                    </p>
                  )}
                </div>
              </div>
            </motion.form>
          )}
        </AnimatePresence>

        {/* Vehicle List */}
        {isLoading ? (
          <div className="flex justify-center py-8"><Spinner /></div>
        ) : !vehicles || vehicles.length === 0 ? (
          <p className="py-8 text-center text-sm text-neutral-500">
            No authorized vehicles yet. Add one above.
          </p>
        ) : (
          <div className="max-h-[300px] overflow-y-auto scrollbar-thin">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-neutral-900/90 backdrop-blur">
                <tr className="border-b border-white/10 text-left text-xs uppercase tracking-wider text-neutral-500">
                  <th className="px-3 py-2">Plate</th>
                  <th className="px-3 py-2">Owner</th>
                  <th className="px-3 py-2">Type</th>
                  <th className="px-3 py-2">Department</th>
                  <th className="px-3 py-2 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {vehicles.map((v, i) => (
                  <motion.tr
                    key={v.id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.03 }}
                    className="border-b border-white/5 hover:bg-white/5"
                  >
                    <td className="px-3 py-2.5 font-mono font-medium text-emerald-400">
                      {v.plate_number}
                    </td>
                    <td className="px-3 py-2.5 text-neutral-300">{v.owner_name}</td>
                    <td className="px-3 py-2.5 text-neutral-400">{v.vehicle_type || "—"}</td>
                    <td className="px-3 py-2.5 text-neutral-400">{v.department || "—"}</td>
                    <td className="px-3 py-2.5 text-right">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-red-400 hover:bg-red-500/10 hover:text-red-300"
                        onClick={() => deleteMutation.mutate(v.id)}
                        disabled={deleteMutation.isPending}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ─── Detection History Table ────────────────────────────────────────────────

function DetectionHistoryTable() {
  const { data, isLoading } = useQuery({
    queryKey: ["detections", { limit: 30, offset: 0 }],
    queryFn: () => getDetections(30, 0),
    refetchInterval: 10000,
  });

  const records: DetectionRecord[] = data?.results ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-white">
          <Clock className="h-5 w-5 text-cyan-400" />
          Detection History
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex justify-center py-8"><Spinner /></div>
        ) : records.length === 0 ? (
          <p className="py-8 text-center text-sm text-neutral-500">
            No detections yet.
          </p>
        ) : (
          <div className="max-h-[300px] overflow-y-auto scrollbar-thin">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-neutral-900/90 backdrop-blur">
                <tr className="border-b border-white/10 text-left text-xs uppercase tracking-wider text-neutral-500">
                  <th className="px-3 py-2">Plate</th>
                  <th className="px-3 py-2">Confidence</th>
                  <th className="px-3 py-2">Location</th>
                  <th className="px-3 py-2">Time</th>
                </tr>
              </thead>
              <tbody>
                {records.map((r, i) => (
                  <motion.tr
                    key={r.id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.02 }}
                    className="border-b border-white/5 hover:bg-white/5"
                  >
                    <td className="px-3 py-2.5 font-mono font-medium text-cyan-400">
                      {r.plate_text || "—"}
                    </td>
                    <td className="px-3 py-2.5 text-neutral-300">
                      {formatConfidence(r.confidence)}
                    </td>
                    <td className="px-3 py-2.5 text-neutral-400">
                      <span className="flex items-center gap-1">
                        <MapPin className="h-3 w-3" />
                        {r.camera_location || "Gate 1"}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-neutral-400">
                      {new Date(r.detected_at).toLocaleString()}
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ─── Main Security Dashboard ────────────────────────────────────────────────

export default function SecurityDashboard() {
  const { data: stats } = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: getDashboardStats,
    refetchInterval: 10000,
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">
          ANPR Security Dashboard
        </h1>
        <p className="text-sm text-neutral-400">
          Unauthorized Vehicle Detection &amp; Access Control System
        </p>
      </div>

      {/* Stats Cards */}
      <SecurityStatsCards stats={stats} />

      {/* Live Check + Unauthorized Alerts (side by side on lg) */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <LiveCheckPanel />
        <UnauthorizedTable />
      </div>

      {/* Authorized Vehicles Management */}
      <AuthorizedVehiclesPanel />

      {/* Detection History */}
      <DetectionHistoryTable />
    </div>
  );
}
