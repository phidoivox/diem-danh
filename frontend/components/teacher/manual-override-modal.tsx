"use client";

import React, { useState, useEffect } from "react";
import { manualOverrideAttendance } from "@/lib/api";
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
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (target) {
      setSelectedStatus(target.currentStatus || "PRESENT");
      setNote(target.currentNote || "");
      setErrorMessage(null);
    }
  }, [target]);

  if (!isOpen || !target) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!target) return;

    try {
      setIsSubmitting(true);
      setErrorMessage(null);

      await manualOverrideAttendance(target.attendanceId || 0, {
        status: selectedStatus,
        note: note.trim(),
        schedule_id: target.scheduleId || undefined,
        student_id: target.studentId,
      });

      onSuccess();
      onClose();
    } catch (err: any) {
      setErrorMessage(err?.message || "Không thể cập nhật điểm danh.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-[2px]">
      <div className="relative w-full max-w-lg bg-white rounded-lg border border-slate-200 shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50/50">
          <div>
            <h3 className="text-base font-semibold text-slate-900">
              Sửa điểm danh thủ công
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
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

        {/* Student Info Card */}
        <div className="px-6 pt-4 pb-2">
          <div className="p-3 bg-slate-50 border border-slate-200 rounded-md">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-medium text-slate-900">
                  {target.studentName}
                </div>
                <div className="flex items-center gap-2 text-xs text-slate-500 mt-0.5">
                  <span className="font-mono tabular-nums text-slate-700 font-medium">
                    {target.studentCode}
                  </span>
                  {target.className && (
                    <>
                      <span>•</span>
                      <span>{target.className}</span>
                    </>
                  )}
                </div>
              </div>
              <div className="text-right">
                <span className="text-[11px] text-slate-500 block mb-0.5">
                  Hiện tại
                </span>
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-slate-200 text-slate-700">
                  {target.currentStatus}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="px-6 py-4 space-y-4">
          {errorMessage && (
            <div className="p-3 rounded-md bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-start gap-2">
              <AlertCircle size={15} className="mt-0.5 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Status Selection */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">
              Chọn trạng thái mới <span className="text-rose-500">*</span>
            </label>
            <div className="grid grid-cols-1 gap-2">
              {STATUS_OPTIONS.map((opt) => {
                const Icon = opt.icon;
                const isSelected = selectedStatus === opt.value;
                return (
                  <label
                    key={opt.value}
                    className={`flex items-center justify-between p-2.5 rounded-md border text-sm cursor-pointer transition-all ${
                      isSelected
                        ? opt.activeClass
                        : "border-slate-200 hover:border-slate-300 hover:bg-slate-50/50"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <input
                        type="radio"
                        name="override_status"
                        value={opt.value}
                        checked={isSelected}
                        onChange={() => setSelectedStatus(opt.value)}
                        className="text-slate-900 focus:ring-slate-400 h-4 w-4"
                      />
                      <div>
                        <div className="flex items-center gap-2">
                          <Icon size={14} className="text-slate-600" />
                          <span className="font-medium text-slate-900">
                            {opt.label}
                          </span>
                        </div>
                        <p className="text-xs text-slate-500 mt-0.5">
                          {opt.description}
                        </p>
                      </div>
                    </div>
                    <span
                      className={`px-2 py-0.5 rounded text-[11px] font-semibold border ${opt.badgeClass}`}
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
              placeholder="VD: Sinh viên vào muộn có lý do chính đáng, Camera nhận diện nhầm,..."
              rows={2}
              maxLength={250}
              className="w-full px-3 py-2 text-sm rounded-md border border-slate-200 bg-white text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400 focus:border-slate-400 transition-colors"
            />
            <div className="flex justify-between text-[11px] text-slate-400 mt-1">
              <span>Ghi chú sẽ được lưu vào lịch sử đối soát học vụ</span>
              <span className="font-mono tabular-nums">{note.length}/250</span>
            </div>
          </div>

          {/* Audit Callout */}
          <div className="p-3 rounded-md bg-slate-50 border border-slate-200 text-slate-600 text-xs flex items-start gap-2">
            <Info size={15} className="mt-0.5 shrink-0 text-slate-500" />
            <span className="leading-relaxed">
              Điểm danh sau khi can thiệp sẽ gắn cờ{" "}
              <strong className="text-slate-800">Sửa thủ công</strong>. Cron tính
              điểm chuyên cần tự động 23:59 sẽ bảo lưu trạng thái này và không ghi
              đè.
            </span>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-200">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-3.5 py-1.5 rounded-md text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 border border-transparent transition-colors disabled:opacity-50"
            >
              Hủy
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-md text-sm font-medium bg-slate-900 text-white hover:bg-slate-800 border border-slate-900 shadow-sm transition-colors disabled:opacity-50"
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
    </div>
  );
}
