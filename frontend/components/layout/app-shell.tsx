"use client";

import React, { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { isAuthenticated, isLoading, role } = useAuth();

  const isStandalonePage =
    pathname === "/login" ||
    pathname.startsWith("/login/") ||
    pathname === "/diem-danh" ||
    pathname.startsWith("/diem-danh/");

  useEffect(() => {
    // If auth state resolved and user is not authenticated on a protected route, redirect to /login
    if (!isLoading && !isAuthenticated && !isStandalonePage && pathname !== "/") {
      router.push("/login");
    }
  }, [isLoading, isAuthenticated, isStandalonePage, pathname, router]);

  // For standalone pages (e.g. login, Kiosk mode full screen)
  if (isStandalonePage) {
    return <div className="min-h-screen w-full bg-slate-50">{children}</div>;
  }

  // Loading state before session check
  if (isLoading) {
    return (
      <div className="h-screen w-screen flex flex-col items-center justify-center bg-slate-50 text-slate-600 select-none">
        <div className="flex items-center gap-3 text-sm">
          <span className="w-4 h-4 rounded-full border-2 border-slate-300 border-t-slate-800 animate-spin" />
          <span>Đang tải hệ thống...</span>
        </div>
      </div>
    );
  }

  // Unified SaaS Shell Layout
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-50 text-slate-900 font-sans antialiased">
      <Sidebar />
      <div className="flex flex-col flex-1 min-w-0 h-full overflow-hidden">
        <Topbar />
        <main className="flex-1 overflow-y-auto p-6 bg-slate-50">
          {children}
        </main>
      </div>
    </div>
  );
}
