"use client";

import React, { useState, useEffect, useMemo } from "react";
import { RoleGuard } from "@/components/layout/role-guard";
import { getStudentSchedule, StudentSchedule } from "@/lib/api";
import { LeaveRequestModal } from "@/components/student/leave-request-modal";
import {
  Calendar as CalendarIcon,
  Clock,
  MapPin,
  User,
  BookOpen,
  Filter,
  RefreshCw,
  PlusCircle,
  FileText,
  CheckCircle2,
  CalendarDays,
} from "lucide-react";

export default function StudentSchedulePage() {
  const [schedules, setSchedules] = useState<StudentSchedule[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [selectedCourse, setSelectedCourse] = useState<string>("ALL");
  const [timeFilter, setTimeFilter] = useState<"ALL" | "UPCOMING" | "PAST">("ALL");

  // Modal state
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [preselectedScheduleId, setPreselectedScheduleId] = useState<number | null>(null);

  const fetchSchedule = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getStudentSchedule();
      setSchedules(data);
    } catch (err: any) {
      setError(err?.message || "Không thể tải thời khóa biểu.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSchedule();
  }, []);

  // Extract unique course names for filter
  const uniqueCourses = useMemo(() => {
    const courseMap = new Map<string, string>();
    schedules.forEach((s) => {
      if (s.course_name) {
        courseMap.set(s.course_name, s.course_name);
      }
    });
    return Array.from(courseMap.values());
  }, [schedules]);

  // Filtered schedules
  const filteredSchedules = useMemo(() => {
    const todayStr = new Date().toISOString().split("T")[0];
    return schedules.filter((s) => {
      if (selectedCourse !== "ALL" && s.course_name !== selectedCourse) {
        return false;
      }
      if (timeFilter === "UPCOMING" && s.study_date < todayStr) {
        return false;
      }
      if (timeFilter === "PAST" && s.study_date >= todayStr) {
        return false;
      }
      return true;
    });
  }, [schedules, selectedCourse, timeFilter]);

  const todayStr = new Date().toISOString().split("T")[0];
  const upcomingCount = schedules.filter((s) => s.study_date >= todayStr).length;

  const formatDate = (dateStr: string) => {
    try {
      const d = new Date(dateStr);
      const days = ["Chủ nhật", "Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7"];
      const dayOfWeek = days[d.getDay()];
      const dd = String(d.getDate()).padStart(2, "0");
      const mm = String(d.getMonth() + 1).padStart(2, "0");
      const yyyy = d.getFullYear();
      return `${dayOfWeek}, ${dd}/${mm}/${yyyy}`;
    } catch {
      return dateStr;
    }
  };

  const handleOpenLeaveModal = (scheduleId?: number) => {
    setPreselectedScheduleId(scheduleId || null);
    setIsModalOpen(true);
  };

  return (
    <RoleGuard allowedRoles={["STUDENT", "ADMIN"]}>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-200">
          <div>
            <h1 className="text-lg font-semibold text-slate-900 tracking-tight">
              Thời khóa biểu cá nhân
            </h1>
            <p className="text-xs text-slate-500 mt-0.5">
              Tra cứu ca học, phòng học và thời gian các học phần đang đăng ký
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={fetchSchedule}
              disabled={loading}
              className="h-8 px-3 rounded-md text-xs font-medium border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 transition-colors inline-flex items-center gap-1.5 shadow-sm"
              title="Tải lại lịch học"
            >
              <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
              <span>Làm mới</span>
            </button>
            <button
              onClick={() => handleOpenLeaveModal()}
              className="h-8 px-3 rounded-md text-xs font-medium bg-slate-900 text-white hover:bg-slate-800 transition-colors inline-flex items-center gap-1.5 shadow-sm"
            >
              <PlusCircle size={14} />
              <span>Nộp đơn xin nghỉ</span>
            </button>
          </div>
        </div>

        {/* Stats Strip */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="p-4 rounded-lg bg-white border border-slate-200 shadow-sm flex items-center justify-between">
            <div>
              <span className="text-[11px] font-medium uppercase tracking-wider text-slate-500">
                Tổng số ca học
              </span>
              <div className="text-xl font-semibold text-slate-900 font-mono tabular-nums mt-0.5">
                {schedules.length}
              </div>
            </div>
            <div className="w-8 h-8 rounded bg-slate-100 flex items-center justify-center text-slate-600">
              <CalendarDays size={16} />
            </div>
          </div>

          <div className="p-4 rounded-lg bg-white border border-slate-200 shadow-sm flex items-center justify-between">
            <div>
              <span className="text-[11px] font-medium uppercase tracking-wider text-slate-500">
                Ca học sắp tới
              </span>
              <div className="text-xl font-semibold text-emerald-700 font-mono tabular-nums mt-0.5">
                {upcomingCount}
              </div>
            </div>
            <div className="w-8 h-8 rounded bg-emerald-50 text-emerald-700 flex items-center justify-center">
              <Clock size={16} />
            </div>
          </div>

          <div className="p-4 rounded-lg bg-white border border-slate-200 shadow-sm flex items-center justify-between">
            <div>
              <span className="text-[11px] font-medium uppercase tracking-wider text-slate-500">
                Môn học đang theo
              </span>
              <div className="text-xl font-semibold text-slate-900 font-mono tabular-nums mt-0.5">
                {uniqueCourses.length}
              </div>
            </div>
            <div className="w-8 h-8 rounded bg-slate-100 flex items-center justify-center text-slate-600">
              <BookOpen size={16} />
            </div>
          </div>
        </div>

        {/* Filter Toolbar */}
        <div className="p-3 bg-white rounded-lg border border-slate-200 shadow-sm flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <Filter size={14} />
              <span>Lọc môn:</span>
            </div>
            <select
              value={selectedCourse}
              onChange={(e) => setSelectedCourse(e.target.value)}
              className="h-8 px-2.5 rounded-md border border-slate-200 text-xs text-slate-700 bg-white focus:outline-none focus:ring-1 focus:ring-slate-900"
            >
              <option value="ALL">Tất cả môn học ({uniqueCourses.length})</option>
              {uniqueCourses.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>

            <div className="h-4 w-px bg-slate-200 mx-1 hidden sm:block" />

            <div className="inline-flex rounded-md p-0.5 bg-slate-100 border border-slate-200">
              <button
                type="button"
                onClick={() => setTimeFilter("ALL")}
                className={`px-2.5 py-1 text-xs font-medium rounded ${
                  timeFilter === "ALL"
                    ? "bg-white text-slate-900 shadow-xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Tất cả ({schedules.length})
              </button>
              <button
                type="button"
                onClick={() => setTimeFilter("UPCOMING")}
                className={`px-2.5 py-1 text-xs font-medium rounded ${
                  timeFilter === "UPCOMING"
                    ? "bg-white text-slate-900 shadow-xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Sắp tới ({upcomingCount})
              </button>
              <button
                type="button"
                onClick={() => setTimeFilter("PAST")}
                className={`px-2.5 py-1 text-xs font-medium rounded ${
                  timeFilter === "PAST"
                    ? "bg-white text-slate-900 shadow-xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Đã qua ({schedules.length - upcomingCount})
              </button>
            </div>
          </div>

          <div className="text-xs text-slate-500 font-mono">
            Hiển thị <span className="font-semibold text-slate-900">{filteredSchedules.length}</span> ca học
          </div>
        </div>

        {/* Schedule List */}
        {loading ? (
          <div className="p-12 text-center bg-white border border-slate-200 rounded-lg shadow-sm">
            <RefreshCw size={24} className="animate-spin text-slate-400 mx-auto mb-2" />
            <p className="text-xs text-slate-500">Đang tải dữ liệu thời khóa biểu...</p>
          </div>
        ) : error ? (
          <div className="p-6 text-center bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-xs">
            {error}
          </div>
        ) : filteredSchedules.length === 0 ? (
          <div className="p-12 text-center bg-white border border-slate-200 rounded-lg shadow-sm">
            <CalendarIcon size={36} className="text-slate-300 mx-auto mb-2" />
            <h3 className="text-sm font-semibold text-slate-800">Không tìm thấy ca học nào</h3>
            <p className="text-xs text-slate-500 mt-1">
              Bạn không có lịch học nào phù hợp với bộ lọc hiện tại.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
            {filteredSchedules.map((s) => {
              const isPast = s.study_date < todayStr;
              const isToday = s.study_date === todayStr;

              return (
                <div
                  key={s.id}
                  className={`p-4 rounded-lg bg-white border transition-all shadow-xs flex flex-col justify-between ${
                    isToday
                      ? "border-emerald-300 ring-1 ring-emerald-300/40"
                      : "border-slate-200 hover:border-slate-300"
                  }`}
                >
                  <div>
                    {/* Top Row: Session Order & Date status */}
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <span className="text-[11px] font-medium font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200">
                        Buổi {s.session_order}
                      </span>
                      {isToday ? (
                        <span className="text-[11px] font-semibold px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 border border-emerald-200">
                          Hôm nay
                        </span>
                      ) : isPast ? (
                        <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-slate-100 text-slate-500">
                          Đã diễn ra
                        </span>
                      ) : (
                        <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-sky-50 text-sky-700 border border-sky-200">
                          Sắp diễn ra
                        </span>
                      )}
                    </div>

                    {/* Course Name & Class Code */}
                    <h3 className="text-sm font-semibold text-slate-900 leading-snug line-clamp-1">
                      {s.course_name}
                    </h3>
                    <div className="mt-0.5 text-xs text-slate-500 font-mono">
                      Mã lớp: <span className="text-slate-800 font-medium">{s.class_code}</span>
                    </div>

                    {/* Schedule Metadata */}
                    <div className="mt-3.5 space-y-2 border-t border-slate-100 pt-3 text-xs text-slate-600">
                      <div className="flex items-center gap-2">
                        <CalendarIcon size={14} className="text-slate-400 shrink-0" />
                        <span className="font-medium text-slate-800">{formatDate(s.study_date)}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Clock size={14} className="text-slate-400 shrink-0" />
                        <span className="font-mono tabular-nums text-slate-700">
                          {s.start_time.slice(0, 5)} - {s.end_time.slice(0, 5)}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <MapPin size={14} className="text-slate-400 shrink-0" />
                        <span className="font-medium text-slate-800">{s.room_name}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <User size={14} className="text-slate-400 shrink-0" />
                        <span className="text-slate-600 truncate">
                          {s.teacher_name || "Giảng viên bộ môn"}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Card Action */}
                  <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-end">
                    <button
                      type="button"
                      onClick={() => handleOpenLeaveModal(s.id)}
                      className="text-xs font-medium text-slate-700 hover:text-slate-900 inline-flex items-center gap-1 px-2.5 py-1 rounded hover:bg-slate-100 transition-colors"
                    >
                      <FileText size={13} />
                      <span>Xin nghỉ phép ca này</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Leave Request Modal */}
        <LeaveRequestModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          onSuccess={fetchSchedule}
          schedules={schedules}
          preselectedScheduleId={preselectedScheduleId}
        />
      </div>
    </RoleGuard>
  );
}
