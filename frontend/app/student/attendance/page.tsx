"use client";

import React from "react";
import { RoleGuard } from "@/components/layout/role-guard";
import { CheckSquare } from "lucide-react";

export default function StudentAttendancePage() {
  return (
    <RoleGuard allowedRoles={["STUDENT", "ADMIN"]}>
      <div className="space-y-4">
        <div className="flex items-center justify-between pb-4 border-b border-slate-200">
          <div>
            <h2 className="text-lg font-semibold text-slate-900 tracking-tight">
              Lịch sử điểm danh
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Theo dõi lịch sử check-in, check-out và tác phong đồng phục
            </p>
          </div>
        </div>

        <div className="p-8 border border-slate-200 rounded-lg bg-white text-center">
          <CheckSquare size={36} className="mx-auto text-slate-400 mb-2" />
          <h3 className="text-sm font-semibold text-slate-800">
            Lịch sử điểm danh cá nhân
          </h3>
          <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
            Hệ thống phân hệ sinh viên đang được khởi tạo cho Task 9.
          </p>
        </div>
      </div>
    </RoleGuard>
  );
}
