"use client";

import React from "react";
import { RoleGuard } from "@/components/layout/role-guard";
import { AlertTriangle } from "lucide-react";

export default function TeacherReportsPage() {
  return (
    <RoleGuard allowedRoles={["TEACHER", "ADMIN"]}>
      <div className="space-y-4">
        <div className="flex items-center justify-between pb-4 border-b border-slate-200">
          <div>
            <h2 className="text-lg font-semibold text-slate-900 tracking-tight">
              Báo cáo cảnh báo & Cấm thi môn học
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Danh sách sinh viên vi phạm chuyên cần và xuất file Excel theo môn
            </p>
          </div>
        </div>

        <div className="p-8 border border-slate-200 rounded-lg bg-white text-center">
          <AlertTriangle size={36} className="mx-auto text-amber-500 mb-2" />
          <h3 className="text-sm font-semibold text-slate-800">
            Báo cáo cấm thi môn học
          </h3>
          <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
            Hệ thống phân hệ giảng viên đang được khởi tạo cho Task 10.
          </p>
        </div>
      </div>
    </RoleGuard>
  );
}
