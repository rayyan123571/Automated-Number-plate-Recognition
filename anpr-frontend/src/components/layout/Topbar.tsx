// =============================================================================
// components/layout/Topbar.tsx — Dashboard Top Bar
// =============================================================================
// Displays the page title, hamburger toggle for mobile sidebar, and a live
// connection indicator.
// =============================================================================

"use client";

import { Wifi, WifiOff, Menu } from "lucide-react";
import { Badge } from "@/components/ui/Badge";

interface TopbarProps {
  isOnline: boolean;
  onMenuToggle: () => void;
}

export function Topbar({ isOnline, onMenuToggle }: TopbarProps) {
  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-white/10 bg-neutral-950/60 px-4 backdrop-blur-xl sm:px-6 lg:px-8">
      {/* Left: Hamburger + Title */}
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuToggle}
          className="flex h-9 w-9 items-center justify-center rounded-lg text-neutral-400 hover:bg-white/10 hover:text-white lg:hidden"
          aria-label="Toggle sidebar"
        >
          <Menu className="h-5 w-5" />
        </button>
        <div>
          <h2 className="text-lg font-semibold text-white">
            AI Detection Dashboard
          </h2>
          <p className="hidden text-xs text-neutral-500 sm:block">
            Automatic Number Plate Recognition System
          </p>
        </div>
      </div>

      {/* Right: Status */}
      <div className="flex items-center gap-4">
        <Badge variant={isOnline ? "success" : "danger"}>
          {isOnline ? (
            <Wifi className="mr-1.5 h-3 w-3" />
          ) : (
            <WifiOff className="mr-1.5 h-3 w-3" />
          )}
          <span className="hidden sm:inline">
            {isOnline ? "Backend Connected" : "Backend Offline"}
          </span>
          <span className="sm:hidden">
            {isOnline ? "Online" : "Offline"}
          </span>
        </Badge>
      </div>
    </header>
  );
}
