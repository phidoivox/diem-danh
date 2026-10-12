"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  getStudentAttendanceHistory,
  getAdminStudentAttendanceHistory,
} from "@/features/shell";
import { AuthedSnapshotImg } from "@/features/shell";
import { formatTime as formatTimeVN } from "@/features/shell";
import {
  X,
  History,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  FileCheck,
  RefreshCw,
  ShieldCheck,
  ShieldAlert,
} from "lucide-react";

export interface HistoryTarget {
  studentId: number;
  studentCode: string;
  studentName: string;
  className?: string;
}

interface AttendanceHistoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  classId: number | null;
  target: HistoryTarget | null;
  /** Admin dùng endpoint admin (teacher mặc định). */
  scope?: "teacher" | "admin";
}

function renderStatusBadge(status: string) {
  switch (status) {
    case "PRESENT":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold whitespace-nowrap bg-emerald-50 text-emerald-700 border border-emerald-200">
          <CheckCircle2 size={12} />
          Có mặt
        </span>
      );
    case "LATE":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold whitespace-nowrap bg-amber-50 text-amber-700 border border-amber-200">
          <Clock size={12} />
          Đi muộn
        </span>
      );
    case "HALF_ABSENT":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold whitespace-nowrap bg-sky-50 text-sky-700 border border-sky-200">
          <AlertTriangle size={12} />
          Nửa buổi
        </span>
      );
    case "EXCUSED":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold whitespace-nowrap bg-blue-50 text-blue-700 border border-blue-200">
          <FileCheck size={12} />
          Có phép
        </span>
      );
    case "ABSENT":
    default:
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold whitespace-nowrap bg-rose-50 text-rose-700 border border-rose-200">
          <XCircle size={12} />
          Vắng
        </span>
      );
  }
}

function formatTime(isoString?: string | null) {
  if (!isoString) return "--:--";
  try {
    return formatTimeVN(isoString);
  } catch {
    return isoString;
  }
}

function renderPointDelta(pointDelta?: number | null) {
  if (pointDelta === undefined || pointDelta === null) {
    return <span className="text-slate-300">—</span>;
  }
  if (pointDelta > 0) {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold font-mono tabular-nums whitespace-nowrap bg-emerald-50 text-emerald-700 border border-emerald-200">
        +{pointDelta}
      </span>
    );
  }
  if (pointDelta === 0) {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium font-mono tabular-nums whitespace-nowrap bg-slate-100 text-slate-600 border border-slate-200">
        0
      </span>
    );
  }
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold font-mono tabular-nums whitespace-nowrap bg-rose-50 text-rose-700 border border-rose-200">
      {pointDelta}
    </span>
  );
}

export function AttendanceHistoryModal({
  isOpen,
  onClose,
  classId,
  target,
  scope = "teacher",
}: AttendanceHistoryModalProps) {
  const historyQuery = useQuery({
    queryKey: [`${scope}-student-history`, classId, target?.studentId],
    queryFn: () =>
      scope === "admin"
        ? getAdminStudentAttendanceHistory(classId!, target!.studentId)
        : getStudentAttendanceHistory(classId!, target!.studentId),
    enabled: isOpen && !!classId && !!target,
  });
  const data = historyQuery.data ?? null;
  const loading = historyQuery.isPending;
  const error = historyQuery.isError
    ? historyQuery.error instanceof Error
      ? historyQuery.error.message
      : "Không thể tải lịch sử điểm danh."
    : null;

  if (!isOpen || !target) return null;

  const s = data?.summary;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-slate-900/50 backdrop-blur-[2px] overflow-y-auto">
      <div className="relative w-full max-w-4xl max-h-[90vh] flex flex-col bg-white rounded-xl border border-slate-200 shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-200 bg-slate-50/70 shrink-0">
          <div className="min-w-0">
            <h3 className="text-sm sm:text-base font-semibold text-slate-900 flex items-center gap-1.5">
              <History size={16} className="text-slate-500 shrink-0" />
              <span className="truncate">Lịch sử điểm danh</span>
            </h3>
            <p className="text-xs text-slate-500 truncate">
              {target.studentName}{" "}
              <span className="font-mono tabular-nums">{target.studentCode}</span>
              {data ? ` · ${data.class_code} - ${data.course_name}` : ""}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors shrink-0"
          >
            <X size={18} />
          </button>
        </div>

        {/* Summary */}
        {s && (
          <div className="flex flex-wrap items-center gap-1.5 px-5 py-2.5 border-b border-slate-100 text-xs shrink-0">
            <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 font-medium">
              Tổng <strong className="font-mono tabular-nums ml-1">{s.total_sessions}</strong>&nbsp;buổi
            </span>
            <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium">
              Có mặt <strong className="font-mono tabular-nums ml-1">{s.present}</strong>
            </span>
            <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200 font-medium">
              Muộn <strong className="font-mono tabular-nums ml-1">{s.late}</strong>
            </span>
            <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-sky-50 text-sky-700 border border-sky-200 font-medium">
              Nửa buổi <strong className="font-mono tabular-nums ml-1">{s.half_absent}</strong>
            </span>
            <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200 font-medium">
              Có phép <strong className="font-mono tabular-nums ml-1">{s.excused}</strong>
            </span>
            <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-rose-50 text-rose-700 border border-rose-200 font-medium">
              Vắng <strong className="font-mono tabular-nums ml-1">{s.absent}</strong>
            </span>
            {(s.total_deducted ?? 0) > 0 && (
              <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-rose-100 text-rose-800 border border-rose-300 font-semibold">
                Bị trừ <strong className="font-mono tabular-nums ml-1">-{s.total_deducted}</strong>&nbsp;điểm
              </span>
            )}
          </div>
        )}

        {/* Body */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="p-12 text-center">
              <RefreshCw size={24} className="animate-spin text-slate-400 mx-auto mb-2" />
              <p className="text-xs text-slate-500">Đang tải lịch sử điểm danh...</p>
            </div>
          ) : error ? (
            <div className="p-6 text-center text-rose-700 bg-rose-50 text-xs">
              {error}
            </div>
          ) : !data || data.items.length === 0 ? (
            <div className="p-12 text-center">
              <History size={36} className="text-slate-300 mx-auto mb-2" />
              <h3 className="text-sm font-semibold text-slate-800">Chưa có buổi học nào</h3>
              <p className="text-xs text-slate-500 mt-1">
                Lớp này chưa có lịch học nên chưa có lịch sử điểm danh.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto [scrollbar-width:thin]">
              <table className="w-full min-w-[720px] text-left text-xs">
                <thead className="bg-slate-50/75 border-b border-slate-200 text-[11px] font-semibold text-slate-500 uppercase tracking-wider sticky top-0">
                  <tr>
                    <th className="px-4 py-2.5 w-14 text-center whitespace-nowrap">STT</th>
                    <th className="px-4 py-2.5 whitespace-nowrap">Ngày học</th>
                    <th className="px-4 py-2.5 whitespace-nowrap">Giờ vào</th>
                    <th className="px-4 py-2.5 whitespace-nowrap">Giờ ra</th>
                    <th className="px-4 py-2.5 text-center whitespace-nowrap">Ảnh vào</th>
                    <th className="px-4 py-2.5 text-center whitespace-nowrap">Ảnh ra</th>
                    <th className="px-4 py-2.5 text-center whitespace-nowrap">Đồng phục</th>
                    <th className="px-4 py-2.5 text-center whitespace-nowrap">Trạng thái</th>
                    <th className="px-4 py-2.5 text-center whitespace-nowrap">Điểm</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {data.items.map((it, idx) => (
                    <tr key={it.schedule_id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="px-4 py-3 text-center">
                        <div className="font-mono tabular-nums font-semibold text-slate-900">
                          {idx + 1}
                        </div>
                        <div className="text-[10px] text-slate-400 font-mono tabular-nums whitespace-nowrap">
                          Buổi {it.session_order}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-mono tabular-nums font-medium text-slate-900 whitespace-nowrap">
                          {String(it.study_date)}
                        </div>
                        <div className="text-[11px] text-slate-400 font-mono tabular-nums whitespace-nowrap mt-0.5">
                          {it.start_time} - {it.end_time} · {it.room_name}
                        </div>
                      </td>
                      <td className="px-4 py-3 font-mono tabular-nums whitespace-nowrap">
                        {it.check_in_time ? (
                          <span className="text-emerald-700 font-medium">
                            {formatTime(it.check_in_time)}
                          </span>
                        ) : (
                          <span className="text-slate-300">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 font-mono tabular-nums whitespace-nowrap">
                        {it.check_out_time ? (
                          <span className="text-slate-700 font-medium">
                            {formatTime(it.check_out_time)}
                          </span>
                        ) : (
                          <span className="text-slate-300">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-center">
                        {it.check_in_snapshot_url ? (
                          <AuthedSnapshotImg
                            src={it.check_in_snapshot_url}
                            alt="check-in"
                            className="w-10 h-10 rounded-md object-cover border border-emerald-200 shadow-xs"
                            linkTitle="Ảnh check-in"
                          />
                        ) : (
                          <span className="text-slate-300">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-center">
                        {it.check_out_snapshot_url ? (
                          <AuthedSnapshotImg
                            src={it.check_out_snapshot_url}
                            alt="check-out"
                            className="w-10 h-10 rounded-md object-cover border border-sky-200 shadow-xs"
                            linkTitle="Ảnh check-out"
                          />
                        ) : (
                          <span className="text-slate-300">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-center">
                        {it.status === "ABSENT" || !it.attendance_id ? (
                          <span className="text-slate-300">—</span>
                        ) : it.has_uniform ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium whitespace-nowrap bg-emerald-50 text-emerald-700 border border-emerald-200">
                            <ShieldCheck size={12} />
                            Đúng chuẩn
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold whitespace-nowrap bg-rose-50 text-rose-700 border border-rose-200">
                            <ShieldAlert size={12} />
                            Vi phạm
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-center">
                        {renderStatusBadge(it.status)}
                      </td>
                      <td className="px-4 py-3 text-center">
                        {renderPointDelta(it.point_delta)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex flex-col-reverse sm:flex-row sm:items-center sm:justify-end flex-wrap gap-2 px-4 sm:px-5 py-3 border-t border-slate-200 bg-slate-50/80 shrink-0">
          <button
            type="button"
            onClick={onClose}
            className="w-full sm:w-auto inline-flex justify-center px-3.5 py-1.5 min-h-[36px] items-center rounded-lg text-xs sm:text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-200/60 border border-transparent transition-colors"
          >
            Đóng
          </button>
        </div>
      </div>
    </div>
  );
}
