"use client";

import React, { useState, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { RoleGuard } from "@/components/layout/role-guard";
import {
  AdminClass,
  ExamBanReport,
  getAdminClasses,
  getAdminExamBanReport,
  downloadAllSchoolExamBanExcel,
  getAdminUsers,
} from "@/lib/api";
import {
  BarChart3,
  Download,
  AlertTriangle,
  ShieldAlert,
  GraduationCap,
  BookOpen,
  Users,
  Search,
  CheckCircle2,
  FileSpreadsheet,
  Loader2,
  Filter,
} from "lucide-react";

export default function AdminReportsPage() {
  const queryClient = useQueryClient();
  const [selectedClassId, setSelectedClassId] = useState<number | "">("");
  const [statusFilter, setStatusFilter] = useState<"ALL" | "WARNING" | "BANNED">("ALL");

  const [isDownloading, setIsDownloading] = useState(false);
  const [feedbackMsg, setFeedbackMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const classesQuery = useQuery({
    queryKey: ["admin-classes", 1, ""],
    queryFn: () => getAdminClasses({ page: 1, size: 100, q: "" }),
  });
  const studentsCountQuery = useQuery({
    queryKey: ["admin-users", 1, "STUDENT", "count"],
    queryFn: () => getAdminUsers({ role: "STUDENT", size: 1 }),
  });
  const classes: AdminClass[] = classesQuery.data?.items ?? [];
  const totalStudents = studentsCountQuery.data?.total ?? 0;
  const isLoadingClasses = classesQuery.isPending;

  const reportQuery = useQuery({
    queryKey: ["admin-report", selectedClassId === "" ? 0 : Number(selectedClassId)],
    queryFn: () => getAdminExamBanReport(Number(selectedClassId)),
    enabled: selectedClassId !== "",
  });
  const reportData: ExamBanReport | null = reportQuery.data ?? null;
  const isLoadingReport = reportQuery.isPending || reportQuery.isFetching;

  // Mặc định chọn lớp đầu tiên khi danh sách về.
  useEffect(() => {
    if (selectedClassId === "" && classes.length > 0) {
      setSelectedClassId(classes[0].id);
    }
  }, [classes, selectedClassId]);

  // Surface lỗi query lên feedback chung.
  useEffect(() => {
    const err = classesQuery.error ?? reportQuery.error;
    if (err) {
      setFeedbackMsg({
        type: "error",
        text: err instanceof Error ? err.message : "Không thể tải dữ liệu báo cáo",
      });
    }
  }, [classesQuery.error, reportQuery.error]);

  // Download All School Excel
  const handleDownloadAllExcel = async () => {
    setIsDownloading(true);
    setFeedbackMsg(null);
    try {
      await downloadAllSchoolExamBanExcel("danh_sach_cam_thi_toan_truong.xlsx");
      setFeedbackMsg({
        type: "success",
        text: "Đã xuất và tải về file Excel danh sách cấm thi toàn trường thành công!",
      });
    } catch (err: any) {
      setFeedbackMsg({
        type: "error",
        text: err.message || "Không thể tải file Excel cấm thi",
      });
    } finally {
      setIsDownloading(false);
    }
  };

  // Filter students in current report
  const filteredStudents = (reportData?.students || []).filter((st) => {
    if (statusFilter === "BANNED") return st.is_banned;
    if (statusFilter === "WARNING") return st.is_warning && !st.is_banned;
    return true;
  });

  const bannedCountInClass = (reportData?.students || []).filter((s) => s.is_banned).length;
  const warningCountInClass = (reportData?.students || []).filter(
    (s) => s.is_warning && !s.is_banned
  ).length;

  return (
    <RoleGuard allowedRoles={["ADMIN"]}>
      <div className="space-y-4 sm:space-y-6 max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-200">
          <div>
            <h2 className="text-lg font-semibold text-slate-900 tracking-tight flex items-center gap-2">
              <BarChart3 size={20} className="text-slate-700" />
              Báo cáo Học vụ & Danh sách Cấm thi Toàn trường
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Theo dõi tỷ lệ vắng tích lũy, quản lý danh sách cấm thi học kỳ và xuất báo cáo Đào tạo
            </p>
          </div>

          <button
            onClick={handleDownloadAllExcel}
            disabled={isDownloading}
            className="inline-flex items-center justify-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-slate-900 hover:bg-slate-800 rounded-md transition-colors disabled:opacity-50 cursor-pointer shadow-xs"
          >
            {isDownloading ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <FileSpreadsheet size={16} className="text-emerald-400" />
            )}
            Xuất Danh sách Cấm thi Toàn trường (.xlsx)
          </button>
        </div>

        {/* Feedback Alert */}
        {feedbackMsg && (
          <div
            className={`p-3 text-xs rounded-md border flex items-center justify-between ${
              feedbackMsg.type === "success"
                ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                : "bg-rose-50 text-rose-800 border-rose-200"
            }`}
          >
            <div className="flex items-center gap-2">
              {feedbackMsg.type === "success" ? (
                <CheckCircle2 size={16} className="text-emerald-600 shrink-0" />
              ) : (
                <AlertTriangle size={16} className="text-rose-600 shrink-0" />
              )}
              <span>{feedbackMsg.text}</span>
            </div>
            <button
              onClick={() => setFeedbackMsg(null)}
              className="text-xs font-semibold underline hover:opacity-75 cursor-pointer ml-4"
            >
              Đóng
            </button>
          </div>
        )}

        {/* Overview KPI Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500 font-medium">Lớp học phần</span>
              <div className="p-1.5 bg-slate-100 text-slate-700 rounded-md">
                <BookOpen size={16} />
              </div>
            </div>
            <div className="text-2xl font-bold font-mono tabular-nums text-slate-900 mt-2">
              {classes.length}
            </div>
            <p className="text-[11px] text-slate-400 mt-1">Đang mở trong học kỳ này</p>
          </div>

          <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500 font-medium">Tổng số sinh viên</span>
              <div className="p-1.5 bg-emerald-50 text-emerald-700 rounded-md">
                <GraduationCap size={16} />
              </div>
            </div>
            <div className="text-2xl font-bold font-mono tabular-nums text-slate-900 mt-2">
              {totalStudents}
            </div>
            <p className="text-[11px] text-slate-400 mt-1">Tài khoản sinh viên toàn trường</p>
          </div>

          <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500 font-medium">Ngưỡng cảnh báo</span>
              <div className="p-1.5 bg-amber-50 text-amber-700 rounded-md">
                <AlertTriangle size={16} />
              </div>
            </div>
            <div className="text-2xl font-bold font-mono tabular-nums text-amber-700 mt-2">
              ≥ {reportData?.warning_percent ?? 15}%
            </div>
            <p className="text-[11px] text-slate-400 mt-1">Cảnh báo vắng tích lũy sớm</p>
          </div>

          <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500 font-medium">Quy chuẩn Cấm thi</span>
              <div className="p-1.5 bg-rose-50 text-rose-700 rounded-md">
                <ShieldAlert size={16} />
              </div>
            </div>
            <div className="text-2xl font-bold font-mono tabular-nums text-rose-700 mt-2">
              ≥ {reportData?.ban_percent ?? 20}%
            </div>
            <p className="text-[11px] text-slate-400 mt-1">Vắng trên {reportData?.ban_percent ?? 20}% số buổi cả kỳ</p>
          </div>
        </div>

        {/* Detailed Class Inspection */}
        <div className="bg-white rounded-lg border border-slate-200 shadow-xs overflow-hidden">
          {/* Toolbar */}
          <div className="p-4 border-b border-slate-200 bg-slate-50/50 flex flex-col sm:flex-row sm:items-center justify-between flex-wrap gap-2 sm:gap-3">
            <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3 w-full sm:w-auto">
              <span className="text-xs font-semibold text-slate-700">Xem chi tiết lớp:</span>
              <select
                value={selectedClassId}
                onChange={(e) => setSelectedClassId(e.target.value ? Number(e.target.value) : "")}
                className="w-full sm:w-auto px-3 py-1.5 text-xs rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900 sm:max-w-sm"
              >
                {classes.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.class_code} - {c.course_name} (GV: {c.teacher_name})
                  </option>
                ))}
              </select>
            </div>

            {/* Filter pills */}
            <div className="flex flex-wrap items-center gap-1.5">
              <button
                onClick={() => setStatusFilter("ALL")}
                className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors cursor-pointer ${
                  statusFilter === "ALL"
                    ? "bg-slate-900 text-white"
                    : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                }`}
              >
                Tất cả ({reportData?.students.length || 0})
              </button>
              <button
                onClick={() => setStatusFilter("WARNING")}
                className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors cursor-pointer ${
                  statusFilter === "WARNING"
                    ? "bg-amber-600 text-white"
                    : "bg-amber-50 text-amber-700 border border-amber-200 hover:bg-amber-100"
                }`}
              >
                Cảnh báo ({warningCountInClass})
              </button>
              <button
                onClick={() => setStatusFilter("BANNED")}
                className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors cursor-pointer ${
                  statusFilter === "BANNED"
                    ? "bg-rose-600 text-white"
                    : "bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-100"
                }`}
              >
                Bị cấm thi ({bannedCountInClass})
              </button>
            </div>
          </div>

          {/* Class Overview Stats Bar */}
          {reportData && (
            <div className="px-6 py-3 bg-slate-50 border-b border-slate-200 flex flex-wrap items-center justify-between text-xs text-slate-600 gap-4">
              <div>
                Học kỳ: <span className="font-mono font-semibold text-slate-900">{reportData.semester}</span>
              </div>
              <div>
                Giảng viên: <span className="font-semibold text-slate-900">{reportData.teacher_name}</span>
              </div>
              <div>
                Tiến độ ca học:{" "}
                <span className="font-mono font-semibold text-slate-900 tabular-nums">
                  {reportData.elapsed_sessions} / {reportData.total_sessions} buổi
                </span>
              </div>
            </div>
          )}

          {/* Students Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50/75 border-b border-slate-200 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                  <th className="sticky left-0 bg-slate-50 z-20 px-4 py-3 w-12 text-center">STT</th>
                  <th className="sticky left-12 bg-slate-50 z-20 px-4 py-3">Mã SV</th>
                  <th className="px-4 py-3">Họ và tên</th>
                  <th className="px-4 py-3 hidden md:table-cell">Lớp SH</th>
                  <th className="px-4 py-3 text-center hidden md:table-cell">Vắng (buổi)</th>
                  <th className="px-4 py-3 text-center hidden md:table-cell">Tỷ lệ tích lũy</th>
                  <th className="px-4 py-3 text-center">Tỷ lệ cả kỳ</th>
                  <th className="px-4 py-3 text-center">Trạng thái thi</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs text-slate-700">
                {isLoadingReport ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-12 text-center text-slate-400">
                      <div className="flex flex-col items-center justify-center gap-2">
                        <Loader2 size={24} className="animate-spin text-slate-500" />
                        <span>Đang tính toán tỷ lệ vắng và danh sách cấm thi...</span>
                      </div>
                    </td>
                  </tr>
                ) : filteredStudents.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-12 text-center text-slate-400">
                      Không có sinh viên nào trong danh sách lọc này
                    </td>
                  </tr>
                ) : (
                  filteredStudents.map((st, idx) => (
                    <tr
                      key={st.student_id}
                      className={`hover:bg-slate-50/75 transition-colors ${
                        st.is_banned ? "bg-rose-50/30" : st.is_warning ? "bg-amber-50/20" : ""
                      }`}
                    >
                      <td className="sticky left-0 bg-white z-10 px-4 py-3 text-center font-mono tabular-nums text-slate-400">
                        {idx + 1}
                      </td>
                      <td className="sticky left-12 bg-white z-10 px-4 py-3 font-mono font-medium text-slate-900 tabular-nums">
                        {st.student_code}
                      </td>
                      <td className="px-4 py-3 font-medium text-slate-900">
                        {st.full_name}
                      </td>
                      <td className="px-4 py-3 font-mono text-slate-600 hidden md:table-cell">
                        {st.class_name || "-"}
                      </td>
                      <td className="px-4 py-3 text-center font-mono tabular-nums hidden md:table-cell">
                        <span className="font-semibold text-slate-800">{st.converted_absent ?? 0}</span>
                        <span className="text-slate-400 text-[11px] ml-1">
                          ({st.absent_count}v + {st.half_absent_count}nửa)
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center font-mono tabular-nums hidden md:table-cell">
                        <span
                          className={`font-semibold ${
                            st.is_banned
                              ? "text-rose-600"
                              : st.is_warning
                              ? "text-amber-600"
                              : "text-slate-700"
                          }`}
                        >
                          {(st.cumulative_rate ?? 0).toFixed(1)}%
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center font-mono tabular-nums">
                        <span
                          className={`font-semibold ${
                            st.is_banned ? "text-rose-600" : "text-slate-700"
                          }`}
                        >
                          {(st.semester_rate ?? 0).toFixed(1)}%
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center">
                        {st.is_banned ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-50 text-rose-700 border border-rose-200">
                            <ShieldAlert size={12} />
                            BỊ CẤM THI
                          </span>
                        ) : st.is_warning ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                            <AlertTriangle size={12} />
                            CẢNH BÁO
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                            <CheckCircle2 size={12} />
                            ĐỦ ĐIỀU KIỆN
                          </span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </RoleGuard>
  );
}
