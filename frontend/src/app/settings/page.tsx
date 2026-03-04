// =============================================================================
// app/settings/page.tsx — Settings Page
// =============================================================================

import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Settings, Server, Eye, Bell } from "lucide-react";

export default function SettingsPage() {
  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-white">
            <Settings className="h-6 w-6 text-cyan-400" />
            Settings
          </h1>
          <p className="mt-1 text-sm text-neutral-400">
            Configure your ANPR system preferences.
          </p>
        </div>

        <div className="grid gap-6 md:grid-cols-2">
          {/* Backend Config */}
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6 space-y-4">
            <div className="flex items-center gap-2">
              <Server className="h-5 w-5 text-cyan-400" />
              <h2 className="text-base font-semibold text-white">
                Backend Connection
              </h2>
            </div>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-neutral-400">
                  API Endpoint
                </label>
                <input
                  type="text"
                  defaultValue="http://localhost:8000"
                  readOnly
                  className="mt-1 w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-neutral-300 outline-none focus:border-cyan-500/50"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-neutral-400">
                  Health Check Interval
                </label>
                <input
                  type="text"
                  defaultValue="30 seconds"
                  readOnly
                  className="mt-1 w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-neutral-300 outline-none focus:border-cyan-500/50"
                />
              </div>
            </div>
          </div>

          {/* Detection Config */}
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6 space-y-4">
            <div className="flex items-center gap-2">
              <Eye className="h-5 w-5 text-cyan-400" />
              <h2 className="text-base font-semibold text-white">
                Detection Settings
              </h2>
            </div>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-neutral-400">
                  Model
                </label>
                <input
                  type="text"
                  defaultValue="YOLOv8 — best.pt"
                  readOnly
                  className="mt-1 w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-neutral-300 outline-none focus:border-cyan-500/50"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-neutral-400">
                  OCR Engine
                </label>
                <input
                  type="text"
                  defaultValue="EasyOCR (English)"
                  readOnly
                  className="mt-1 w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-neutral-300 outline-none focus:border-cyan-500/50"
                />
              </div>
            </div>
          </div>

          {/* Notifications */}
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6 space-y-4 md:col-span-2">
            <div className="flex items-center gap-2">
              <Bell className="h-5 w-5 text-cyan-400" />
              <h2 className="text-base font-semibold text-white">About</h2>
            </div>
            <div className="text-sm text-neutral-400 space-y-1">
              <p>
                <span className="text-neutral-300">Version:</span> 1.0.0
              </p>
              <p>
                <span className="text-neutral-300">Frontend:</span> Next.js +
                React + Tailwind CSS
              </p>
              <p>
                <span className="text-neutral-300">Backend:</span> FastAPI +
                YOLOv8 + EasyOCR
              </p>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
