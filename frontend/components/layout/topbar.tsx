"use client";

import React, { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { API } from "@/lib/api";
import { LogOut, Wifi, WifiOff, ChevronRight } from "lucide-react";

const routeTitleMap: Record<string, { portal: string; title: string }> = {
  "/student/schedule": { portal: "Cổng Sinh viên", title: "Thời khóa biểu" },
  "/student/attendance": { portal: "Cổng Sinh viên", title: "Lịch sử điểm danh" },
  "/student/conduct-points": { portal: "Cổng Sinh viên", title: "Điểm rèn luyện & Sổ cái" },
  "/student/leave-requests": { portal: "Cổng Sinh viên", title: "Đơn xin nghỉ phép" },
  "/teacher/classes": { portal: "Cổng Giảng viên", title: "Lớp học phụ trách" },
  "/teacher/leave-reviews": { portal: "Cổng Giảng viên", title: "Duyệt đơn nghỉ phép" },
  "/teacher/reports": { portal: "Cổng Giảng viên", title: "Báo cáo cấm thi" },
  "/admin/users": { portal: "Quản trị viên", title: "Quản lý người dùng" },
  "/admin/academic": { portal: "Quản trị viên", title: "Lớp học & Thời khóa biểu" },
  "/admin/settings": { portal: "Cấu hình", title: "Tham số hệ thống" },
  "/admin/reports": { portal: "Quản trị viên", title: "Báo cáo cấm thi toàn trường" },
  "/diem-danh": { portal: "Kiosk AI", title: "Điểm danh FaceID & Đồng phục" },
};

export function Topbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, role, logout } = useAuth();
  const [isBackendOnline, setIsBackendOnline] = useState<boolean | null>(null);

  useEffect(() => {
    let isMounted = true;
    const checkBackend = async () => {
      try {
        const res = await fetch(`${API}/docs`, { method: "HEAD", cache: "no-store" });
        if (isMounted) setIsBackendOnline(res.ok || res.status < 500);
      } catch {
        if (isMounted) setIsBackendOnline(false);
      }
    };
    checkBackend();
    const timer = setInterval(checkBackend, 30000);
    return () => {
      isMounted = false;
      clearInterval(timer);
    };
  }, []);

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  const getBreadcrumb = () => {
    // Find matching route or prefix
    for (const [route, info] of Object.entries(routeTitleMap)) {
      if (pathname === route || pathname.startsWith(route + "/")) {
        return info;
      }
    }
    return { portal: "Hệ thống", title: "Bảng điều khiển" };
  };

  const breadcrumb = getBreadcrumb();

  return (
    <header className="h-14 min-h-[56px] border-b border-slate-200 bg-white px-6 flex items-center justify-between select-none">
      {/* Breadcrumb / Page Title */}
      <div className="flex items-center gap-2 text-sm">
        <span className="text-slate-500 font-normal">{breadcrumb.portal}</span>
        <ChevronRight size={14} className="text-slate-400" />
        <h1 className="font-semibold text-slate-900 tracking-tight">{breadcrumb.title}</h1>
      </div>

      {/* Right Controls: Backend status + User info + Logout */}
      <div className="flex items-center gap-4">
        {/* Backend health status indicator */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs bg-slate-50 border border-slate-200 text-slate-600">
          <span
            className={`w-2 h-2 rounded-full ${
              isBackendOnline === true
                ? "bg-emerald-500"
                : isBackendOnline === false
                ? "bg-rose-500"
                : "bg-amber-400"
            }`}
          />
          <span className="text-[11px] font-medium hidden sm:inline">
            {isBackendOnline === true
              ? "Backend Trực tuyến"
              : isBackendOnline === false
              ? "Mất kết nối Backend"
              : "Đang kiểm tra..."}
          </span>
        </div>

        {/* User Summary */}
        {user && (
          <div className="hidden md:flex items-center gap-2 text-xs text-slate-700">
            <span className="font-medium text-slate-900">{user.full_name}</span>
            <span className="text-slate-400">|</span>
            <span className="font-mono tabular-nums text-slate-500">{user.user_code}</span>
            <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold tracking-wider bg-slate-100 text-slate-700 border border-slate-200 uppercase">
              {role}
            </span>
          </div>
        )}

        {/* Logout Button */}
        <button
          onClick={handleLogout}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium text-slate-600 hover:text-rose-700 hover:bg-rose-50 border border-slate-200 hover:border-rose-200 transition-colors"
          title="Đăng xuất khỏi hệ thống"
        >
          <LogOut size={14} />
          <span className="hidden sm:inline">Đăng xuất</span>
        </button>
      </div>
    </header>
  );
}
