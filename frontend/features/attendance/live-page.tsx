"use client";

import React, { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { RoleGuard } from "@/features/shell";
import { SearchInput } from "@/features/shell";
import {
  getTeacherLiveAttendance,
  LiveAttendanceStudent,
} from "@/features/shell";
import { formatTime as formatTimeVN } from "@/features/shell";
import {
  ManualOverrideModal,
  OverrideTarget,
} from "./manual-override-modal";
import {
  AttendanceHistoryModal,
  HistoryTarget,
} from "./attendance-history-modal";
import {
  ArrowLeft,
  Users,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  Radio,
  RefreshCw,
  Edit3,
  Calendar,
  MapPin,
  FileCheck,
  ClipboardCheck,
  History,
} from "lucide-react";

export default function TeacherLiveAttendancePage() {
  const params = useParams();
  const router = useRouter();
  const classId = Number(params?.id);

  // Auto-refresh 5s qua react-query (thay setInterval+timerRef tay).
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true);

  // Filtering & Search
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  // Modal target
  const [overrideTarget, setOverrideTarget] = useState<OverrideTarget | null>(null);
  const [isOverrideModalOpen, setIsOverrideModalOpen] = useState<boolean>(false);

  // Modal lịch sử điểm danh từng SV
  const [historyTarget, setHistoryTarget] = useState<HistoryTarget | null>(null);
  const [isHistoryModalOpen, setIsHistoryModalOpen] = useState<boolean>(false);

  const queryClient = useQueryClient();
  const liveQuery = useQuery({
    queryKey: ["teacher-live", classId],
    queryFn: () => getTeacherLiveAttendance(classId),
    enabled: !!classId && !isNaN(classId),
    // Không poll tab ẩn (tiết kiệm pin + tránh token/request thừa nền).
    refetchInterval: autoRefresh ? 5000 : false,
    refetchIntervalInBackground: false,
  });
  const liveData = liveQuery.data ?? null;
  const loading = liveQuery.isPending;
  const refreshing = liveQuery.isFetching && !liveQuery.isPending;
  const error = liveQuery.isError
    ? liveQuery.error instanceof Error
      ? liveQuery.error.message
      : "Không thể tải dữ liệu điểm danh thời gian thực."
    : null;
  const lastUpdated = liveQuery.dataUpdatedAt ? new Date(liveQuery.dataUpdatedAt) : new Date();

  const refetchLive = () => queryClient.invalidateQueries({ queryKey: ["teacher-live", classId] });

  // Open modal handler
  const handleOpenOverride = (st: LiveAttendanceStudent) => {
    setOverrideTarget({
      attendanceId: st.attendance_id,
      studentId: st.student_id,
      studentCode: st.student_code,
      studentName: st.full_name,
      className: st.class_name,
      currentStatus: st.status,
      scheduleId: liveData?.schedule_id || null,
    });
    setIsOverrideModalOpen(true);
  };

  // Open history modal handler
  const handleOpenHistory = (st: LiveAttendanceStudent) => {
    setHistoryTarget({
      studentId: st.student_id,
      studentCode: st.student_code,
      studentName: st.full_name,
      className: st.class_name,
    });
    setIsHistoryModalOpen(true);
  };

  // Filtered students list (pure filter; React Compiler auto-memoizes,
  // no manual useMemo so inferred/liveData.students dep mismatch can't occur).
  const filteredStudents = (liveData?.students ?? []).filter((s) => {
    const q = searchQuery.toLowerCase().trim();
    const matchSearch =
      !q ||
      s.student_code.toLowerCase().includes(q) ||
      s.full_name.toLowerCase().includes(q) ||
      (s.class_name && s.class_name.toLowerCase().includes(q));

    let matchStatus = true;
    if (statusFilter === "CHECKED_IN") {
      matchStatus = ["PRESENT", "LATE", "HALF_ABSENT"].includes(s.status);
    } else if (statusFilter === "ABSENT") {
      matchStatus = s.status === "ABSENT";
    } else if (statusFilter === "UNIFORM_VIOLATION") {
      matchStatus = !s.has_uniform && ["PRESENT", "LATE", "HALF_ABSENT"].includes(s.status);
    } else if (statusFilter === "OVERRIDDEN") {
      matchStatus = s.is_manual_override;
    } else if (statusFilter !== "ALL") {
      matchStatus = s.status === statusFilter;
    }

    return matchSearch && matchStatus;
  });

  const formatTime = (isoString?: string | null) => {
    if (!isoString) return "--:--";
    try {
      return formatTimeVN(isoString);
    } catch {
      return isoString;
    }
  };

  const renderStatusBadge = (status: string) => {
    switch (status) {
      case "PRESENT":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 size={12} />
            Có mặt
          </span>
        );
      case "LATE":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            <Clock size={12} />
            Đi muộn
          </span>
        );
      case "HALF_ABSENT":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-sky-50 text-sky-700 border border-sky-200">
            <AlertTriangle size={12} />
            Nửa buổi
          </span>
        );
      case "EXCUSED":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-blue-50 text-blue-700 border border-blue-200">
            <FileCheck size={12} />
            Có phép
          </span>
        );
      case "ABSENT":
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-50 text-rose-700 border border-rose-200">
            <XCircle size={12} />
            Chưa đến / Vắng
          </span>
        );
    }
  };

  return (
    <RoleGuard allowedRoles={["TEACHER"]}>
      <div className="p-4 sm:p-6 max-w-7xl mx-auto space-y-5 sm:space-y-6">
        {/* Navigation & Header */}
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 pb-4 border-b border-slate-200">
          <div className="min-w-0 flex-1">
            <Link
              href="/teacher/classes"
              className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-slate-800 transition-colors mb-2"
            >
              <ArrowLeft size={14} />
              <span>Quay lại danh sách lớp học phần</span>
            </Link>

            <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
              <h1 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight break-words leading-tight min-w-0">
                {liveData ? `${liveData.class_code} - ${liveData.course_name}` : "Điểm danh trực tiếp"}
              </h1>
              <span className="inline-flex shrink-0 whitespace-nowrap items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                Live Room
              </span>
            </div>

            {/* Schedule details bar */}
            {liveData && (
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-slate-500 mt-2">
                <div className="flex items-center gap-1.5">
                  <Calendar size={14} className="text-slate-400" />
                  <span>
                    Ngày học:{" "}
                    <strong className="text-slate-700">
                      {liveData.study_date ? String(liveData.study_date) : "Hôm nay"}
                    </strong>
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <Clock size={14} className="text-slate-400" />
                  <span>
                    Ca học:{" "}
                    <strong className="font-mono tabular-nums text-slate-700">
                      {liveData.start_time || "--:--"} - {liveData.end_time || "--:--"}
                    </strong>
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <MapPin size={14} className="text-slate-400" />
                  <span>
                    Phòng học:{" "}
                    <strong className="font-mono text-slate-700">
                      {liveData.room_name || "Chưa xếp phòng"}
                    </strong>
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Controls: Auto-refresh & Refresh button */}
          <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto sm:justify-end shrink-0">
            <label className="flex flex-1 sm:flex-none items-center justify-center gap-2 px-3 py-1.5 rounded-md border border-slate-200 bg-white cursor-pointer shadow-xs text-xs font-medium text-slate-700 select-none whitespace-nowrap">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="rounded text-emerald-600 focus:ring-emerald-500 h-3.5 w-3.5"
              />
              <span className="flex items-center gap-1.5">
                <Radio
                  size={12}
                  className={autoRefresh ? "text-emerald-600 animate-pulse" : "text-slate-400"}
                />
                <span>Tự động cập nhật (5s)</span>
              </span>
            </label>

            <button
              onClick={() => refetchLive()}
              disabled={loading || refreshing}
              className="inline-flex flex-1 sm:flex-none items-center justify-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium text-slate-700 bg-white hover:bg-slate-50 border border-slate-200 shadow-xs transition-colors disabled:opacity-50 whitespace-nowrap"
              title="Làm mới dữ liệu"
            >
              <RefreshCw
                size={13}
                className={refreshing || loading ? "animate-spin text-slate-800" : ""}
              />
              <span>Cập nhật</span>
            </button>

            {liveData && !liveData.schedule_id ? (
              <span
                className="inline-flex flex-1 sm:flex-none items-center justify-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold text-white bg-slate-300 cursor-not-allowed whitespace-nowrap"
                title="Hôm nay lớp không có tiết — kiosk đang đóng"
              >
                <span>Mở Kiosk Face</span>
              </span>
            ) : (
              <Link
                href={`/teacher/classes/${classId}/kiosk`}
                className="inline-flex flex-1 sm:flex-none items-center justify-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 shadow-xs transition-colors whitespace-nowrap"
                title="Mở kiosk điểm danh khuôn mặt ở cửa lớp"
              >
                <span>Mở Kiosk Face</span>
              </Link>
            )}
          </div>
        </div>

        {/* Banner khi ngoài tiết: hôm nay lớp không có buổi học -> kiosk đóng */}
        {liveData && !liveData.schedule_id && (
          <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-700 text-sm flex items-center gap-2">
            <Calendar size={15} className="shrink-0" />
            <span>
              Hôm nay lớp không có tiết — điểm danh đang đóng. Kiosk khuôn mặt chỉ mở
              vào ngày có buổi học. Giáo viên vẫn sửa điểm tay được.
            </span>
          </div>
        )}

        {/* 4 KPI Cards */}
        {liveData && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* 1. Tổng sĩ số */}
            <div className="p-4 bg-white rounded-lg border border-slate-200 shadow-sm flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Tổng sĩ số
                </p>
                <p className="text-2xl font-bold font-mono tabular-nums text-slate-900 mt-1">
                  {liveData.total_students}
                </p>
                <p className="text-[11px] text-slate-400 mt-0.5">Sinh viên ghi danh</p>
              </div>
              <div className="w-10 h-10 rounded-md bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-600">
                <Users size={20} />
              </div>
            </div>

            {/* 2. Đã check-in */}
            <div className="p-4 bg-white rounded-lg border border-emerald-200 shadow-sm flex items-center justify-between bg-emerald-50/20">
              <div>
                <p className="text-xs font-semibold text-emerald-700 uppercase tracking-wider">
                  Đã check-in
                </p>
                <p className="text-2xl font-bold font-mono tabular-nums text-emerald-700 mt-1">
                  {liveData.checked_in_count}
                </p>
                <p className="text-[11px] text-emerald-600/80 mt-0.5">
                  {liveData.total_students > 0
                    ? `${Math.round((liveData.checked_in_count / liveData.total_students) * 100)}% có mặt tại lớp`
                    : "0%"}
                </p>
              </div>
              <div className="w-10 h-10 rounded-md bg-emerald-100 border border-emerald-200 flex items-center justify-center text-emerald-700">
                <CheckCircle2 size={20} />
              </div>
            </div>

            {/* 3. Chưa đến / Vắng */}
            <div className="p-4 bg-white rounded-lg border border-rose-200 shadow-sm flex items-center justify-between bg-rose-50/20">
              <div>
                <p className="text-xs font-semibold text-rose-700 uppercase tracking-wider">
                  Chưa đến / Vắng
                </p>
                <p className="text-2xl font-bold font-mono tabular-nums text-rose-700 mt-1">
                  {liveData.absent_count}
                </p>
                <p className="text-[11px] text-rose-600/80 mt-0.5">
                  Chưa điểm danh ca này
                </p>
              </div>
              <div className="w-10 h-10 rounded-md bg-rose-100 border border-rose-200 flex items-center justify-center text-rose-700">
                <XCircle size={20} />
              </div>
            </div>

            {/* 4. Vi phạm đồng phục */}
            <div className="p-4 bg-white rounded-lg border border-amber-200 shadow-sm flex items-center justify-between bg-amber-50/20">
              <div>
                <p className="text-xs font-semibold text-amber-700 uppercase tracking-wider">
                  Vi phạm đồng phục
                </p>
                <p className="text-2xl font-bold font-mono tabular-nums text-amber-700 mt-1">
                  {liveData.uniform_violation_count}
                </p>
                <p className="text-[11px] text-amber-600/80 mt-0.5">
                  AI phát hiện thiếu đồng phục
                </p>
              </div>
              <div className="w-10 h-10 rounded-md bg-amber-100 border border-amber-200 flex items-center justify-center text-amber-700">
                <AlertTriangle size={20} />
              </div>
            </div>
          </div>
        )}

        {/* Toolbar: Search and Filter Tabs */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between flex-wrap gap-2 sm:gap-3 p-3 bg-white rounded-lg border border-slate-200 shadow-sm">
          {/* Search box */}
          <SearchInput
            value={searchQuery}
            onChange={setSearchQuery}
            placeholder="Tìm theo MSSV, Họ tên..."
            ariaLabel="Tìm kiếm sinh viên điểm danh"
            className="w-full sm:w-auto flex-1 sm:max-w-xs"
          />

          {/* Quick Filter Buttons */}
          <div className="flex flex-wrap items-center gap-1.5">
            {[
              { id: "ALL", label: "Tất cả" },
              { id: "CHECKED_IN", label: "Đã đến lớp" },
              { id: "ABSENT", label: "Chưa đến" },
              { id: "UNIFORM_VIOLATION", label: "Lỗi đồng phục" },
              { id: "OVERRIDDEN", label: "Sửa thủ công" },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setStatusFilter(tab.id)}
                className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                  statusFilter === tab.id
                    ? "bg-slate-900 text-white shadow-xs"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="text-right text-[11px] text-slate-400 font-mono tabular-nums shrink-0">
            Lần cuối: {formatTime(lastUpdated.toISOString())}
          </div>
        </div>

        {/* Error message */}
        {error && (
          <div className="p-4 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-sm flex items-center justify-between">
            <span>{error}</span>
            <button
              onClick={() => refetchLive()}
              className="text-xs font-semibold underline hover:no-underline ml-4"
            >
              Thử lại
            </button>
          </div>
        )}

        {/* Loading state */}
        {loading && (
          <div className="p-12 text-center bg-white rounded-lg border border-slate-200">
            <div className="flex items-center justify-center gap-3 text-slate-500 text-sm">
              <span className="w-5 h-5 rounded-full border-2 border-slate-300 border-t-slate-800 animate-spin" />
              <span>Đang kết nối camera và tải danh sách sĩ số...</span>
            </div>
          </div>
        )}

        {/* Students Realtime Table */}
        {!loading && liveData && (
          <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                  <tr>
                    <th className="sticky left-0 bg-slate-50 z-20 px-4 py-3 w-12 text-center">STT</th>
                    <th className="sticky left-12 bg-slate-50 z-20 px-4 py-3">Mã SV</th>
                    <th className="px-4 py-3">Họ và tên</th>
                    <th className="px-4 py-3 hidden md:table-cell">Lớp SH</th>
                    <th className="px-4 py-3 text-center">Trạng thái</th>
                    <th className="px-4 py-3 text-center hidden md:table-cell">Nguồn</th>
                    <th className="px-4 py-3 text-right">Thao tác</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredStudents.length === 0 ? (
                    <tr>
                      <td
                        colSpan={7}
                        className="px-4 py-8 text-center text-xs text-slate-400"
                      >
                        Không có sinh viên nào khớp với bộ lọc hiện tại.
                      </td>
                    </tr>
                  ) : (
                    filteredStudents.map((st, idx) => (
                      <tr
                        key={st.student_id}
                        className={`hover:bg-slate-50/70 transition-colors ${
                          !st.has_uniform && ["PRESENT", "LATE"].includes(st.status)
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
                        <td className="px-4 py-3 text-center">
                          {renderStatusBadge(st.status)}
                        </td>
                        <td className="px-4 py-3 text-center hidden md:table-cell">
                          {st.is_manual_override ? (
                            <span
                              className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-indigo-50 text-indigo-700 border border-indigo-200"
                              title="Điểm danh được giảng viên chỉnh sửa thủ công"
                            >
                              <Edit3 size={10} />
                              GV sửa
                            </span>
                          ) : st.source === "face" ? (
                            <span
                              className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200"
                              title="Kiosk điểm danh khuôn mặt tự ghi nhận"
                            >
                              <ClipboardCheck size={10} />
                              Face
                            </span>
                          ) : st.attendance_id ? (
                            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-600">
                              <ClipboardCheck size={10} />
                              GV điểm danh
                            </span>
                          ) : (
                            <span className="text-slate-300 text-xs">--</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="inline-flex items-center gap-1.5">
                            <button
                              type="button"
                              onClick={() => handleOpenHistory(st)}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 shadow-2xs transition-colors"
                              title="Xem lịch sử điểm danh của sinh viên trong môn này"
                            >
                              <History size={12} />
                              <span>Lịch sử</span>
                            </button>
                            <button
                              type="button"
                              onClick={() => handleOpenOverride(st)}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium text-slate-700 bg-white hover:bg-slate-100 border border-slate-200 shadow-2xs transition-colors"
                            >
                              <Edit3 size={12} className="text-slate-500" />
                              <span>Sửa điểm</span>
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Manual Override Modal */}
        <ManualOverrideModal
          isOpen={isOverrideModalOpen}
          onClose={() => {
            setIsOverrideModalOpen(false);
            setOverrideTarget(null);
          }}
          onSuccess={() => {
            refetchLive();
          }}
          target={overrideTarget}
        />

        {/* Attendance History Modal */}
        <AttendanceHistoryModal
          isOpen={isHistoryModalOpen}
          onClose={() => {
            setIsHistoryModalOpen(false);
            setHistoryTarget(null);
          }}
          classId={classId}
          target={historyTarget}
        />
      </div>
    </RoleGuard>
  );
}
