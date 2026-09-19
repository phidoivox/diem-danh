"use client";

import React, { useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AdminClass, AdminSchedule, createAdminSchedule, updateAdminSchedule } from "@/lib/api";
import { todayVN } from "@/lib/date";
import { scheduleFullSchema, type ScheduleFullFormValues } from "@/lib/validation";
import { X, Calendar, Clock, AlertTriangle, Loader2 } from "lucide-react";

interface ScheduleFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  classes: AdminClass[];
  initialClassId?: number;
  /** Truyền buổi học vào để mở ở chế độ sửa; không truyền = chế độ xếp mới. */
  initialSchedule?: AdminSchedule | null;
}

export function ScheduleFormModal({
  isOpen,
  onClose,
  onSuccess,
  classes,
  initialClassId,
  initialSchedule,
}: ScheduleFormModalProps) {
  const isEditMode = Boolean(initialSchedule);

  const {
    register,
    handleSubmit,
    setValue,
    setError,
    reset,
    formState: { errors },
  } = useForm<ScheduleFullFormValues>({
    resolver: zodResolver(scheduleFullSchema),
    defaultValues: {
      class_id: initialClassId ?? classes[0]?.id ?? 0,
      room_name: "A1-301",
      study_date: "",
      start_time: "07:30",
      end_time: "11:30",
      session_order: 1,
    },
  });

  const queryClient = useQueryClient();
  const saveScheduleMutation = useMutation({
    mutationFn: (payload: {
      class_id: number;
      room_name: string;
      study_date: string;
      start_time: string;
      end_time: string;
      session_order: number;
    }) =>
      isEditMode && initialSchedule
        ? updateAdminSchedule(initialSchedule.id, payload)
        : createAdminSchedule(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-schedules"] });
    },
  });
  const isSubmitting = saveScheduleMutation.isPending;

  useEffect(() => {
    if (!isOpen) return;
    if (initialSchedule) {
      // Chế độ sửa: nạp sẵn giá trị hiện tại (reset thay sync tay từng field).
      reset({
        class_id: initialSchedule.class_id,
        room_name: initialSchedule.room_name,
        study_date: initialSchedule.study_date,
        start_time: initialSchedule.start_time.slice(0, 5),
        end_time: initialSchedule.end_time.slice(0, 5),
        session_order: initialSchedule.session_order,
      });
    } else {
      reset({
        class_id: initialClassId ?? classes[0]?.id ?? 0,
        room_name: "A1-301",
        // todayVN (+1 ngày): Intl Asia/Ho_Chi_Minh, không lệch UTC như toISOString.
        study_date: todayVN(),
        start_time: "07:30",
        end_time: "11:30",
        session_order: 1,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [classes, initialClassId, initialSchedule, isOpen]);

  if (!isOpen) return null;

  const onSubmit = (values: ScheduleFullFormValues) => {
    const payload = {
      class_id: Number(values.class_id),
      room_name: values.room_name.toUpperCase(),
      study_date: values.study_date,
      start_time: values.start_time.length === 5 ? `${values.start_time}:00` : values.start_time,
      end_time: values.end_time.length === 5 ? `${values.end_time}:00` : values.end_time,
      session_order: Number(values.session_order) || 1,
    };
    saveScheduleMutation.mutate(payload, {
      onSuccess: () => {
        onSuccess();
        onClose();
      },
      onError: (err: unknown) => {
        setError("root", {
          message:
            err instanceof Error
              ? err.message
              : isEditMode
                ? "Không thể cập nhật lịch học. Vui lòng kiểm tra lại thông tin và xung đột phòng."
                : "Không thể tạo lịch học. Vui lòng kiểm tra lại thông tin và xung đột phòng.",
        });
      },
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
      <div className="relative w-full max-w-lg bg-white rounded-lg shadow-xl border border-slate-200 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50/50">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-indigo-50 border border-indigo-200 text-indigo-700 rounded-md">
              <Calendar size={18} />
            </div>
            <div>
              <h3 className="text-base font-semibold text-slate-900">
                {isEditMode ? "Cập nhật lịch học" : "Xếp lịch học phần mới"}
              </h3>
              <p className="text-xs text-slate-500">
                Phân bổ phòng học và thời gian ca học (chống trùng phòng)
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-600 rounded-md hover:bg-slate-100 transition-colors cursor-pointer"
          >
            <X size={18} />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit(onSubmit)} className="p-6 space-y-4">
          {errors.root && (
            <div className="flex items-start gap-2.5 p-3 text-xs bg-rose-50 border border-rose-200 text-rose-700 rounded-md">
              <AlertTriangle size={16} className="shrink-0 text-rose-500 mt-0.5" />
              <div>
                <p className="font-semibold">Lỗi xếp lịch học:</p>
                <p className="mt-0.5">{errors.root.message}</p>
              </div>
            </div>
          )}

          {/* Class Select */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Lớp học phần <span className="text-rose-500">*</span>
            </label>
            <select
              {...register("class_id", { valueAsNumber: true })}
              className="w-full px-3 py-2 text-xs rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900 focus:border-slate-900"
            >
              <option value={0}>-- Chọn lớp học phần --</option>
              {classes.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.class_code} - {c.course_name} (GV: {c.teacher_name})
                </option>
              ))}
            </select>
            {errors.class_id && (
              <p className="mt-1 text-[11px] text-rose-600">{errors.class_id.message}</p>
            )}
          </div>

          {/* Room Name & Session Order */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Phòng học <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                {...register("room_name")}
                placeholder="A1-301, LAB-AI"
                className="w-full px-3 py-2 text-xs font-mono rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900 focus:border-slate-900 uppercase"
              />
              {errors.room_name && (
                <p className="mt-1 text-[11px] text-rose-600">{errors.room_name.message}</p>
              )}
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Thứ tự buổi học <span className="text-rose-500">*</span>
              </label>
              <input
                type="number"
                min={1}
                max={30}
                {...register("session_order", { valueAsNumber: true })}
                className="w-full px-3 py-2 text-xs font-mono rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900 focus:border-slate-900"
              />
            </div>
          </div>

          {/* Study Date */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Ngày học <span className="text-rose-500">*</span>
            </label>
            <div className="relative">
              <input
                type="date"
                {...register("study_date")}
                className="w-full px-3 py-2 text-xs font-mono rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900 focus:border-slate-900"
              />
              {errors.study_date && (
                <p className="mt-1 text-[11px] text-rose-600">{errors.study_date.message}</p>
              )}
            </div>
          </div>

          {/* Start Time & End Time */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1 flex items-center gap-1">
                <Clock size={13} className="text-slate-500" />
                Giờ bắt đầu <span className="text-rose-500">*</span>
              </label>
              <input
                type="time"
                {...register("start_time")}
                className="w-full px-3 py-2 text-xs font-mono rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900 focus:border-slate-900"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1 flex items-center gap-1">
                <Clock size={13} className="text-slate-500" />
                Giờ kết thúc <span className="text-rose-500">*</span>
              </label>
              <input
                type="time"
                {...register("end_time")}
                className="w-full px-3 py-2 text-xs font-mono rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900 focus:border-slate-900"
              />
              {errors.end_time && (
                <p className="mt-1 text-[11px] text-rose-600">{errors.end_time.message}</p>
              )}
            </div>
          </div>

          {/* Quick Slot Presets */}
          <div>
            <span className="text-[11px] text-slate-500">Khung giờ phổ biến:</span>
            <div className="flex flex-wrap gap-1.5 mt-1">
              {[
                { label: "Sáng (07:30 - 11:30)", start: "07:30", end: "11:30" },
                { label: "Chiều (13:00 - 17:00)", start: "13:00", end: "17:00" },
                { label: "Tối (17:30 - 20:45)", start: "17:30", end: "20:45" },
              ].map((slot) => (
                <button
                  key={slot.label}
                  type="button"
                  onClick={() => {
                    setValue("start_time", slot.start);
                    setValue("end_time", slot.end);
                  }}
                  className="px-2 py-1 text-[11px] font-mono bg-slate-100 hover:bg-slate-200 text-slate-700 rounded transition-colors cursor-pointer"
                >
                  {slot.label}
                </button>
              ))}
            </div>
          </div>

          {/* Anti-collision notice */}
          <p className="text-[11px] text-slate-400">
            * Hệ thống tự động kiểm tra xung đột phòng học: Không thể xếp 2 lớp trùng phòng trong cùng một khoảng thời gian.
          </p>

          {/* Footer */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-200">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-4 py-2 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-md hover:bg-slate-50 transition-colors disabled:opacity-50 cursor-pointer"
            >
              Hủy bỏ
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex items-center gap-2 px-4 py-2 text-xs font-medium text-white bg-slate-900 hover:bg-slate-800 rounded-md transition-colors disabled:opacity-50 cursor-pointer"
            >
              {isSubmitting && <Loader2 size={14} className="animate-spin" />}
              {isEditMode ? "Lưu thay đổi" : "Lưu lịch học"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
