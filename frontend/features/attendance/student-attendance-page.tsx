"use client";

import React, { useState, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { RoleGuard } from "@/features/shell";
import { SearchInput } from "@/features/shell";
import { formatTime as formatTimeVN } from "@/features/shell";
import { getStudentAttendance, StudentAttendance } from "@/features/shell";
import { AuthedSnapshotImg } from "@/features/shell";
import {
  CheckSquare,
  Shirt,
  AlertCircle,
  RefreshCw,
  Calendar,
} from "lucide-react";

interface AttendanceCardProps {
  item: StudentAttendance;
  formatTime: (timeStr?: string | null) => string;
  renderPointDelta: (pointDelta?: number | null) => React.ReactNode;
  renderStatusBadge: (status: string) => React.ReactNode;
}

function AttendanceCard({
  item,
  formatTime,
  renderPointDelta,
  renderStatusBadge,
}: AttendanceCardProps) {
  const timeRange =
    item.start_time && item.end_time
      ? `${item.start_time.slice(0, 5)} - ${item.end_time.slice(0, 5)}`
      : "";

  return (
    <div className="p-3.5 bg-white rounded-lg border border-slate-200 shadow-xs space-y-3">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="space-y-1 min-w-0">
          <div className="font-semibold text-sm text-slate-900 leading-snug break-words">
            {item.course_name}
          </div>
          <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-slate-500 font-mono">
            <span className="bg-slate-100 px-1.5 py-0.5 rounded text-slate-700 font-medium">
              {item.class_code}
            </span>
            <span className="flex items-center gap-1">
              <Calendar size={12} className="text-slate-400" />
              <span>{item.study_date}</span>
            </span>
            {timeRange && (
              <>
                <span className="text-slate-300">·</span>
                <span>{timeRange}</span>
              </>
            )}
          </div>
        </div>
        <div className="shrink-0">{renderStatusBadge(item.status)}</div>
      </div>

      {/* Micro-grid 2 cột: Check-in / Check-out */}
      <div className="grid grid-cols-2 gap-2 p-2.5 bg-slate-50 rounded-md border border-slate-100 text-xs font-mono">
        <div>
          <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 block">
            Check-in
          </span>
          <div className="mt-0.5 font-medium tabular-nums">
            {item.check_in_time ? (
              <span className="text-emerald-700 font-medium">
                {formatTime(item.check_in_time)}
              </span>
            ) : (
              <span className="text-slate-400">--:--</span>
            )}
          </div>
        </div>
        <div>
          <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 block">
            Check-out
          </span>
          <div className="mt-0.5 font-medium tabular-nums">
            {item.check_out_time ? (
              <span className="text-slate-700 font-medium">
                {formatTime(item.check_out_time)}
              </span>
            ) : (
              <span className="text-slate-400">--:--</span>
            )}
          </div>
        </div>
      </div>

      {/* Footer / Thông tin bổ sung */}
      <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-slate-100 text-xs">
        {/* Uniform badge & Snapshots */}
        <div className="flex items-center gap-2">
          {item.has_uniform ? (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
              <Shirt size={12} />
              Đúng quy định
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-rose-50 text-rose-700 border border-rose-200">
              <AlertCircle size={12} />
              Vi phạm
            </span>
          )}

          {(item.check_in_snapshot_url || item.check_out_snapshot_url) && (
            <div className="flex items-center gap-1">
              {item.check_in_snapshot_url && (
                <AuthedSnapshotImg
                  src={item.check_in_snapshot_url}
                  alt="check-in"
                  className="w-7 h-7 rounded object-cover border border-emerald-200"
                  linkTitle="Ảnh check-in"
                />
              )}
              {item.check_out_snapshot_url && (
                <AuthedSnapshotImg
                  src={item.check_out_snapshot_url}
                  alt="check-out"
                  className="w-7 h-7 rounded object-cover border border-sky-200"
                  linkTitle="Ảnh check-out"
                />
              )}
            </div>
          )}
        </div>

        {/* Điểm bị trừ */}
        <div className="flex items-center gap-1.5 ml-auto">
          <span className="text-[11px] text-slate-500">Điểm:</span>
          {renderPointDelta(item.point_delta)}
        </div>
      </div>

      {/* Ghi chú nếu có */}
      {item.note && (
        <div className="text-xs text-slate-600 bg-slate-50/70 p-2 rounded border border-slate-100 italic">
          <span className="font-medium text-slate-500 not-italic mr-1">Ghi chú:</span>
          {item.note}
        </div>
      )}
    </div>
  );
}

export default function StudentAttendancePage() {
  const queryClient = useQueryClient();
  const attendanceQuery = useQuery({
    queryKey: ["student-attendance"],
    queryFn: getStudentAttendance,
  });
  const rawAttendances = attendanceQuery.data;
  const attendances: StudentAttendance[] = useMemo(
    () => rawAttendances ?? [],
    [rawAttendances]
  );
  const loading = attendanceQuery.isPending;
  const error = attendanceQuery.isError
    ? attendanceQuery.error instanceof Error
      ? attendanceQuery.error.message
      : "Không thể tải lịch sử điểm danh."
    : null;

  // Filters
  const [courseFilter, setCourseFilter] = useState<string>("ALL");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [searchTerm, setSearchTerm] = useState<string>("");

  const fetchAttendance = () =>
    queryClient.invalidateQueries({ queryKey: ["student-attendance"] });

  // Distinct courses
  const uniqueCourses = useMemo(() => {
    const map = new Map<string, string>();
    attendances.forEach((a) => {
      if (a.course_name) map.set(a.course_name, a.course_name);
    });
    return Array.from(map.values());
  }, [attendances]);

  // Statistics
  const stats = useMemo(() => {
    const total = attendances.length;
    let present = 0;
    let late = 0;
    let excused = 0;
    let absent = 0;
    let uniformViolations = 0;
    let totalDeducted = 0;

    attendances.forEach((a) => {
      if (a.status === "PRESENT") present++;
      else if (a.status === "LATE") late++;
      else if (a.status === "EXCUSED") excused++;
      else if (a.status === "ABSENT" || a.status === "HALF_ABSENT") absent++;

      if (!a.has_uniform) uniformViolations++;

      if (typeof a.point_delta === "number" && a.point_delta < 0) {
        totalDeducted += Math.abs(a.point_delta);
      }
    });

    const attendanceRate =
      total > 0
        ? Math.round(((present + excused + late * 0.5) / total) * 100)
        : 100;

    return { total, present, late, excused, absent, uniformViolations, attendanceRate, totalDeducted };
  }, [attendances]);

  // Filtered rows
  const filteredAttendances = useMemo(() => {
    return attendances.filter((a) => {
      if (courseFilter !== "ALL" && a.course_name !== courseFilter) {
        return false;
      }
      if (statusFilter !== "ALL" && a.status !== statusFilter) {
        return false;
      }
      if (searchTerm.trim()) {
        const query = searchTerm.toLowerCase();
        const matchCourse = a.course_name?.toLowerCase().includes(query);
        const matchCode = a.class_code?.toLowerCase().includes(query);
        const matchDate = a.study_date?.toLowerCase().includes(query);
        const matchNote = a.note?.toLowerCase().includes(query);
        if (!matchCourse && !matchCode && !matchDate && !matchNote) return false;
      }
      return true;
    });
  }, [attendances, courseFilter, statusFilter, searchTerm]);

  const formatTime = (timeStr?: string | null) => {
    if (!timeStr) return "--:--";
    try {
      if (timeStr.includes("T")) {
        return formatTimeVN(new Date(timeStr));
      }
      return timeStr.slice(0, 5);
    } catch {
      return timeStr;
    }
  };

  const renderPointDelta = (pointDelta?: number | null) => {
    if (pointDelta === undefined || pointDelta === null) {
      return <span className="text-slate-300">—</span>;
    }
    if (pointDelta > 0) {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold font-mono tabular-nums bg-emerald-50 text-emerald-700 border border-emerald-200 whitespace-nowrap">
          +{pointDelta}
        </span>
      );
    }
    if (pointDelta === 0) {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium font-mono tabular-nums bg-slate-100 text-slate-600 border border-slate-200 whitespace-nowrap">
          0
        </span>
      );
    }
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold font-mono tabular-nums bg-rose-50 text-rose-700 border border-rose-200 whitespace-nowrap">
        {pointDelta}
      </span>
    );
  };

  const renderStatusBadge = (status: string) => {
    switch (status) {
      case "PRESENT":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            Có mặt
          </span>
        );
      case "LATE":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-amber-50 text-amber-700 border border-amber-200">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
            Đi muộn
          </span>
        );
      case "EXCUSED":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-sky-50 text-sky-700 border border-sky-200">
            <span className="w-1.5 h-1.5 rounded-full bg-sky-500" />
            Nghỉ có phép
          </span>
        );
      case "HALF_ABSENT":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-orange-50 text-orange-700 border border-orange-200">
            <span className="w-1.5 h-1.5 rounded-full bg-orange-500" />
            Vắng nửa buổi
          </span>
        );
      case "ABSENT":
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-rose-50 text-rose-700 border border-rose-200">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />
            Vắng mặt
          </span>
        );
    }
  };

  return (
    <RoleGuard allowedRoles={["STUDENT"]}>
      <div className="space-y-4 sm:space-y-6 max-w-7xl mx-auto">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-200">
          <div>
            <h1 className="text-lg font-semibold text-slate-900 tracking-tight">
              Lịch sử điểm danh cá nhân
            </h1>
            <p className="text-xs text-slate-500 mt-0.5">
              Theo dõi giờ check-in, check-out, tác phong đồng phục và trạng thái chuyên cần
            </p>
          </div>
          <button
            onClick={fetchAttendance}
            disabled={loading}
            className="h-10 sm:h-8 px-3 rounded-md text-xs font-medium border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 transition-colors inline-flex items-center justify-center gap-1.5 shadow-sm self-start sm:self-auto"
          >
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
            <span>Làm mới</span>
          </button>
        </div>

        {/* Attendance Summary KPI Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          <div className="p-3.5 rounded-lg bg-white border border-slate-200 shadow-sm">
            <span className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
              Tổng số buổi
            </span>
            <div className="text-xl font-semibold text-slate-900 font-mono tabular-nums mt-0.5">
              {stats.total}
            </div>
          </div>

          <div className="p-3.5 rounded-lg bg-white border border-slate-200 shadow-sm">
            <span className="text-[11px] font-medium uppercase tracking-wider text-emerald-600">
              Có mặt
            </span>
            <div className="text-xl font-semibold text-emerald-700 font-mono tabular-nums mt-0.5">
              {stats.present}
            </div>
          </div>

          <div className="p-3.5 rounded-lg bg-white border border-slate-200 shadow-sm">
            <span className="text-[11px] font-medium uppercase tracking-wider text-amber-600">
              Đi muộn
            </span>
            <div className="text-xl font-semibold text-amber-700 font-mono tabular-nums mt-0.5">
              {stats.late}
            </div>
          </div>

          <div className="p-3.5 rounded-lg bg-white border border-slate-200 shadow-sm">
            <span className="text-[11px] font-medium uppercase tracking-wider text-sky-600">
              Nghỉ phép
            </span>
            <div className="text-xl font-semibold text-sky-700 font-mono tabular-nums mt-0.5">
              {stats.excused}
            </div>
          </div>

          <div className="p-3.5 rounded-lg bg-white border border-slate-200 shadow-sm">
            <span className="text-[11px] font-medium uppercase tracking-wider text-rose-600">
              Vắng mặt
            </span>
            <div className="text-xl font-semibold text-rose-700 font-mono tabular-nums mt-0.5">
              {stats.absent}
            </div>
          </div>

          <div className="p-3.5 rounded-lg bg-white border border-slate-200 shadow-sm">
            <span className="text-[11px] font-medium uppercase tracking-wider text-slate-500">
              Tỷ lệ chuyên cần
            </span>
            <div className="text-xl font-semibold text-slate-900 font-mono tabular-nums mt-0.5 flex items-center gap-0.5">
              <span>{stats.attendanceRate}</span>
              <span className="text-xs text-slate-500 font-normal">%</span>
            </div>
          </div>
        </div>

        {/* Filter Toolbar */}
        <div className="p-3 bg-white rounded-lg border border-slate-200 shadow-sm flex flex-col sm:flex-row sm:flex-wrap sm:items-center justify-between gap-2.5 sm:gap-3">
          <div className="flex flex-col sm:flex-row sm:flex-wrap items-stretch sm:items-center gap-2 sm:gap-3 w-full sm:w-auto">
            {/* Search */}
            <SearchInput
              value={searchTerm}
              onChange={setSearchTerm}
              placeholder="Tìm môn, mã lớp, ngày..."
              ariaLabel="Tìm kiếm lịch sử điểm danh"
              className="w-full sm:w-56"
            />

            {/* Course Filter */}
            <select
              value={courseFilter}
              onChange={(e) => setCourseFilter(e.target.value)}
              className="w-full sm:w-auto h-10 sm:h-8 px-2.5 rounded-md border border-slate-200 text-xs text-slate-700 bg-white focus:outline-none focus:ring-1 focus:ring-slate-900"
            >
              <option value="ALL">Tất cả môn học ({uniqueCourses.length})</option>
              {uniqueCourses.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>

            {/* Status Filter */}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full sm:w-auto h-10 sm:h-8 px-2.5 rounded-md border border-slate-200 text-xs text-slate-700 bg-white focus:outline-none focus:ring-1 focus:ring-slate-900"
            >
              <option value="ALL">Tất cả trạng thái</option>
              <option value="PRESENT">Có mặt</option>
              <option value="LATE">Đi muộn</option>
              <option value="EXCUSED">Nghỉ có phép</option>
              <option value="ABSENT">Vắng mặt</option>
              <option value="HALF_ABSENT">Vắng nửa buổi</option>
            </select>
          </div>

          <div className="text-xs text-slate-500 font-mono flex items-center justify-between sm:justify-start gap-2 pt-1.5 sm:pt-0 border-t sm:border-t-0 border-slate-100">
            <span>
              Hiển thị <span className="font-semibold text-slate-900">{filteredAttendances.length}</span> bản ghi
            </span>
            <span className="text-slate-300">·</span>
            <span>
              Tổng bị trừ{" "}
              <span className="font-semibold text-rose-700">-{stats.totalDeducted}</span>{" "}
              điểm
            </span>
          </div>
        </div>

        {/* Content Section: Dual-View */}
        <div className="bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden">
          {loading ? (
            <div className="p-12 text-center">
              <RefreshCw size={24} className="animate-spin text-slate-400 mx-auto mb-2" />
              <p className="text-xs text-slate-500">Đang tải lịch sử điểm danh...</p>
            </div>
          ) : error ? (
            <div className="p-6 text-center text-rose-700 bg-rose-50 text-xs">
              {error}
            </div>
          ) : filteredAttendances.length === 0 ? (
            <div className="p-12 text-center">
              <CheckSquare size={36} className="text-slate-300 mx-auto mb-2" />
              <h3 className="text-sm font-semibold text-slate-800">Chưa có dữ liệu điểm danh</h3>
              <p className="text-xs text-slate-500 mt-1">
                Các lượt điểm danh do giáo viên ghi nhận sẽ hiển thị tại đây.
              </p>
            </div>
          ) : (
            <>
              {/* Desktop Table View */}
              <div className="hidden md:block overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50/75 border-b border-slate-200 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                    <tr>
                      <th className="px-4 py-3">Môn học & Mã lớp</th>
                      <th className="px-4 py-3">Ngày học</th>
                      <th className="px-4 py-3 font-mono">Check-in</th>
                      <th className="px-4 py-3 font-mono hidden md:table-cell">Check-out</th>
                      <th className="px-4 py-3 hidden md:table-cell">Ảnh</th>
                      <th className="px-4 py-3">Đồng phục</th>
                      <th className="px-4 py-3">Trạng thái</th>
                      <th className="px-4 py-3 text-center whitespace-nowrap">Điểm bị trừ</th>
                      <th className="px-4 py-3 hidden md:table-cell">Ghi chú</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 text-slate-700">
                    {filteredAttendances.map((item) => (
                      <tr key={item.attendance_id} className="hover:bg-slate-50/70 transition-colors">
                        {/* Course & Class */}
                        <td className="px-4 py-3 font-medium text-slate-900">
                          <div className="font-semibold text-slate-900">{item.course_name}</div>
                          <div className="text-[11px] text-slate-500 font-mono mt-0.5">
                            {item.class_code}
                          </div>
                        </td>

                        {/* Study Date */}
                        <td className="px-4 py-3 font-mono tabular-nums text-slate-600">
                          <div className="flex items-center gap-1.5">
                            <Calendar size={13} className="text-slate-400" />
                            <span>{item.study_date}</span>
                          </div>
                          <div className="text-[11px] text-slate-400 mt-0.5">
                            {item.start_time.slice(0, 5)} - {item.end_time.slice(0, 5)}
                          </div>
                        </td>

                        {/* Check-in Time */}
                        <td className="px-4 py-3 font-mono tabular-nums">
                          {item.check_in_time ? (
                            <span className="text-emerald-700 font-medium">
                              {formatTime(item.check_in_time)}
                            </span>
                          ) : (
                            <span className="text-slate-400">--:--</span>
                          )}
                        </td>

                        {/* Check-out Time */}
                        <td className="px-4 py-3 font-mono tabular-nums hidden md:table-cell">
                          {item.check_out_time ? (
                            <span className="text-slate-700 font-medium">
                              {formatTime(item.check_out_time)}
                            </span>
                          ) : (
                            <span className="text-slate-400">--:--</span>
                          )}
                        </td>

                        {/* Snapshots check-in/out (thư mục local) */}
                        <td className="px-4 py-3 hidden md:table-cell">
                          <div className="flex items-center gap-1">
                            {item.check_in_snapshot_url ? (
                              <AuthedSnapshotImg
                                src={item.check_in_snapshot_url}
                                alt="check-in"
                                className="w-9 h-9 rounded object-cover border border-emerald-200"
                                linkTitle="Ảnh check-in"
                              />
                            ) : (
                              <span className="text-slate-300 text-xs">--</span>
                            )}
                            {item.check_out_snapshot_url ? (
                              <AuthedSnapshotImg
                                src={item.check_out_snapshot_url}
                                alt="check-out"
                                className="w-9 h-9 rounded object-cover border border-sky-200"
                                linkTitle="Ảnh check-out"
                              />
                            ) : null}
                          </div>
                        </td>

                        {/* Uniform */}
                        <td className="px-4 py-3">
                          {item.has_uniform ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                              <Shirt size={12} />
                              Đúng quy định
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-rose-50 text-rose-700 border border-rose-200">
                              <AlertCircle size={12} />
                              Vi phạm
                            </span>
                          )}
                        </td>

                        {/* Status */}
                        <td className="px-4 py-3">
                          {renderStatusBadge(item.status)}
                        </td>

                        {/* Điểm bị trừ */}
                        <td className="px-4 py-3 text-center">
                          {renderPointDelta(item.point_delta)}
                        </td>

                        {/* Note */}
                        <td className="px-4 py-3 text-slate-500 max-w-xs truncate hidden md:table-cell">
                          {item.note || "--"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Mobile Card Feed View */}
              <div className="md:hidden space-y-3 p-3">
                {filteredAttendances.map((item) => (
                  <AttendanceCard
                    key={item.attendance_id}
                    item={item}
                    formatTime={formatTime}
                    renderPointDelta={renderPointDelta}
                    renderStatusBadge={renderStatusBadge}
                  />
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </RoleGuard>
  );
}
