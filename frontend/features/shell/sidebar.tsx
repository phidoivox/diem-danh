"use client";

import React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "./auth-context";
import { UserAvatar } from "./user-avatar";
import {
  Calendar,
  Award,
  FileText,
  BookOpen,
  ClipboardCheck,
  AlertTriangle,
  Users,
  Layers,
  Settings,
  BarChart3,
  LogOut,
  X,
} from "lucide-react";

interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string; size?: number }>;
}

interface SidebarProps {
  open?: boolean;
  onClose?: () => void;
  onNavigate?: () => void;
}

export function Sidebar({ open = false, onClose, onNavigate }: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, role, logout } = useAuth();

  const handleClose = () => {
    if (typeof document !== "undefined" && document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }
    onClose?.();
  };

  const handleLogout = () => {
    if (typeof document !== "undefined" && document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }
    logout();
    onNavigate?.();
    onClose?.();
    router.push("/login");
  };

  // Trạng thái online/offline của phiên hiện tại theo kết nối mạng trình duyệt.
  const [isOnline, setIsOnline] = React.useState<boolean>(() =>
    typeof navigator === "undefined" ? true : navigator.onLine
  );
  React.useEffect(() => {
    const goOnline = () => setIsOnline(true);
    const goOffline = () => setIsOnline(false);
    window.addEventListener("online", goOnline);
    window.addEventListener("offline", goOffline);
    return () => {
      window.removeEventListener("online", goOnline);
      window.removeEventListener("offline", goOffline);
    };
  }, []);

  const studentNav: NavItem[] = [
    { href: "/student/schedule", label: "Thời khóa biểu", icon: Calendar },
    { href: "/student/conduct-points", label: "Điểm rèn luyện & Sổ cái", icon: Award },
    { href: "/student/leave-requests", label: "Đơn xin nghỉ phép", icon: FileText },
  ];

  const teacherNav: NavItem[] = [
    { href: "/teacher/classes", label: "Lớp học phụ trách", icon: BookOpen },
    { href: "/teacher/leave-reviews", label: "Duyệt đơn nghỉ phép", icon: ClipboardCheck },
    { href: "/teacher/conduct", label: "Điểm rèn luyện", icon: Award },
    { href: "/teacher/homeroom", label: "Ban cán sự", icon: Users },
    { href: "/teacher/reports", label: "Báo cáo cấm thi", icon: AlertTriangle },
  ];

  const adminNav: NavItem[] = [
    { href: "/admin/users", label: "Quản lý người dùng", icon: Users },
    { href: "/admin/academic", label: "Lớp học & TKB", icon: Layers },
    { href: "/admin/conduct", label: "Điểm rèn luyện", icon: Award },
    { href: "/admin/settings", label: "Cấu hình hệ thống", icon: Settings },
    { href: "/admin/reports", label: "Báo cáo toàn trường", icon: BarChart3 },
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
                onClick={() => {
                  if (typeof document !== "undefined" && document.activeElement instanceof HTMLElement) {
                    document.activeElement.blur();
                  }
                  onNavigate?.();
                }}
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

  const getRoleLabel = () => {
    switch (role) {
      case "ADMIN":
        return "Quản trị viên";
      case "TEACHER":
        return "Giảng viên";
      case "STUDENT":
        return "Sinh viên";
      default:
        return "";
    }
  };

  const brandHeader = (
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
            Học vụ & Điểm danh
          </span>
        </div>
      </div>
    </div>
  );

  const navList = (
    <div className="flex-1 overflow-y-auto px-3 py-4">
      {role === "STUDENT" && renderNavGroup("Cổng Sinh viên", studentNav)}
      {role === "TEACHER" && renderNavGroup("Cổng Giảng viên", teacherNav)}
      {role === "ADMIN" && renderNavGroup("Quản trị Hệ thống", adminNav)}
    </div>
  );

  const userRow = user && (
    <div className="p-3 pb-[max(12px,env(safe-area-inset-bottom))] border-t border-slate-200">
      <div className="flex items-center gap-2.5 px-1 py-1">
        <UserAvatar
          user={user}
          size="sm"
          showStatusDot={false}
          presence={isOnline ? "online" : "offline"}
        />
        <div className="min-w-0 flex-1">
          <p
            className="text-[13px] font-medium text-slate-800 truncate leading-tight"
            title={user.full_name}
          >
            {user.full_name}
          </p>
          <p className="text-[11px] text-slate-500 truncate mt-px">
            {user.user_code}
            {getRoleLabel() && ` · ${getRoleLabel()}`}
            {user.student_profile && ` · ${user.student_profile.total_point}đ`}
          </p>
        </div>
        <button
          onClick={handleLogout}
          title="Đăng xuất"
          aria-label="Đăng xuất"
          className="flex shrink-0 items-center justify-center w-9 h-9 rounded-md border border-slate-200 text-slate-500 transition-colors hover:border-rose-200 hover:bg-rose-50 hover:text-rose-700"
        >
          <LogOut size={16} />
        </button>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop: sidebar 240px cố định */}
      <aside className="hidden md:flex w-60 min-w-[240px] max-w-[240px] shrink-0 h-screen border-r border-slate-200 bg-white flex-col select-none">
        {brandHeader}
        {navList}
        {userRow}
      </aside>

      {/* Mobile: overlay */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/50 md:hidden"
          onClick={handleClose}
          aria-hidden="true"
        />
      )}

      {/* Mobile: drawer */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-[280px] max-w-[85vw] bg-white transition-transform duration-200 md:hidden flex flex-col border-r border-slate-200 select-none pb-safe ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
        inert={!open ? true : undefined}
      >
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
                Học vụ & Điểm danh
              </span>
            </div>
          </div>
          <button
            onClick={handleClose}
            aria-label="Đóng menu"
            className="flex items-center justify-center w-11 h-11 min-w-[44px] min-h-[44px] shrink-0 -mr-2 rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-900 transition-colors"
          >
            <X size={20} />
          </button>
        </div>
        {navList}
        {userRow}
      </aside>
    </>
  );
}
