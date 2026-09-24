"use client";

import React, { useEffect, useState } from "react";
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
  const { isAuthenticated, isLoading } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const isStandalonePage =
    pathname === "/login" ||
    pathname.startsWith("/login/");

  useEffect(() => {
    // If auth state resolved and user is not authenticated on a protected route, redirect to /login
    if (!isLoading && !isAuthenticated && !isStandalonePage && pathname !== "/") {
      router.push("/login");
    }
  }, [isLoading, isAuthenticated, isStandalonePage, pathname, router]);

  // Đóng drawer khi pathname đổi (điều hướng mobile)
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSidebarOpen(false);
  }, [pathname]);

  // Lock body scroll khi drawer mobile mở
  useEffect(() => {
    if (sidebarOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [sidebarOpen]);

  // For standalone pages (e.g. login)
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
    <div className="flex h-[100dvh] w-full overflow-hidden bg-slate-50 text-slate-900 font-sans antialiased">
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onNavigate={() => setSidebarOpen(false)}
      />
      <div className="flex flex-col flex-1 min-w-0 h-full overflow-hidden">
        <Topbar onMenuClick={() => setSidebarOpen(true)} />
        <main className="flex-1 overflow-y-auto p-3 sm:p-5 lg:p-8 bg-slate-50 pb-safe">
          {children}
        </main>
      </div>
    </div>
  );
}
