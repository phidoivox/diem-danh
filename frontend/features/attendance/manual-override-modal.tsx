"use client";

import React, { useState, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { manualOverrideAttendance } from "@/features/shell";
import {
  X,
  CheckCircle2,
  Clock,
  AlertCircle,
  XCircle,
  FileCheck,
  Info,
  Loader2,
} from "lucide-react";

export interface OverrideTarget {
  attendanceId: number | null;
  studentId: number;
  studentCode: string;
  studentName: string;
  className?: string;
  currentStatus: string;
  scheduleId?: number | null;
  currentNote?: string;
}

interface ManualOverrideModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  target: OverrideTarget | null;
}

const STATUS_OPTIONS = [
  {
    value: "PRESENT",
    label: "Có mặt",
    description: "Sinh viên có mặt đầy đủ trong lớp",
    icon: CheckCircle2,
    badgeClass: "bg-emerald-50 text-emerald-700 border-emerald-200",
    activeClass: "border-emerald-500 bg-emerald-50/50 ring-1 ring-emerald-500",
  },
  {
    value: "LATE",
    label: "Đi muộn",
    description: "Đến lớp sau thời gian cho phép",
    icon: Clock,
    badgeClass: "bg-amber-50 text-amber-700 border-amber-200",
    activeClass: "border-amber-500 bg-amber-50/50 ring-1 ring-amber-500",
  },
  {
    value: "HALF_ABSENT",
    label: "Vắng nửa buổi",
    description: "Rời lớp sớm hoặc vào quá muộn (tính 0.5 buổi vắng)",
    icon: AlertCircle,
    badgeClass: "bg-sky-50 text-sky-700 border-sky-200",
    activeClass: "border-sky-500 bg-sky-50/50 ring-1 ring-sky-500",
  },
  {
    value: "ABSENT",
    label: "Vắng không phép",
    description: "Không đến lớp và không có đơn xin nghỉ",
    icon: XCircle,
    badgeClass: "bg-rose-50 text-rose-700 border-rose-200",
    activeClass: "border-rose-500 bg-rose-50/50 ring-1 ring-rose-500",
  },
  {
    value: "EXCUSED",
    label: "Nghỉ có phép",
    description: "Đã có đơn nghỉ phép hoặc được giáo viên chấp thuận",
    icon: FileCheck,
    badgeClass: "bg-blue-50 text-blue-700 border-blue-200",
    activeClass: "border-blue-500 bg-blue-50/50 ring-1 ring-blue-500",
  },
];

export function ManualOverrideModal({
  isOpen,
  onClose,
  onSuccess,
  target,
}: ManualOverrideModalProps) {
  const [selectedStatus, setSelectedStatus] = useState<string>("PRESENT");
  const [note, setNote] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const overrideMutation = useMutation({
    mutationFn: (payload: {
      attendanceId: number;
      status: string;
      note: string;
      scheduleId?: number | null;
      studentId: number;
    }) =>
      manualOverrideAttendance(payload.attendanceId, {
        status: payload.status,
        note: payload.note,
        schedule_id: payload.scheduleId || undefined,
        student_id: payload.studentId,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["teacher-live"] });
      onSuccess();
      onClose();
    },
    onError: (err: unknown) => {
      setErrorMessage(
        err instanceof Error ? err.message : "Không thể cập nhật điểm danh."
      );
    },
  });
  const isSubmitting = overrideMutation.isPending;

  useEffect(() => {
    if (target) {
      setSelectedStatus(target.currentStatus || "PRESENT");
      setNote(target.currentNote || "");
      setErrorMessage(null);
    }
  }, [target]);

  if (!isOpen || !target) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!target) return;

    setErrorMessage(null);
    overrideMutation.mutate({
      attendanceId: target.attendanceId || 0,
      status: selectedStatus,
      note: note.trim(),
      scheduleId: target.scheduleId || undefined,
      studentId: target.studentId,
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-slate-900/50 backdrop-blur-[2px] overflow-y-auto">
      <form
        onSubmit={handleSubmit}
        className="relative w-full max-w-lg max-h-[90vh] flex flex-col bg-white rounded-xl border border-slate-200 shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150"
      >
        {/* Header - Fixed */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-200 bg-slate-50/70 shrink-0">
          <div>
            <h3 className="text-sm sm:text-base font-semibold text-slate-900">
              Sửa điểm danh thủ công
            </h3>
            <p className="text-xs text-slate-500">
              Cập nhật trạng thái điểm danh cho buổi học
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="p-1 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Scrollable Form Body */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-3.5">
          {/* Student Info Card */}
          <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg">
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <div className="text-sm font-semibold text-slate-900 truncate">
                  {target.studentName}
                </div>
                <div className="flex items-center gap-1.5 text-xs text-slate-500 mt-0.5">
                  <span className="font-mono tabular-nums text-slate-700 font-medium">
                    {target.studentCode}
                  </span>
                  {target.className && (
                    <>
                      <span>•</span>
                      <span className="truncate">{target.className}</span>
                    </>
                  )}
                </div>
              </div>
              <div className="text-right shrink-0">
                <span className="text-[10px] text-slate-500 block">
                  Hiện tại
                </span>
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-200 text-slate-700">
                  {target.currentStatus}
                </span>
              </div>
            </div>
          </div>

          {errorMessage && (
            <div className="p-2.5 rounded-md bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-start gap-2">
              <AlertCircle size={15} className="mt-0.5 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Status Selection */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              Chọn trạng thái mới <span className="text-rose-500">*</span>
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {STATUS_OPTIONS.map((opt, idx) => {
                const Icon = opt.icon;
                const isSelected = selectedStatus === opt.value;
                const isLastAndOdd =
                  idx === STATUS_OPTIONS.length - 1 &&
                  STATUS_OPTIONS.length % 2 !== 0;
                return (
                  <label
                    key={opt.value}
                    className={`relative flex items-center justify-between p-2 sm:p-2.5 rounded-lg border text-xs cursor-pointer transition-all ${
                      isLastAndOdd ? "sm:col-span-2" : ""
                    } ${
                      isSelected
                        ? opt.activeClass
                        : "border-slate-200 hover:border-slate-300 hover:bg-slate-50/60"
                    }`}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <input
                        type="radio"
                        name="override_status"
                        value={opt.value}
                        checked={isSelected}
                        onChange={() => setSelectedStatus(opt.value)}
                        className="text-slate-900 focus:ring-slate-400 h-3.5 w-3.5 shrink-0"
                      />
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5 font-medium text-slate-900">
                          <Icon size={14} className="shrink-0 text-slate-600" />
                          <span className="truncate">{opt.label}</span>
                        </div>
                        <p className="text-[11px] text-slate-500 truncate max-w-[180px] sm:max-w-none">
                          {opt.description}
                        </p>
                      </div>
                    </div>
                    <span
                      className={`shrink-0 ml-1.5 px-1.5 py-0.5 rounded text-[10px] font-semibold border ${opt.badgeClass}`}
                    >
                      {opt.value}
                    </span>
                  </label>
                );
              })}
            </div>
          </div>

          {/* Note Input */}
          <div>
            <label
              htmlFor="override-note"
              className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1"
            >
              Lý do / Ghi chú sửa điểm
            </label>
            <textarea
              id="override-note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="VD: Sinh viên vào muộn có lý do chính đáng, máy nhận diện nhầm,..."
              rows={2}
              maxLength={250}
              className="w-full px-3 py-1.5 text-xs sm:text-sm rounded-lg border border-slate-200 bg-white text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400 focus:border-slate-400 transition-colors resize-none"
            />
            <div className="flex justify-between text-[11px] text-slate-400 mt-0.5">
              <span>Lưu vào lịch sử đối soát học vụ</span>
              <span className="font-mono tabular-nums">{note.length}/250</span>
            </div>
          </div>

          {/* Audit Callout */}
          <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-slate-600 text-[11px] flex items-start gap-2">
            <Info size={14} className="mt-0.5 shrink-0 text-slate-500" />
            <span className="leading-relaxed">
              Điểm danh sau khi can thiệp sẽ gắn cờ{" "}
              <strong className="text-slate-800 font-semibold">
                Sửa thủ công
              </strong>
              . Cron chuyên cần tự động 23:59 sẽ bảo lưu trạng thái này và không
              ghi đè.
            </span>
          </div>
        </div>

        {/* Footer Action Buttons - Always Visible (Sticky Bottom) */}
        <div className="flex flex-col-reverse sm:flex-row sm:items-center sm:justify-end flex-wrap gap-2 px-4 sm:px-5 py-3 border-t border-slate-200 bg-slate-50/80 shrink-0">
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="w-full sm:w-auto inline-flex justify-center items-center px-3.5 py-1.5 min-h-[36px] rounded-lg text-xs sm:text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-200/60 border border-transparent transition-colors disabled:opacity-50"
          >
            Hủy
          </button>
          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-1.5 px-4 py-1.5 min-h-[36px] rounded-lg text-xs sm:text-sm font-medium bg-slate-900 text-white hover:bg-slate-800 border border-slate-900 shadow-sm transition-colors disabled:opacity-50"
          >
            {isSubmitting ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                <span>Đang lưu...</span>
              </>
            ) : (
              <span>Lưu thay đổi</span>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
