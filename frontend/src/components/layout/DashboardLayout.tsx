// =============================================================================
// components/layout/DashboardLayout.tsx — Main Dashboard Shell
// =============================================================================
// Composition component that wraps Sidebar + Topbar + main content area.
// Handles health polling (checks backend every 30s), sidebar toggle state,
// and passes status down to child components.
// =============================================================================

"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { checkHealth } from "@/services/anprService";
import type { HealthResponse } from "@/types";

interface DashboardLayoutProps {
  children: React.ReactNode;
}

export function DashboardLayout({ children }: DashboardLayoutProps) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [isOnline, setIsOnline] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const hasFetched = useRef(false);

  const fetchHealth = useCallback(async () => {
    try {
      const data = await checkHealth();
      setHealth(data);
      setIsOnline(true);
    } catch {
      setHealth(null);
      setIsOnline(false);
    }
  }, []);

  // Poll health every 30 seconds — initial fetch deferred to avoid
  // synchronous setState warning in React 19 strict mode.
  useEffect(() => {
    if (!hasFetched.current) {
      hasFetched.current = true;
      // Defer first fetch to next tick so it doesn't trigger cascading renders
      const id = setTimeout(fetchHealth, 0);
      const interval = setInterval(fetchHealth, 30000);
      return () => {
        clearTimeout(id);
        clearInterval(interval);
      };
    }
    const interval = setInterval(fetchHealth, 30000);
    return () => clearInterval(interval);
  }, [fetchHealth]);

  return (
    <div className="flex min-h-screen bg-neutral-950">
      {/* Sidebar — fixed on desktop, drawer on mobile */}
      <Sidebar
        health={health}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      {/* Main content — offset by sidebar width on desktop */}
      <div className="flex flex-1 flex-col lg:pl-64">
        <Topbar
          isOnline={isOnline}
          onMenuToggle={() => setSidebarOpen((prev) => !prev)}
        />
        <main className="flex-1 p-4 sm:p-6 lg:p-8">{children}</main>
      </div>
    </div>
  );
}
