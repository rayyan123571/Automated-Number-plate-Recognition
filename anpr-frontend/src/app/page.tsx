// =============================================================================
// app/page.tsx — Dashboard Entry Point
// =============================================================================
// Server component that renders the client-side Dashboard within the
// DashboardLayout shell. This is the landing page of the application.
// =============================================================================

import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Dashboard } from "@/components/Dashboard";

export default function HomePage() {
  return (
    <DashboardLayout>
      <Dashboard />
    </DashboardLayout>
  );
}
