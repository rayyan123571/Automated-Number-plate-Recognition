// =============================================================================
// components/layout/Sidebar.tsx — Dashboard Navigation Sidebar
// =============================================================================
// Responsive sidebar: fixed on desktop (lg+), slide-over drawer on mobile.
// Uses glassmorphism (backdrop-blur + transparent bg) for depth.
// =============================================================================

"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  ScanLine,
  LayoutDashboard,
  History,
  Settings,
  Activity,
  Shield,
  X,
  BarChart3,
  Radio,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/Badge";
import type { HealthResponse } from "@/types";

interface SidebarProps {
  health: HealthResponse | null;
  isOpen: boolean;
  onClose: () => void;
}

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/live", label: "Live Detection", icon: Radio },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/history", label: "History", icon: History },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar({ health, isOpen, onClose }: SidebarProps) {
  const pathname = usePathname();

  // Close sidebar on route change (mobile)
  useEffect(() => {
    onClose();
  }, [pathname]); // eslint-disable-line react-hooks/exhaustive-deps

  // Close on Escape key
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  const sidebarContent = (
    <>
      {/* ── Logo ──────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between border-b border-white/10 px-6 py-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 shadow-lg shadow-cyan-500/25">
            <ScanLine className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-white tracking-wide">
              ANPR
            </h1>
            <p className="text-[10px] text-neutral-500 uppercase tracking-widest">
              AI Detection System
            </p>
          </div>
        </div>
        {/* Close button — visible only on mobile */}
        <button
          onClick={onClose}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-neutral-400 hover:bg-white/10 hover:text-white lg:hidden"
          aria-label="Close sidebar"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* ── Navigation ────────────────────────────────────────────────── */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200",
                isActive
                  ? "bg-cyan-500/15 text-cyan-400 shadow-sm shadow-cyan-500/10"
                  : "text-neutral-400 hover:bg-white/5 hover:text-white"
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* ── System Status ─────────────────────────────────────────────── */}
      <div className="border-t border-white/10 p-4 space-y-3">
        <p className="text-[10px] uppercase tracking-widest text-neutral-500 px-1">
          System Status
        </p>
        <div className="space-y-2">
          <div className="flex items-center justify-between px-1">
            <div className="flex items-center gap-2 text-xs text-neutral-400">
              <Shield className="h-3.5 w-3.5" />
              <span>YOLO Model</span>
            </div>
            <Badge variant={health?.model_loaded ? "success" : "danger"}>
              {health?.model_loaded ? "Online" : "Offline"}
            </Badge>
          </div>
          <div className="flex items-center justify-between px-1">
            <div className="flex items-center gap-2 text-xs text-neutral-400">
              <Activity className="h-3.5 w-3.5" />
              <span>OCR Engine</span>
            </div>
            <Badge variant={health?.ocr_loaded ? "success" : "danger"}>
              {health?.ocr_loaded ? "Online" : "Offline"}
            </Badge>
          </div>
        </div>
      </div>
    </>
  );

  return (
    <>
      {/* ── Desktop sidebar (always visible on lg+) ───────────────────── */}
      <aside className="fixed left-0 top-0 z-40 hidden h-screen w-64 flex-col border-r border-white/10 bg-neutral-950 backdrop-blur-xl lg:flex">
        {sidebarContent}
      </aside>

      {/* ── Mobile overlay + drawer ───────────────────────────────────── */}
      <AnimatePresence>
        {isOpen && (
          <>
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
              onClick={onClose}
              aria-hidden="true"
            />
            {/* Drawer */}
            <motion.aside
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "spring", damping: 25, stiffness: 300 }}
              className="fixed left-0 top-0 z-50 flex h-screen w-64 flex-col border-r border-white/10 bg-neutral-950 shadow-2xl lg:hidden"
            >
              {sidebarContent}
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
