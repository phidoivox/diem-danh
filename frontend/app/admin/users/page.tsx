"use client";

import React from "react";
import { RoleGuard } from "@/components/layout/role-guard";
import { Users } from "lucide-react";

export default function AdminUsersPage() {
  return (
    <RoleGuard allowedRoles={["ADMIN"]}>
      <div className="space-y-4">
        <div className="flex items-center justify-between pb-4 border-b border-slate-200">
          <div>
            <h2 className="text-lg font-semibold text-slate-900 tracking-tight">
              Quản lý người dùng hệ thống
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Danh sách tài khoản sinh viên, giảng viên và quản trị viên
            </p>
          </div>
        </div>

        <div className="p-8 border border-slate-200 rounded-lg bg-white text-center">
          <Users size={36} className="mx-auto text-slate-400 mb-2" />
          <h3 className="text-sm font-semibold text-slate-800">
            Quản lý tài khoản & Hồ sơ sinh viên
          </h3>
          <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
            Hệ thống phân hệ quản trị đang được khởi tạo cho Task 11.
          </p>
        </div>
      </div>
    </RoleGuard>
  );
}
