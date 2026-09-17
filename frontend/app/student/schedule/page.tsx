"use client";

import React from "react";
import { RoleGuard } from "@/components/layout/role-guard";
import { Calendar } from "lucide-react";

export default function StudentSchedulePage() {
  return (
    <RoleGuard allowedRoles={["STUDENT", "ADMIN"]}>
      <div className="space-y-4">
        <div className="flex items-center justify-between pb-4 border-b border-slate-200">
          <div>
            <h2 className="text-lg font-semibold text-slate-900 tracking-tight">
              Thời khóa biểu cá nhân
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Danh sách lịch học theo tuần và phòng học phân bổ
            </p>
          </div>
        </div>

        <div className="p-8 border border-slate-200 rounded-lg bg-white text-center">
          <Calendar size={36} className="mx-auto text-slate-400 mb-2" />
          <h3 className="text-sm font-semibold text-slate-800">
            Đang tải dữ liệu thời khóa biểu...
          </h3>
          <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
            Hệ thống phân hệ sinh viên đang được khởi tạo cho Task 9.
          </p>
        </div>
      </div>
    </RoleGuard>
  );
}
