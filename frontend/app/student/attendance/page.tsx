"use client";

import React, { useState, useEffect, useMemo } from "react";
import { RoleGuard } from "@/components/layout/role-guard";
import { getStudentAttendance, StudentAttendance } from "@/lib/api";
import {
  CheckSquare,
  Clock,
  Shirt,
  AlertCircle,
  Filter,
  RefreshCw,
  Search,
  CheckCircle2,
  Calendar,
  Percent,
} from "lucide-react";

export default function StudentAttendancePage() {
  const [attendances, setAttendances] = useState<StudentAttendance[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [courseFilter, setCourseFilter] = useState<string>("ALL");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [searchTerm, setSearchTerm] = useState<string>("");

  const fetchAttendance = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getStudentAttendance();
      setAttendances(data);
    } catch (err: any) {
      setError(err?.message || "Không thể tải lịch sử điểm danh.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAttendance();
  }, []);

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

    attendances.forEach((a) => {
      if (a.status === "PRESENT") present++;
      else if (a.status === "LATE") late++;
      else if (a.status === "EXCUSED") excused++;
      else if (a.status === "ABSENT" || a.status === "HALF_ABSENT") absent++;

      if (!a.has_uniform) uniformViolations++;
    });

    const attendanceRate =
      total > 0
        ? Math.round(((present + excused + late * 0.5) / total) * 100)
        : 100;

    return { total, present, late, excused, absent, uniformViolations, attendanceRate };
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
        const d = new Date(timeStr);
        return d.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
      }
      return timeStr.slice(0, 5);
    } catch {
      return timeStr;
    }
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
    <RoleGuard allowedRoles={["STUDENT", "ADMIN"]}>
      <div className="space-y-6">
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
            className="h-8 px-3 rounded-md text-xs font-medium border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 transition-colors inline-flex items-center gap-1.5 shadow-sm self-start sm:self-auto"
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
        <div className="p-3 bg-white rounded-lg border border-slate-200 shadow-sm flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            {/* Search */}
            <div className="relative w-44 sm:w-56">
              <Search size={14} className="absolute left-2.5 top-2.5 text-slate-400" />
              <input
                type="text"
                placeholder="Tìm môn, mã lớp, ngày..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full h-8 pl-8 pr-3 rounded-md border border-slate-200 text-xs text-slate-800 placeholder:text-slate-400 bg-white focus:outline-none focus:ring-1 focus:ring-slate-900"
              />
            </div>

            {/* Course Filter */}
            <select
              value={courseFilter}
              onChange={(e) => setCourseFilter(e.target.value)}
              className="h-8 px-2.5 rounded-md border border-slate-200 text-xs text-slate-700 bg-white focus:outline-none focus:ring-1 focus:ring-slate-900"
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
              className="h-8 px-2.5 rounded-md border border-slate-200 text-xs text-slate-700 bg-white focus:outline-none focus:ring-1 focus:ring-slate-900"
            >
              <option value="ALL">Tất cả trạng thái</option>
              <option value="PRESENT">Có mặt</option>
              <option value="LATE">Đi muộn</option>
              <option value="EXCUSED">Nghỉ có phép</option>
              <option value="ABSENT">Vắng mặt</option>
              <option value="HALF_ABSENT">Vắng nửa buổi</option>
            </select>
          </div>

          <div className="text-xs text-slate-500 font-mono">
            Hiển thị <span className="font-semibold text-slate-900">{filteredAttendances.length}</span> bản ghi
          </div>
        </div>

        {/* Table Content */}
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
                Các lượt điểm danh quét qua FaceID hoặc giáo viên điểm danh sẽ hiển thị tại đây.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50/75 border-b border-slate-200 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                  <tr>
                    <th className="px-4 py-3">Môn học & Mã lớp</th>
                    <th className="px-4 py-3">Ngày học</th>
                    <th className="px-4 py-3 font-mono">Check-in</th>
                    <th className="px-4 py-3 font-mono">Check-out</th>
                    <th className="px-4 py-3">Đồng phục</th>
                    <th className="px-4 py-3">Trạng thái</th>
                    <th className="px-4 py-3">Ghi chú</th>
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
                      <td className="px-4 py-3 font-mono tabular-nums">
                        {item.check_out_time ? (
                          <span className="text-slate-700 font-medium">
                            {formatTime(item.check_out_time)}
                          </span>
                        ) : (
                          <span className="text-slate-400">--:--</span>
                        )}
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

                      {/* Note */}
                      <td className="px-4 py-3 text-slate-500 max-w-xs truncate">
                        {item.note || "--"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </RoleGuard>
  );
}
