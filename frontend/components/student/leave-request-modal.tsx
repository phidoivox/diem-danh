"use client";

import React, { useState, useEffect } from "react";
import { StudentSchedule, submitLeaveRequest } from "@/lib/api";
import { X, Upload, FileText, AlertCircle, CheckCircle2, Loader2 } from "lucide-react";

interface LeaveRequestModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
  schedules: StudentSchedule[];
  preselectedScheduleId?: number | null;
}

export function LeaveRequestModal({
  isOpen,
  onClose,
  onSuccess,
  schedules,
  preselectedScheduleId,
}: LeaveRequestModalProps) {
  const [scheduleId, setScheduleId] = useState<string>("");
  const [reason, setReason] = useState<string>("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      if (preselectedScheduleId) {
        setScheduleId(preselectedScheduleId.toString());
      } else if (schedules.length > 0 && !scheduleId) {
        setScheduleId(schedules[0].id.toString());
      }
      setError(null);
      setSuccessMsg(null);
    }
  }, [isOpen, preselectedScheduleId, schedules]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!scheduleId) {
      setError("Vui lòng chọn buổi học cần xin nghỉ.");
      return;
    }
    if (!reason.trim()) {
      setError("Vui lòng nhập lý do xin nghỉ phép.");
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const formData = new FormData();
      formData.append("schedule_id", scheduleId);
      formData.append("reason", reason.trim());
      if (file) {
        formData.append("proof_file", file);
      }

      await submitLeaveRequest(formData);

      setSuccessMsg("Nộp đơn xin nghỉ phép thành công. Giảng viên sẽ xem xét phê duyệt.");
      setReason("");
      setFile(null);

      setTimeout(() => {
        onSuccess?.();
        onClose();
      }, 1200);
    } catch (err: any) {
      setError(err?.message || "Đã xảy ra lỗi khi gửi đơn xin nghỉ phép.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-[1px]">
      <div className="relative w-full max-w-lg bg-white rounded-lg border border-slate-200 shadow-lg overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 bg-slate-50/50">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-700">
              <FileText size={16} />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-slate-900">
                Tạo đơn xin nghỉ phép
              </h3>
              <p className="text-xs text-slate-500">
                Gửi lý do vắng mặt đến giảng viên phụ trách học phần
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="text-slate-400 hover:text-slate-600 rounded p-1 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {error && (
            <div className="flex items-start gap-2.5 p-3 rounded-md bg-rose-50 border border-rose-200 text-rose-700 text-xs">
              <AlertCircle size={16} className="shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {successMsg && (
            <div className="flex items-start gap-2.5 p-3 rounded-md bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs">
              <CheckCircle2 size={16} className="shrink-0 mt-0.5" />
              <span>{successMsg}</span>
            </div>
          )}

          {/* Schedule Select */}
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">
              Chọn buổi học xin nghỉ <span className="text-rose-500">*</span>
            </label>
            <select
              value={scheduleId}
              onChange={(e) => setScheduleId(e.target.value)}
              disabled={loading || schedules.length === 0}
              className="w-full h-9 px-3 rounded-md border border-slate-200 bg-white text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-slate-900 focus:border-slate-900 font-mono"
            >
              {schedules.length === 0 ? (
                <option value="">Không có buổi học nào</option>
              ) : (
                schedules.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.course_name} ({s.class_code}) - {s.study_date} [{s.start_time.slice(0, 5)}-{s.end_time.slice(0, 5)}] ({s.room_name})
                  </option>
                ))
              )}
            </select>
          </div>

          {/* Reason Textarea */}
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">
              Lý do xin nghỉ <span className="text-rose-500">*</span>
            </label>
            <textarea
              rows={3}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="VD: Em bị sốt cao cần đi khám bệnh tại bệnh viện, em xin phép vắng buổi học..."
              disabled={loading}
              className="w-full px-3 py-2 rounded-md border border-slate-200 bg-white text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-900 focus:border-slate-900 resize-none"
            />
          </div>

          {/* Proof File (Optional) */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs font-medium text-slate-700">
                Minh chứng đính kèm
              </label>
              <span className="text-[11px] text-slate-400 italic">
                (Không bắt buộc)
              </span>
            </div>
            <div className="mt-1 flex justify-center px-4 pt-4 pb-4 border border-dashed border-slate-300 rounded-md bg-slate-50/50 hover:bg-slate-50 transition-colors relative">
              <div className="space-y-1 text-center">
                <Upload className="mx-auto h-7 w-7 text-slate-400" />
                <div className="text-xs text-slate-600">
                  <label
                    htmlFor="proof-upload"
                    className="relative cursor-pointer rounded font-medium text-slate-900 hover:underline"
                  >
                    <span>{file ? file.name : "Tải lên tài liệu minh chứng"}</span>
                    <input
                      id="proof-upload"
                      name="proof_file"
                      type="file"
                      accept="image/*,application/pdf"
                      onChange={(e) => {
                        if (e.target.files && e.target.files[0]) {
                          setFile(e.target.files[0]);
                        }
                      }}
                      className="sr-only"
                      disabled={loading}
                    />
                  </label>
                </div>
                <p className="text-[11px] text-slate-400">
                  {file
                    ? `${(file.size / 1024).toFixed(1)} KB`
                    : "Hỗ trợ ảnh chụp giấy khám bệnh, PDF (tối đa 10MB)"}
                </p>
              </div>
            </div>
            {file && (
              <div className="mt-1.5 flex items-center justify-between text-xs text-slate-600 bg-slate-100 px-2.5 py-1 rounded">
                <span className="truncate font-mono">{file.name}</span>
                <button
                  type="button"
                  onClick={() => setFile(null)}
                  disabled={loading}
                  className="text-slate-400 hover:text-rose-600 ml-2"
                >
                  <X size={14} />
                </button>
              </div>
            )}
          </div>

          {/* Footer Actions */}
          <div className="pt-2 flex items-center justify-end gap-2 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="h-8 px-3 rounded-md text-xs font-medium text-slate-600 hover:bg-slate-100 transition-colors"
            >
              Hủy bỏ
            </button>
            <button
              type="submit"
              disabled={loading || schedules.length === 0}
              className="h-8 px-4 rounded-md text-xs font-medium bg-slate-900 text-white hover:bg-slate-800 disabled:opacity-50 disabled:pointer-events-none transition-colors inline-flex items-center gap-1.5"
            >
              {loading && <Loader2 size={13} className="animate-spin" />}
              <span>{loading ? "Đang gửi đơn..." : "Gửi đơn nghỉ phép"}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
