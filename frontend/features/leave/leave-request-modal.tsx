"use client";

import React, { useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { StudentSchedule, submitLeaveRequest } from "@/features/shell";
import { leaveRequestSchema, type LeaveRequestFormValues } from "@/features/shell";
import { FileDropzone } from "@/features/shell";
import { X, FileText, AlertCircle, CheckCircle2, Loader2 } from "lucide-react";

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
  const [file, setFile] = React.useState<File | null>(null);
  const [successMsg, setSuccessMsg] = React.useState<string | null>(null);
  const queryClient = useQueryClient();

  const {
    register,
    handleSubmit,
    setValue,
    setError,
    reset,
    formState: { errors },
  } = useForm<LeaveRequestFormValues>({
    resolver: zodResolver(leaveRequestSchema),
    defaultValues: { schedule_id: preselectedScheduleId ?? undefined, reason: "" },
  });

  const submitMutation = useMutation({
    mutationFn: (formData: FormData) => submitLeaveRequest(formData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["student-leaves"] });
      queryClient.invalidateQueries({ queryKey: ["student-schedule"] });
    },
  });
  const isSubmitting = submitMutation.isPending;

  useEffect(() => {
    if (isOpen) {
      if (preselectedScheduleId) {
        setValue("schedule_id", preselectedScheduleId);
      } else if (schedules.length > 0) {
        setValue("schedule_id", schedules[0].id);
      }
      setSuccessMsg(null);
    }
  }, [isOpen, preselectedScheduleId, schedules, setValue]);

  if (!isOpen) return null;

  const onSubmit = (values: LeaveRequestFormValues) => {
    const formData = new FormData();
    formData.append("schedule_id", String(values.schedule_id));
    formData.append("reason", values.reason);
    if (file) {
      formData.append("proof_file", file);
    }

    submitMutation.mutate(formData, {
      onSuccess: () => {
        setSuccessMsg("Nộp đơn xin nghỉ phép thành công. Giảng viên sẽ xem xét phê duyệt.");
        reset({ schedule_id: values.schedule_id, reason: "" });
        setFile(null);

        setTimeout(() => {
          onSuccess?.();
          onClose();
        }, 1200);
      },
      onError: (err: unknown) => {
        setError("root", {
          message:
            err instanceof Error
              ? err.message
              : "Đã xảy ra lỗi khi gửi đơn xin nghỉ phép.",
        });
      },
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-slate-900/50 backdrop-blur-[1px] overflow-y-auto">
      <div className="relative w-full max-w-lg max-h-[90vh] flex flex-col bg-white rounded-lg border border-slate-200 shadow-lg overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header — cố định */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 bg-slate-50/50 shrink-0">
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
            disabled={isSubmitting}
            className="text-slate-400 hover:text-slate-600 rounded p-1 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Form Body — chỉ vùng này cuộn, footer cố định đáy */}
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col min-h-0 flex-1 overflow-hidden">
          <div className="flex-1 overflow-y-auto overscroll-contain p-4 sm:p-5 space-y-4">
          {errors.root && (
            <div className="flex items-start gap-2.5 p-3 rounded-md bg-rose-50 border border-rose-200 text-rose-700 text-xs">
              <AlertCircle size={16} className="shrink-0 mt-0.5" />
              <span>{errors.root.message}</span>
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
              {...register("schedule_id", { valueAsNumber: true })}
              disabled={isSubmitting || schedules.length === 0}
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
            {errors.schedule_id && (
              <p className="mt-1 text-[11px] text-rose-600">{errors.schedule_id.message}</p>
            )}
          </div>

          {/* Reason Textarea */}
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">
              Lý do xin nghỉ <span className="text-rose-500">*</span>
            </label>
            <textarea
              rows={3}
              {...register("reason")}
              placeholder="VD: Em bị sốt cao cần đi khám bệnh tại bệnh viện, em xin phép vắng buổi học..."
              disabled={isSubmitting}
              className="w-full px-3 py-2 rounded-md border border-slate-200 bg-white text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-900 focus:border-slate-900 resize-none"
            />
            {errors.reason && (
              <p className="mt-1 text-[11px] text-rose-600">{errors.reason.message}</p>
            )}
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
            <FileDropzone value={file} onChange={setFile} />
          </div>

          </div>

          {/* Footer Actions — cố định */}
          <div className="px-4 sm:px-5 py-3 flex flex-col-reverse sm:flex-row sm:items-center sm:justify-end flex-wrap gap-2 border-t border-slate-200 bg-slate-50/50 shrink-0">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="w-full sm:w-auto inline-flex justify-center items-center min-h-[36px] h-8 px-3 rounded-md text-xs font-medium text-slate-600 hover:bg-slate-100 transition-colors"
            >
              Hủy bỏ
            </button>
            <button
              type="submit"
              disabled={isSubmitting || schedules.length === 0}
              className="w-full sm:w-auto min-h-[36px] h-8 px-4 rounded-md text-xs font-medium bg-slate-900 text-white hover:bg-slate-800 disabled:opacity-50 disabled:pointer-events-none transition-colors inline-flex items-center justify-center gap-1.5"
            >
              {isSubmitting && <Loader2 size={13} className="animate-spin" />}
              <span>{isSubmitting ? "Đang gửi đơn..." : "Gửi đơn nghỉ phép"}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
