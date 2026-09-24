"use client";

import React, { useState, useMemo, Suspense, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { RoleGuard } from "@/components/layout/role-guard";
import {
  getTeacherClasses,
  getTeacherExamBanReport,
  downloadTeacherExamBanExcel,
  TeacherClass,
  ExamBanReport,
  ExamBanStudent,
} from "@/lib/api";
import {
  AlertTriangle,
  FileSpreadsheet,
  Download,
  Users,
  AlertCircle,
  CheckCircle2,
  XCircle,
  Search,
  Filter,
  RefreshCw,
  BookOpen,
  Calendar,
  Loader2,
  Percent,
} from "lucide-react";

function TeacherReportsContent() {
  const searchParams = useSearchParams();
  const urlClassId = searchParams.get("class_id");
  const queryClient = useQueryClient();

  const [selectedClassId, setSelectedClassId] = useState<number | null>(null);
  const [downloading, setDownloading] = useState<boolean>(false);

  // Table search & filter
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  const classesQuery = useQuery({
    queryKey: ["teacher-classes"],
    queryFn: getTeacherClasses,
  });
  const classes: TeacherClass[] = classesQuery.data ?? [];
  const loadingClasses = classesQuery.isPending;
  const classesError = classesQuery.isError
    ? classesQuery.error instanceof Error
      ? classesQuery.error.message
      : "Không thể tải danh sách lớp học phần."
    : null;

  const reportQuery = useQuery({
    queryKey: ["teacher-report", selectedClassId],
    queryFn: () => getTeacherExamBanReport(selectedClassId!),
    enabled: selectedClassId !== null,
  });
  const report: ExamBanReport | null = reportQuery.data ?? null;
  const loadingReport = reportQuery.isPending || reportQuery.isFetching;
  const reportError = reportQuery.isError
    ? reportQuery.error instanceof Error
      ? reportQuery.error.message
      : "Không thể tải dữ liệu báo cáo cấm thi."
    : null;
  const error = classesError ?? reportError;

  // Mặc định chọn lớp theo ?class_id= hoặc lớp đầu tiên khi classes về.
  useEffect(() => {
    if (classes.length > 0 && selectedClassId === null) {
      const matched = urlClassId
        ? classes.find((c) => c.id === Number(urlClassId))
        : null;
      setSelectedClassId(matched ? matched.id : classes[0].id);
    }
  }, [classes, selectedClassId, urlClassId]);

  // Selected Class details
  const currentClass = useMemo(() => {
    return classes.find((c) => c.id === selectedClassId);
  }, [classes, selectedClassId]);

  // Students list filtered
  const filteredStudents = useMemo(() => {
    if (!report?.students) return [];

    return report.students.filter((st) => {
      const q = searchQuery.toLowerCase().trim();
      const matchSearch =
        !q ||
        st.student_code.toLowerCase().includes(q) ||
        st.full_name.toLowerCase().includes(q) ||
        (st.class_name && st.class_name.toLowerCase().includes(q));

      let matchStatus = true;
      if (statusFilter === "BANNED") {
        matchStatus = st.is_banned;
      } else if (statusFilter === "WARNING") {
        matchStatus = st.is_warning && !st.is_banned;
      } else if (statusFilter === "ELIGIBLE") {
        matchStatus = !st.is_banned && !st.is_warning;
      }

      return matchSearch && matchStatus;
    });
  }, [report?.students, searchQuery, statusFilter]);

  // Metrics summary
  const summary = useMemo(() => {
    if (!report?.students || report.students.length === 0) {
      return {
        total: 0,
        banned: 0,
        warning: 0,
        eligible: 0,
        maxRate: 0,
      };
    }

    let banned = 0;
    let warning = 0;
    let eligible = 0;
    let maxRate = 0;

    report.students.forEach((st) => {
      const semRate = st.semester_rate ?? st.rate_semester ?? 0;
      if (semRate > maxRate) maxRate = semRate;

      if (st.is_banned) banned++;
      else if (st.is_warning) warning++;
      else eligible++;
    });

    return {
      total: report.students.length,
      banned,
      warning,
      eligible,
      maxRate: Math.round(maxRate * 10) / 10,
    };
  }, [report?.students]);

  // Ngưỡng backend đang áp dụng (Admin đổi ở /admin/settings thì trang này đổi theo)
  const warnPercent = report?.warning_percent ?? 15;
  const banPercent = report?.ban_percent ?? 20;

  // Export excel
  const handleExportExcel = async () => {
    if (!selectedClassId || !currentClass) return;
    try {
      setDownloading(true);
      const filename = `bao_cao_cam_thi_${currentClass.class_code}.xlsx`;
      await downloadTeacherExamBanExcel(selectedClassId, filename);
    } catch (err: any) {
      toast.error(err?.message || "Không thể xuất file Excel.");
    } finally {
      setDownloading(false);
    }
  };

  const renderStatusBadge = (st: ExamBanStudent) => {
    if (st.is_banned) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-[11px] font-bold bg-rose-50 text-rose-700 border border-rose-200">
          <XCircle size={12} />
          BỊ CẤM THI
        </span>
      );
    }
    if (st.is_warning) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
          <AlertCircle size={12} />
          CẢNH BÁO
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
        <CheckCircle2 size={12} />
        ĐỦ ĐIỀU KIỆN
      </span>
    );
  };

  return (
    <div className="p-4 sm:p-6 max-w-7xl mx-auto space-y-4 sm:space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2 text-slate-500 text-xs font-semibold uppercase tracking-wider mb-1">
            <AlertTriangle size={15} />
            <span>Phân hệ Giảng viên</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            Báo cáo Chuyên cần & Danh sách Cấm thi
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Theo dõi tỷ lệ vắng theo quy chế học vụ (Cảnh báo ≥ {warnPercent}%, Cấm thi ≥ {banPercent}%) và xuất file Excel
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex flex-wrap items-center gap-2.5 self-start sm:self-auto">
          <button
            type="button"
            onClick={handleExportExcel}
            disabled={downloading || !report || loadingReport}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-md text-sm font-medium text-white bg-slate-900 hover:bg-slate-800 shadow-sm transition-colors disabled:opacity-50"
          >
            {downloading ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <FileSpreadsheet size={15} className="text-emerald-400" />
            )}
            <span>Xuất file Excel (.xlsx)</span>
          </button>
        </div>
      </div>

      {/* Class Selector Bar */}
      <div className="p-4 bg-white rounded-lg border border-slate-200 shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between flex-wrap gap-3 sm:gap-4">
        <div className="flex flex-col sm:flex-row sm:items-center gap-3 w-full sm:w-auto">
          <label
            htmlFor="select-class"
            className="text-xs font-semibold text-slate-700 uppercase tracking-wider shrink-0"
          >
            Chọn lớp học phần:
          </label>
          <select
            id="select-class"
            value={selectedClassId || ""}
            onChange={(e) => setSelectedClassId(Number(e.target.value))}
            disabled={loadingClasses || classes.length === 0}
            className="w-full sm:w-auto px-3 py-2 text-sm rounded-md border border-slate-200 bg-slate-50 text-slate-900 font-medium focus:outline-none focus:ring-1 focus:ring-slate-400 sm:min-w-[260px]"
          >
            {classes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.class_code} - {c.course_name} ({c.semester})
              </option>
            ))}
          </select>
        </div>

        {currentClass && report && (
          <div className="flex items-center gap-4 text-xs text-slate-500 font-mono tabular-nums">
            <span>
              Đã học: <strong className="text-slate-800">{report.elapsed_sessions}</strong>/
              {report.total_sessions} buổi
            </span>
            <span>•</span>
            <span>
              Sĩ số: <strong className="text-slate-800">{currentClass.student_count}</strong> SV
            </span>
          </div>
        )}
      </div>

      {/* Error Notice */}
      {error && (
        <div className="p-4 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button
            onClick={() => {
              queryClient.invalidateQueries({ queryKey: ["teacher-classes"] });
              if (selectedClassId) {
                queryClient.invalidateQueries({
                  queryKey: ["teacher-report", selectedClassId],
                });
              }
            }}
            className="text-xs font-semibold underline hover:no-underline ml-4"
          >
            Thử lại
          </button>
        </div>
      )}

      {/* 4 Summary Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total students */}
        <div className="p-4 bg-white rounded-lg border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">
              Tổng sĩ số lớp
            </p>
            <p className="text-2xl font-bold font-mono tabular-nums text-slate-900 mt-1">
              {summary.total}
            </p>
            <p className="text-[11px] text-slate-400 mt-0.5">Sinh viên theo học</p>
          </div>
          <div className="w-10 h-10 rounded-md bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-600">
            <Users size={20} />
          </div>
        </div>

        {/* Banned count */}
        <div className="p-4 bg-white rounded-lg border border-rose-200 shadow-sm bg-rose-50/20 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-rose-700 uppercase tracking-wider">
              Bị cấm thi
            </p>
            <p className="text-2xl font-bold font-mono tabular-nums text-rose-700 mt-1">
              {summary.banned}
            </p>
            <p className="text-[11px] text-rose-600/80 mt-0.5">
              Vắng cả kỳ ≥ {banPercent}%
            </p>
          </div>
          <div className="w-10 h-10 rounded-md bg-rose-100 border border-rose-200 flex items-center justify-center text-rose-700">
            <XCircle size={20} />
          </div>
        </div>

        {/* Warning count */}
        <div className="p-4 bg-white rounded-lg border border-amber-200 shadow-sm bg-amber-50/20 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-amber-700 uppercase tracking-wider">
              Nguy cơ cảnh báo
            </p>
            <p className="text-2xl font-bold font-mono tabular-nums text-amber-700 mt-1">
              {summary.warning}
            </p>
            <p className="text-[11px] text-amber-600/80 mt-0.5">
              Vắng lũy kế ≥ {warnPercent}%
            </p>
          </div>
          <div className="w-10 h-10 rounded-md bg-amber-100 border border-amber-200 flex items-center justify-center text-amber-700">
            <AlertCircle size={20} />
          </div>
        </div>

        {/* Max rate */}
        <div className="p-4 bg-white rounded-lg border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">
              Tỷ lệ vắng cao nhất
            </p>
            <p className="text-2xl font-bold font-mono tabular-nums text-slate-900 mt-1">
              {summary.maxRate}%
            </p>
            <p className="text-[11px] text-slate-400 mt-0.5">
              {summary.eligible} SV đủ điều kiện
            </p>
          </div>
          <div className="w-10 h-10 rounded-md bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-600">
            <Percent size={20} />
          </div>
        </div>
      </div>

      {/* Toolbar: Search and Status filter */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between flex-wrap gap-2 sm:gap-3 p-3 bg-white rounded-lg border border-slate-200 shadow-sm">
        <div className="relative w-full sm:w-auto flex-1 sm:max-w-xs">
          <Search
            size={15}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
          />
          <input
            type="text"
            placeholder="Tìm theo MSSV, Họ tên..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 text-xs rounded-md border border-slate-200 bg-slate-50/50 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
          />
        </div>

        <div className="flex flex-wrap items-center gap-1 self-start sm:self-auto">
          {[
            { id: "ALL", label: "Tất cả" },
            { id: "BANNED", label: `Cấm thi (${summary.banned})` },
            { id: "WARNING", label: `Cảnh báo (${summary.warning})` },
            { id: "ELIGIBLE", label: "Đủ điều kiện" },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setStatusFilter(tab.id)}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                statusFilter === tab.id
                  ? "bg-slate-900 text-white shadow-xs"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Loading */}
      {loadingReport && (
        <div className="p-12 text-center bg-white rounded-lg border border-slate-200">
          <div className="flex items-center justify-center gap-3 text-slate-500 text-sm">
            <span className="w-5 h-5 rounded-full border-2 border-slate-300 border-t-slate-800 animate-spin" />
            <span>Đang tính toán tỷ lệ vắng và lập danh sách cấm thi...</span>
          </div>
        </div>
      )}

      {/* Students Data Table */}
      {!loadingReport && report && (
        <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                <tr>
                  <th className="sticky left-0 bg-slate-50 z-20 px-4 py-3 w-12 text-center">STT</th>
                  <th className="sticky left-12 bg-slate-50 z-20 px-4 py-3">Mã SV</th>
                  <th className="px-4 py-3">Họ và tên</th>
                  <th className="px-4 py-3 hidden md:table-cell">Lớp SH</th>
                  <th className="px-4 py-3 text-center">Vắng (buổi)</th>
                  <th className="px-4 py-3 text-center hidden md:table-cell">Nửa buổi</th>
                  <th className="px-4 py-3 text-center hidden md:table-cell">Vắng Q.Đổi (V)</th>
                  <th className="px-4 py-3 text-center">Vắng Lũy kế (%)</th>
                  <th className="px-4 py-3 text-center">Vắng Cả kỳ (%)</th>
                  <th className="px-4 py-3 text-right">Trạng thái</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredStudents.length === 0 ? (
                  <tr>
                    <td
                      colSpan={10}
                      className="px-4 py-8 text-center text-xs text-slate-400"
                    >
                      Không có sinh viên nào khớp với điều kiện tìm kiếm.
                    </td>
                  </tr>
                ) : (
                  filteredStudents.map((st, idx) => {
                    const cumRate = st.cumulative_rate ?? st.rate_cumulative ?? 0;
                    const semRate = st.semester_rate ?? st.rate_semester ?? 0;
                    const convAbsent =
                      st.converted_absent ?? (st.absent_count + 0.5 * st.half_absent_count);

                    return (
                      <tr
                        key={st.student_id}
                        className={`hover:bg-slate-50/70 transition-colors ${
                          st.is_banned
                            ? "bg-rose-50/30"
                            : st.is_warning
                            ? "bg-amber-50/20"
                            : ""
                        }`}
                      >
                        <td className="sticky left-0 bg-white z-10 px-4 py-3 text-center text-xs text-slate-400 font-mono tabular-nums">
                          {idx + 1}
                        </td>
                        <td className="sticky left-12 bg-white z-10 px-4 py-3 font-mono tabular-nums text-xs font-semibold text-slate-900">
                          {st.student_code}
                        </td>
                        <td className="px-4 py-3 font-medium text-slate-900">
                          {st.full_name}
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-500 hidden md:table-cell">
                          {st.class_name || "--"}
                        </td>
                        <td className="px-4 py-3 text-center font-mono tabular-nums text-xs text-slate-700">
                          {st.absent_count}
                        </td>
                        <td className="px-4 py-3 text-center font-mono tabular-nums text-xs text-slate-700 hidden md:table-cell">
                          {st.half_absent_count}
                        </td>
                        <td className="px-4 py-3 text-center font-mono tabular-nums text-xs font-semibold text-slate-900 hidden md:table-cell">
                          {convAbsent}
                        </td>
                        <td
                          className={`px-4 py-3 text-center font-mono tabular-nums text-xs font-semibold ${
                            st.is_banned
                              ? "text-rose-700"
                              : st.is_warning
                              ? "text-amber-700"
                              : "text-slate-700"
                          }`}
                        >
                          {cumRate}%
                        </td>
                        <td
                          className={`px-4 py-3 text-center font-mono tabular-nums text-xs font-semibold ${
                            st.is_banned ? "text-rose-700 font-bold" : "text-slate-700"
                          }`}
                        >
                          {semRate}%
                        </td>
                        <td className="px-4 py-3 text-right">
                          {renderStatusBadge(st)}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

export default function TeacherReportsPage() {
  return (
    <RoleGuard allowedRoles={["TEACHER"]}>
      <Suspense
        fallback={
          <div className="p-12 text-center bg-slate-50">
            <div className="flex items-center justify-center gap-3 text-slate-500 text-sm">
              <span className="w-5 h-5 rounded-full border-2 border-slate-300 border-t-slate-800 animate-spin" />
              <span>Đang tải báo cáo học vụ...</span>
            </div>
          </div>
        }
      >
        <TeacherReportsContent />
      </Suspense>
    </RoleGuard>
  );
}
