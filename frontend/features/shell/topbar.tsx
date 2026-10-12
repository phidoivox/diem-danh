"use client";

import React from "react";
import { usePathname } from "next/navigation";
import { ChevronRight, Menu } from "lucide-react";

const routeTitleMap: Record<string, { portal: string; title: string }> = {
  "/student/schedule": { portal: "Cổng Sinh viên", title: "Thời khóa biểu" },
  "/student/attendance": { portal: "Cổng Sinh viên", title: "Lịch sử điểm danh" },
  "/student/conduct-points": { portal: "Cổng Sinh viên", title: "Điểm rèn luyện & Sổ cái" },
  "/student/leave-requests": { portal: "Cổng Sinh viên", title: "Đơn xin nghỉ phép" },
  "/teacher/classes": { portal: "Cổng Giảng viên", title: "Lớp học phụ trách" },
  "/teacher/leave-reviews": { portal: "Cổng Giảng viên", title: "Duyệt đơn nghỉ phép" },
  "/teacher/conduct": { portal: "Cổng Giảng viên", title: "Điểm rèn luyện theo lớp" },
  "/teacher/homeroom": { portal: "Cổng Giảng viên", title: "Ban cán sự" },
  "/teacher/reports": { portal: "Cổng Giảng viên", title: "Báo cáo cấm thi" },
  "/admin/users": { portal: "Quản trị viên", title: "Quản lý người dùng" },
  "/admin/academic": { portal: "Quản trị viên", title: "Lớp học & Thời khóa biểu" },
  "/admin/conduct": { portal: "Quản trị viên", title: "Điểm rèn luyện theo lớp" },
  "/admin/settings": { portal: "Cấu hình", title: "Tham số hệ thống" },
  "/admin/reports": { portal: "Quản trị viên", title: "Báo cáo cấm thi toàn trường" },
};

interface TopbarProps {
  onMenuClick?: () => void;
}

export function Topbar({ onMenuClick }: TopbarProps) {
  const pathname = usePathname();

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
    <header className="h-14 min-h-[56px] border-b border-slate-200 bg-white px-4 sm:px-6 flex items-center gap-2 select-none">
      {/* Breadcrumb / Page Title */}
      <div className="min-w-0 flex-1 flex items-center gap-2 text-sm">
        <button
          onClick={onMenuClick}
          aria-label="Mở menu"
          className="md:hidden flex items-center justify-center w-11 h-11 min-w-[44px] min-h-[44px] shrink-0 -ml-2 rounded-md text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-colors"
        >
          <Menu size={20} />
        </button>
        <span className="text-slate-500 font-normal hidden sm:inline truncate min-w-0">{breadcrumb.portal}</span>
        <ChevronRight size={14} className="text-slate-400 shrink-0 hidden sm:inline" />
        <h1 className="font-semibold text-slate-900 tracking-tight truncate min-w-0">{breadcrumb.title}</h1>
      </div>
    </header>
  );
}
