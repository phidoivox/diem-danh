"use client";

import React, { useState, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { RoleGuard } from "@/features/shell";
import { formatDate, todayVN } from "@/features/shell";
import { getStudentSchedule, StudentSchedule } from "@/features/shell";
import { LeaveRequestModal } from "@/features/leave";
import {
  Calendar as CalendarIcon,
  CalendarCheck,
  ChevronLeft,
  ChevronRight,
  Printer,
  MapPin,
  User,
  Filter,
  RefreshCw,
  PlusCircle,
  FileText,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Helpers ngày (date-only YYYY-MM-DD, wall-clock VN — so sánh chuỗi là đủ)
// ---------------------------------------------------------------------------
function parseDateOnly(s: string): Date {
  return new Date(s + "T12:00:00");
}

function toDateOnly(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

function addDays(dateOnly: string, n: number): string {
  const d = parseDateOnly(dateOnly);
  d.setDate(d.getDate() + n);
  return toDateOnly(d);
}

/** Thứ 2 của tuần (T2–CN) chứa dateOnly. */
function getMonday(dateOnly: string): string {
  const d = parseDateOnly(dateOnly);
  const shift = (d.getDay() + 6) % 7; // Mon=0 … Sun=6
  d.setDate(d.getDate() - shift);
  return toDateOnly(d);
}

/** dd/MM/yyyy */
function fmtFull(dateOnly: string): string {
  try {
    return formatDate(parseDateOnly(dateOnly));
  } catch {
    return dateOnly;
  }
}

const WEEKDAY_LABELS = [
  "Thứ 2",
  "Thứ 3",
  "Thứ 4",
  "Thứ 5",
  "Thứ 6",
  "Thứ 7",
  "Chủ nhật",
];

// ---------------------------------------------------------------------------
// Ca học suy từ giờ bắt đầu (backend chỉ lưu start/end, không có tiết)
// Sáng: trước 12h · Chiều: 12h–17h · Tối: từ 17h
// ---------------------------------------------------------------------------
const SHIFTS = [
  { key: "morning", label: "Sáng" },
  { key: "afternoon", label: "Chiều" },
  { key: "evening", label: "Tối" },
] as const;

function shiftIndex(startTime: string): 0 | 1 | 2 {
  const h = parseInt(startTime.slice(0, 2), 10);
  if (Number.isNaN(h)) return 0;
  if (h < 12) return 0;
  if (h < 17) return 1;
  return 2;
}

/** Accent theo ca — chỉ dùng màu đã có trong palette của web. */
const SHIFT_STYLES = [
  {
    chip: "bg-sky-50 text-sky-700 border-sky-200",
    bar: "bg-sky-500",
    block: "bg-sky-50/60 border-sky-200",
  },
  {
    chip: "bg-amber-50 text-amber-700 border-amber-200",
    bar: "bg-amber-500",
    block: "bg-amber-50/60 border-amber-200",
  },
  {
    chip: "bg-slate-100 text-slate-600 border-slate-200",
    bar: "bg-slate-400",
    block: "bg-white border-slate-200",
  },
] as const;

type ViewType = "ALL" | "STUDY" | "EXAM";

// ---------------------------------------------------------------------------
// Block ca học trong ô bảng desktop — nền tint nhẹ + vạch accent theo ca,
// đúng palette của web (slate chủ đạo, sky/amber/slate cho 3 ca)
// ---------------------------------------------------------------------------
function StudyBlock({
  s,
  onLeave,
}: {
  s: StudentSchedule;
  onLeave: (scheduleId: number) => void;
}) {
  const st = SHIFT_STYLES[shiftIndex(s.start_time)];
  return (
    <div className={`rounded-md border ${st.block} flex overflow-hidden shadow-xs`}>
      <div className={`w-1 shrink-0 ${st.bar}`} />
      <div className="p-1.5 text-[11px] leading-snug text-slate-800 min-w-0 flex-1">
        <div className="font-semibold text-slate-900 line-clamp-2">{s.course_name}</div>
        <div className="font-mono mt-0.5 text-slate-500">{s.class_code}</div>
        <div className="mt-0.5 font-mono tabular-nums">
          Buổi {s.session_order} · {s.start_time.slice(0, 5)} - {s.end_time.slice(0, 5)}
        </div>
        <div>Phòng: {s.room_name}</div>
        <div className="truncate">GV: {s.teacher_name || "—"}</div>
        <button
          type="button"
          onClick={() => onLeave(s.id)}
          className="mt-1 inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-200/60 transition-colors"
        >
          <FileText size={11} />
          <span>Xin nghỉ</span>
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Thẻ ca học cho list mobile (gọn, có chip ca Sáng/Chiều/Tối)
// ---------------------------------------------------------------------------
function ClassCard({
  s,
  isPast,
  isToday,
  onLeave,
}: {
  s: StudentSchedule;
  isPast: boolean;
  isToday: boolean;
  onLeave: (scheduleId: number) => void;
}) {
  return (
    <div
      className={`rounded-md border bg-white p-2.5 shadow-xs flex flex-col gap-1.5 text-xs transition-colors ${
        isToday
          ? "border-emerald-300 ring-1 ring-emerald-300/40"
          : "border-slate-200 hover:border-slate-300"
      } ${isPast ? "opacity-70" : ""}`}
    >
      <div className="flex items-center justify-between gap-1">
        <span className="font-mono tabular-nums font-semibold text-slate-800">
          {s.start_time.slice(0, 5)} - {s.end_time.slice(0, 5)}
        </span>
        <span className="flex items-center gap-1">
          <span
            className={`text-[10px] px-1.5 py-px rounded border font-medium whitespace-nowrap ${SHIFT_STYLES[shiftIndex(s.start_time)].chip}`}
          >
            {SHIFTS[shiftIndex(s.start_time)].label}
          </span>
          <span className="font-mono text-[10px] px-1.5 py-px rounded bg-slate-100 border border-slate-200 text-slate-600 whitespace-nowrap">
            Buổi {s.session_order}
          </span>
        </span>
      </div>

      <div className="font-semibold text-slate-900 leading-snug line-clamp-2">
        {s.course_name}
      </div>
      <div className="text-[11px] text-slate-500 font-mono">
        Mã lớp: <span className="text-slate-700 font-medium">{s.class_code}</span>
      </div>
      <div className="flex items-center gap-1.5 text-[11px] text-slate-600">
        <MapPin size={12} className="text-slate-400 shrink-0" />
        <span className="font-medium text-slate-800 truncate">{s.room_name}</span>
      </div>
      <div className="flex items-center gap-1.5 text-[11px] text-slate-500">
        <User size={12} className="text-slate-400 shrink-0" />
        <span className="truncate">{s.teacher_name || "Giảng viên bộ môn"}</span>
      </div>

      <div className="pt-1.5 mt-0.5 border-t border-slate-100 flex items-center justify-end">
        <button
          type="button"
          onClick={() => onLeave(s.id)}
          className="font-medium text-slate-600 hover:text-slate-900 inline-flex items-center gap-1 px-2 py-1 rounded hover:bg-slate-100 transition-colors"
        >
          <FileText size={12} />
          <span>Xin nghỉ</span>
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function StudentSchedulePage() {
  const queryClient = useQueryClient();
  const scheduleQuery = useQuery({
    queryKey: ["student-schedule"],
    queryFn: getStudentSchedule,
  });
  const schedules: StudentSchedule[] = scheduleQuery.data ?? [];
  const loading = scheduleQuery.isPending;
  const error = scheduleQuery.isError
    ? scheduleQuery.error instanceof Error
      ? scheduleQuery.error.message
      : "Không thể tải thời khóa biểu."
    : null;

  const todayStr = todayVN();

  // Ngày neo: tuần đang xem = tuần (T2–CN) chứa ngày này.
  // Ô date + các nút Trở về/Tiếp/Hiện tại đều chỉnh ngày neo này.
  const [anchorDate, setAnchorDate] = useState<string>(() => todayVN());
  const [viewType, setViewType] = useState<ViewType>("STUDY");
  const [selectedCourse, setSelectedCourse] = useState<string>("ALL");

  // Modal xin nghỉ
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [preselectedScheduleId, setPreselectedScheduleId] = useState<number | null>(null);

  const fetchSchedule = () =>
    queryClient.invalidateQueries({ queryKey: ["student-schedule"] });

  // Các môn học cho dropdown lọc
  const uniqueCourses = useMemo(() => {
    const courseMap = new Map<string, string>();
    schedules.forEach((s) => {
      if (s.course_name) {
        courseMap.set(s.course_name, s.course_name);
      }
    });
    return Array.from(courseMap.values());
  }, [schedules]);

  // 7 ngày (T2–CN) của tuần đang xem
  const weekDays = useMemo(() => {
    const monday = getMonday(anchorDate);
    return Array.from({ length: 7 }, (_, i) => addDays(monday, i));
  }, [anchorDate]);

  // Lưới [ca][ngày] → danh sách ca học (đã lọc môn, xếp theo giờ bắt đầu)
  const grid = useMemo(() => {
    const g: StudentSchedule[][][] = SHIFTS.map(() => weekDays.map(() => []));
    schedules.forEach((s) => {
      if (selectedCourse !== "ALL" && s.course_name !== selectedCourse) return;
      // Backend chưa có lịch thi riêng (schedules chỉ có buổi học) nên
      // STUDY/ALL hiện cùng dữ liệu; EXAM rơi xuống nhánh empty-state
      // "Chưa có lịch thi" phía dưới thay vì grid rỗng khó hiểu.
      if (viewType === "EXAM") return;
      const col = weekDays.indexOf(s.study_date);
      if (col < 0) return;
      g[shiftIndex(s.start_time)][col].push(s);
    });
    g.forEach((row) =>
      row.forEach((cell) =>
        cell.sort((a, b) => a.start_time.localeCompare(b.start_time))
      )
    );
    return g;
  }, [schedules, weekDays, selectedCourse, viewType]);

  const weekTotal = useMemo(
    () => grid.flat(2).length,
    [grid]
  );

  const handleOpenLeaveModal = (scheduleId?: number) => {
    setPreselectedScheduleId(scheduleId || null);
    setIsModalOpen(true);
  };

  const radioCls =
    "inline-flex items-center gap-1.5 text-xs text-slate-600 cursor-pointer";

  return (
    <RoleGuard allowedRoles={["STUDENT"]}>
      <div className="space-y-4 max-w-7xl mx-auto">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-200">
          <div>
            <h1 className="text-lg font-semibold text-slate-900 tracking-tight">
              Lịch học, lịch thi theo tuần
            </h1>
            <p className="text-xs text-slate-500 mt-0.5">
              Ca Sáng (trước 12h) · Chiều (12h–17h) · Tối (từ 17h) — suy từ giờ bắt đầu
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

        {/* Toolbar kiểu portal: radio loại lịch + ô ngày + nút điều hướng */}
        <div className="p-3 bg-white rounded-lg border border-slate-200 shadow-sm flex flex-wrap items-center gap-x-4 gap-y-3">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <label className={radioCls}>
              <input
                type="radio"
                name="schedule-view"
                value="ALL"
                checked={viewType === "ALL"}
                onChange={() => setViewType("ALL")}
                className="accent-slate-900"
              />
              Tất cả
            </label>
            <label className={radioCls}>
              <input
                type="radio"
                name="schedule-view"
                value="STUDY"
                checked={viewType === "STUDY"}
                onChange={() => setViewType("STUDY")}
                className="accent-slate-900"
              />
              Lịch học
            </label>
            <label className={radioCls}>
              <input
                type="radio"
                name="schedule-view"
                value="EXAM"
                checked={viewType === "EXAM"}
                onChange={() => setViewType("EXAM")}
                className="accent-slate-900"
              />
              Lịch thi
            </label>
          </div>

          <input
            type="date"
            value={anchorDate}
            onChange={(e) => {
              if (e.target.value) setAnchorDate(e.target.value);
            }}
            className="h-8 px-2 rounded-md border border-slate-200 text-xs text-slate-700 bg-white focus:outline-none focus:ring-1 focus:ring-slate-900 font-mono w-full sm:w-auto"
            title="Chọn ngày để nhảy tới tuần chứa ngày đó"
          />

          <div className="flex flex-wrap items-center gap-1.5">
            <button
              type="button"
              onClick={() => setAnchorDate(todayVN())}
              className="h-8 px-2.5 rounded-md text-xs font-medium bg-slate-900 text-white hover:bg-slate-800 transition-colors inline-flex items-center gap-1 shadow-sm"
            >
              <CalendarCheck size={13} />
              <span>Hiện tại</span>
            </button>
            <button
              type="button"
              onClick={() => window.print()}
              className="h-8 px-2.5 rounded-md text-xs font-medium border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 transition-colors inline-flex items-center gap-1 shadow-sm"
            >
              <Printer size={13} />
              <span>In lịch</span>
            </button>
            <button
              type="button"
              onClick={() => setAnchorDate((a) => addDays(a, -7))}
              className="h-8 px-2.5 rounded-md text-xs font-medium border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 transition-colors inline-flex items-center gap-0.5 shadow-sm"
            >
              <ChevronLeft size={13} />
              <span>Trở về</span>
            </button>
            <button
              type="button"
              onClick={() => setAnchorDate((a) => addDays(a, 7))}
              className="h-8 px-2.5 rounded-md text-xs font-medium border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 transition-colors inline-flex items-center gap-0.5 shadow-sm"
            >
              <span>Tiếp</span>
              <ChevronRight size={13} />
            </button>
          </div>

          <div className="flex items-center gap-2 sm:ml-auto">
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <Filter size={14} />
              <span>Lọc môn:</span>
            </div>
            <select
              value={selectedCourse}
              onChange={(e) => setSelectedCourse(e.target.value)}
              className="h-8 px-2.5 rounded-md border border-slate-200 text-xs text-slate-700 bg-white focus:outline-none focus:ring-1 focus:ring-slate-900 w-full sm:w-auto sm:max-w-56"
            >
              <option value="ALL">Tất cả môn học ({uniqueCourses.length})</option>
              {uniqueCourses.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Content */}
        {loading ? (
          <div className="p-12 text-center bg-white border border-slate-200 rounded-lg shadow-sm">
            <RefreshCw size={24} className="animate-spin text-slate-400 mx-auto mb-2" />
            <p className="text-xs text-slate-500">Đang tải dữ liệu thời khóa biểu...</p>
          </div>
        ) : error ? (
          <div className="p-6 text-center bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-xs">
            {error}
          </div>
        ) : viewType === "EXAM" ? (
          <div className="p-12 text-center bg-white border border-slate-200 rounded-lg shadow-sm">
            <CalendarIcon size={36} className="text-slate-300 mx-auto mb-2" />
            <h3 className="text-sm font-semibold text-slate-800">Chưa có lịch thi</h3>
            <p className="text-xs text-slate-500 mt-1">
              Hệ thống hiện chỉ quản lý lịch học các lớp học phần — chưa có dữ liệu lịch thi.
            </p>
          </div>
        ) : (
          <>
            <div className="text-xs text-slate-500 font-mono">
              Tuần <span className="font-semibold text-slate-900">{fmtFull(weekDays[0])} – {fmtFull(weekDays[6])}</span>
              {" · "}
              <span className="font-semibold text-slate-900">{weekTotal}</span> ca học
            </div>

            {/* Desktop: bảng Ca × Thứ (kiểu portal trường) */}
            <div className="hidden lg:block bg-white border border-slate-300 rounded-lg shadow-sm overflow-x-auto">
              <table className="w-full min-w-[960px] border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-300">
                    <th className="w-20 px-2 py-3 text-slate-500 font-semibold border-r border-slate-200 bg-slate-50">
                      Ca học
                    </th>
                    {weekDays.map((d, i) => {
                      const isToday = d === todayStr;
                      return (
                        <th
                          key={d}
                          className={`px-2 py-2 border-r border-slate-200 last:border-r-0 ${
                            isToday ? "bg-emerald-50" : ""
                          }`}
                        >
                          <div className="text-slate-900 font-semibold">
                            {WEEKDAY_LABELS[i]}
                          </div>
                          <div
                            className={`font-mono tabular-nums mt-0.5 font-medium ${
                              isToday ? "text-emerald-700" : "text-slate-500"
                            }`}
                          >
                            {fmtFull(d)}
                          </div>
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {SHIFTS.map((shift, r) => (
                    <tr
                      key={shift.key}
                      className="border-b border-slate-200 last:border-b-0"
                    >
                      <td className="px-2 py-3 text-center font-semibold text-slate-500 bg-slate-100 border-r border-slate-200 align-top">
                        {shift.label}
                      </td>
                      {weekDays.map((d, c) => (
                        <td
                          key={d}
                          className={`p-1.5 border-r border-slate-200 last:border-r-0 align-top ${
                            d === todayStr ? "bg-emerald-50/50" : ""
                          }`}
                        >
                          <div className="space-y-1.5 min-h-[96px]">
                            {grid[r][c].map((s) => (
                              <StudyBlock
                                key={s.id}
                                s={s}
                                onLeave={handleOpenLeaveModal}
                              />
                            ))}
                          </div>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile/Tablet: nhóm xếp dọc theo từng ngày */}
            <div className="lg:hidden space-y-3">
              {weekTotal === 0 && (
                <div className="px-4 py-3 rounded-lg bg-white border border-dashed border-slate-300 text-xs text-slate-500 flex items-center gap-2">
                  <CalendarIcon size={15} className="text-slate-400 shrink-0" />
                  <span>
                    Tuần này chưa có ca học
                    {selectedCourse !== "ALL" ? ` cho môn “${selectedCourse}”` : ""} — thử
                    chuyển tuần hoặc đổi bộ lọc môn.
                  </span>
                </div>
              )}
              {weekDays.map((date, i) => {
                const list = [...grid[0][i], ...grid[1][i], ...grid[2][i]];
                const isToday = date === todayStr;
                const isPast = date < todayStr;
                return (
                  <section
                    key={date}
                    className={`rounded-lg border bg-white shadow-xs overflow-hidden ${
                      isToday
                        ? "border-emerald-300 ring-1 ring-emerald-300/40"
                        : "border-slate-200"
                    }`}
                  >
                    <header className="flex items-center justify-between px-3 py-2 border-b border-slate-100 bg-slate-50/70">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="text-xs font-semibold text-slate-900">
                          {WEEKDAY_LABELS[i]}
                        </span>
                        <span className="text-xs text-slate-500 font-mono tabular-nums">
                          {fmtFull(date)}
                        </span>
                        {isToday && (
                          <span className="text-[10px] font-semibold px-1.5 py-px rounded bg-emerald-600 text-white">
                            Hôm nay
                          </span>
                        )}
                        {isPast && !isToday && (
                          <span className="text-[10px] font-medium px-1.5 py-px rounded bg-slate-100 text-slate-500">
                            Đã qua
                          </span>
                        )}
                      </div>
                      <span
                        className={`text-[11px] font-mono px-2 py-0.5 rounded border font-medium whitespace-nowrap ${
                          list.length > 0
                            ? "bg-slate-900 text-white border-slate-900"
                            : "bg-slate-100 text-slate-400 border-slate-200"
                        }`}
                      >
                        {list.length} ca
                      </span>
                    </header>
                    <div className="p-2.5 space-y-2">
                      {list.length === 0 ? (
                        <p className="text-xs text-slate-400 text-center py-3">
                          Không có ca học
                        </p>
                      ) : (
                        list.map((s) => (
                          <ClassCard
                            key={s.id}
                            s={s}
                            isPast={isPast}
                            isToday={isToday}
                            onLeave={handleOpenLeaveModal}
                          />
                        ))
                      )}
                    </div>
                  </section>
                );
              })}
            </div>
          </>
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
