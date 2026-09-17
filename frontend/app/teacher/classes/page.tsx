"use client";

import React from "react";
import { RoleGuard } from "@/components/layout/role-guard";
import { BookOpen } from "lucide-react";

export default function TeacherClassesPage() {
  return (
    <RoleGuard allowedRoles={["TEACHER", "ADMIN"]}>
      <div className="space-y-4">
        <div className="flex items-center justify-between pb-4 border-b border-slate-200">
          <div>
            <h2 className="text-lg font-semibold text-slate-900 tracking-tight">
              Lớp học phần phụ trách
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Danh sách lớp học, sĩ số thời gian thực và quản lý điểm danh
            </p>
          </div>
        </div>

        <div className="p-8 border border-slate-200 rounded-lg bg-white text-center">
          <BookOpen size={36} className="mx-auto text-slate-400 mb-2" />
          <h3 className="text-sm font-semibold text-slate-800">
            Danh sách lớp học giảng viên
          </h3>
          <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
            Hệ thống phân hệ giảng viên đang được khởi tạo cho Task 10.
          </p>
        </div>
      </div>
    </RoleGuard>
  );
}
