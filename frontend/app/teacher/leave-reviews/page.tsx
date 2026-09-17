"use client";

import React from "react";
import { RoleGuard } from "@/components/layout/role-guard";
import { ClipboardCheck } from "lucide-react";

export default function TeacherLeaveReviewsPage() {
  return (
    <RoleGuard allowedRoles={["TEACHER", "ADMIN"]}>
      <div className="space-y-4">
        <div className="flex items-center justify-between pb-4 border-b border-slate-200">
          <div>
            <h2 className="text-lg font-semibold text-slate-900 tracking-tight">
              Duyệt đơn nghỉ phép sinh viên
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Xem xét đơn xin phép kèm minh chứng y tế/giấy tờ học vụ
            </p>
          </div>
        </div>

        <div className="p-8 border border-slate-200 rounded-lg bg-white text-center">
          <ClipboardCheck size={36} className="mx-auto text-slate-400 mb-2" />
          <h3 className="text-sm font-semibold text-slate-800">
            Duyệt đơn nghỉ phép
          </h3>
          <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
            Hệ thống phân hệ giảng viên đang được khởi tạo cho Task 10.
          </p>
        </div>
      </div>
    </RoleGuard>
  );
}
