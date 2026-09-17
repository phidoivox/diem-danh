"use client";

import React from "react";
import { RoleGuard } from "@/components/layout/role-guard";
import { Award } from "lucide-react";

export default function StudentConductPointsPage() {
  return (
    <RoleGuard allowedRoles={["STUDENT", "ADMIN"]}>
      <div className="space-y-4">
        <div className="flex items-center justify-between pb-4 border-b border-slate-200">
          <div>
            <h2 className="text-lg font-semibold text-slate-900 tracking-tight">
              Điểm rèn luyện & Sổ cái điểm
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Biến động điểm chuyên cần và lịch sử ghi nhận điểm rèn luyện
            </p>
          </div>
        </div>

        <div className="p-8 border border-slate-200 rounded-lg bg-white text-center">
          <Award size={36} className="mx-auto text-slate-400 mb-2" />
          <h3 className="text-sm font-semibold text-slate-800">
            Sổ cái điểm rèn luyện
          </h3>
          <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
            Hệ thống phân hệ sinh viên đang được khởi tạo cho Task 9.
          </p>
        </div>
      </div>
    </RoleGuard>
  );
}
