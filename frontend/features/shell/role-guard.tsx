"use client";

import React, { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "./auth-context";
import { UserRole, getDefaultPortalPath } from "./http";
import { ShieldAlert, ArrowLeft, LogOut } from "lucide-react";
import Link from "next/link";

interface RoleGuardProps {
  allowedRoles: UserRole[];
  children: React.ReactNode;
}

export function RoleGuard({ allowedRoles, children }: RoleGuardProps) {
  const { user, role, isLoading, isAuthenticated, logout } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isLoading, isAuthenticated, router]);

  if (isLoading) {
    return (
      <div className="h-full flex-1 flex flex-col items-center justify-center p-8 bg-slate-50 select-none">
        <div className="flex items-center gap-3 text-slate-500 text-sm">
          <span className="w-4 h-4 rounded-full border-2 border-slate-300 border-t-slate-800 animate-spin" />
          <span>Đang xác thực quyền truy cập...</span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated || !user || !role) {
    return null;
  }

  const isAllowed = allowedRoles.includes(role);

  if (!isAllowed) {
    return (
      <div className="h-full flex-1 flex flex-col items-center justify-center p-8 bg-slate-50">
        <div className="w-full max-w-md bg-white border border-slate-200 rounded-lg p-6 shadow-xs text-center">
          <div className="w-12 h-12 rounded-full bg-rose-50 border border-rose-200 text-rose-600 flex items-center justify-center mx-auto mb-4">
            <ShieldAlert size={24} />
          </div>
          <h2 className="text-lg font-semibold text-slate-900 tracking-tight">
            403 - Quyền truy cập bị từ chối
          </h2>
          <p className="mt-2 text-sm text-slate-600">
            Tài khoản{" "}
            <span className="font-mono font-medium text-slate-800 tabular-nums">
              {user.user_code}
            </span>{" "}
            với vai trò{" "}
            <span className="font-semibold text-slate-800">{role}</span> không được phép
            truy cập trang này.
          </p>
          <div className="mt-6 flex flex-col sm:flex-row items-center justify-center gap-2">
            <Link
              href={getDefaultPortalPath(role)}
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-4 py-2 text-xs font-medium rounded-md bg-slate-900 text-white hover:bg-slate-800 transition-colors"
            >
              <ArrowLeft size={14} />
              Về phân hệ của bạn
            </Link>
            <button
              onClick={() => {
                logout();
                router.push("/login");
              }}
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-4 py-2 text-xs font-medium rounded-md border border-slate-200 text-slate-700 hover:bg-slate-50 transition-colors"
            >
              <LogOut size={14} />
              Đăng xuất
            </button>
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
