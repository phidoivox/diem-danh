"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  Calendar,
  CheckSquare,
  Award,
  FileText,
  BookOpen,
  ClipboardCheck,
  AlertTriangle,
  Users,
  Layers,
  Settings,
  BarChart3,
  Camera,
  Shield,
  GraduationCap,
  Briefcase,
} from "lucide-react";

interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string; size?: number }>;
}

export function Sidebar() {
  const pathname = usePathname();
  const { user, role } = useAuth();

  const studentNav: NavItem[] = [
    { href: "/student/schedule", label: "Thời khóa biểu", icon: Calendar },
    { href: "/student/attendance", label: "Lịch sử điểm danh", icon: CheckSquare },
    { href: "/student/conduct-points", label: "Điểm rèn luyện & Sổ cái", icon: Award },
    { href: "/student/leave-requests", label: "Đơn xin nghỉ phép", icon: FileText },
  ];

  const teacherNav: NavItem[] = [
    { href: "/teacher/classes", label: "Lớp học phụ trách", icon: BookOpen },
    { href: "/teacher/leave-reviews", label: "Duyệt đơn nghỉ phép", icon: ClipboardCheck },
    { href: "/teacher/reports", label: "Báo cáo cấm thi", icon: AlertTriangle },
  ];

  const adminNav: NavItem[] = [
    { href: "/admin/users", label: "Quản lý người dùng", icon: Users },
    { href: "/admin/academic", label: "Lớp học & TKB", icon: Layers },
    { href: "/admin/settings", label: "Cấu hình hệ thống", icon: Settings },
    { href: "/admin/reports", label: "Báo cáo toàn trường", icon: BarChart3 },
  ];

  const commonNav: NavItem[] = [
    { href: "/diem-danh", label: "Điểm danh Kiosk AI", icon: Camera },
  ];

  const renderNavGroup = (title: string, items: NavItem[]) => {
    return (
      <div className="mb-6">
        <div className="px-3 mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
          {title}
        </div>
        <div className="space-y-0.5">
          {items.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                  isActive
                    ? "bg-slate-100 text-slate-900 font-medium"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                }`}
              >
                <Icon size={18} className={isActive ? "text-slate-900" : "text-slate-500"} />
                <span className="truncate">{item.label}</span>
              </Link>
            );
          })}
        </div>
      </div>
    );
  };

  const getRoleBadge = () => {
    switch (role) {
      case "ADMIN":
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-700 border border-slate-200">
            <Shield size={12} />
            Quản trị viên
          </span>
        );
      case "TEACHER":
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-700 border border-slate-200">
            <Briefcase size={12} />
            Giảng viên
          </span>
        );
      case "STUDENT":
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-700 border border-slate-200">
            <GraduationCap size={12} />
            Sinh viên
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <aside className="w-60 min-w-[240px] max-w-[240px] h-screen border-r border-slate-200 bg-white flex flex-col select-none">
      {/* Brand Header */}
      <div className="h-14 border-b border-slate-200 px-4 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded bg-slate-900 flex items-center justify-center text-white font-bold text-xs">
            SC
          </div>
          <div className="flex flex-col">
            <span className="text-sm font-semibold text-slate-900 tracking-tight leading-none">
              Smart Classroom
            </span>
            <span className="text-[10px] text-slate-500 mt-0.5 font-mono">
              Học vụ & Điểm danh AI
            </span>
          </div>
        </div>
      </div>

      {/* Navigation List */}
      <div className="flex-1 overflow-y-auto px-3 py-4">
        {role === "STUDENT" && renderNavGroup("Cổng Sinh viên", studentNav)}
        {role === "TEACHER" && renderNavGroup("Cổng Giảng viên", teacherNav)}
        {role === "ADMIN" && (
          <>
            {renderNavGroup("Quản trị Hệ thống", adminNav)}
            {renderNavGroup("Xem Cổng Giảng viên", teacherNav)}
            {renderNavGroup("Xem Cổng Sinh viên", studentNav)}
          </>
        )}
        {renderNavGroup("Thiết bị & Điểm danh", commonNav)}
      </div>

      {/* Bottom User Card */}
      {user && (
        <div className="p-3 border-t border-slate-200 bg-slate-50/60">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-slate-200 border border-slate-300 flex items-center justify-center text-slate-700 font-medium text-xs">
              {user.full_name ? user.full_name.charAt(0).toUpperCase() : "U"}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-medium text-slate-900 truncate">
                {user.full_name}
              </p>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className="text-[11px] font-mono tabular-nums text-slate-500">
                  {user.user_code}
                </span>
              </div>
            </div>
          </div>
          <div className="mt-2 flex items-center justify-between">
            {getRoleBadge()}
            {user.student_profile && (
              <span className="text-[11px] font-mono tabular-nums text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200">
                {user.student_profile.total_point}đ
              </span>
            )}
          </div>
        </div>
      )}
    </aside>
  );
}
