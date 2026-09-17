"use client";

import React, { useState, useEffect } from "react";
import { AdminClass, createAdminSchedule } from "@/lib/api";
import { X, Calendar, Clock, AlertTriangle, Loader2 } from "lucide-react";

interface ScheduleFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  classes: AdminClass[];
  initialClassId?: number;
}

export function ScheduleFormModal({
  isOpen,
  onClose,
  onSuccess,
  classes,
  initialClassId,
}: ScheduleFormModalProps) {
  const [classId, setClassId] = useState<number | "">("");
  const [roomName, setRoomName] = useState("A1-301");
  const [studyDate, setStudyDate] = useState("");
  const [startTime, setStartTime] = useState("07:30");
  const [endTime, setEndTime] = useState("11:30");
  const [sessionOrder, setSessionOrder] = useState<number>(1);

  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (initialClassId) {
      setClassId(initialClassId);
    } else if (classes.length > 0 && !classId) {
      setClassId(classes[0].id);
    }
    // Set default date to tomorrow if not set
    if (!studyDate) {
      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);
      setStudyDate(tomorrow.toISOString().split("T")[0]);
    }
    setErrorMessage(null);
  }, [classes, initialClassId, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!classId) {
      setErrorMessage("Vui lòng chọn lớp học phần");
      return;
    }
    if (!roomName.trim()) {
      setErrorMessage("Vui lòng nhập tên phòng học");
      return;
    }
    if (!studyDate) {
      setErrorMessage("Vui lòng chọn ngày học");
      return;
    }
    if (!startTime || !endTime) {
      setErrorMessage("Vui lòng nhập đầy đủ giờ bắt đầu và giờ kết thúc");
      return;
    }
    if (startTime >= endTime) {
      setErrorMessage("Giờ bắt đầu phải sớm hơn giờ kết thúc buổi học");
      return;
    }

    setIsLoading(true);

    try {
      await createAdminSchedule({
        class_id: Number(classId),
        room_name: roomName.trim().toUpperCase(),
        study_date: studyDate,
        start_time: startTime.length === 5 ? `${startTime}:00` : startTime,
        end_time: endTime.length === 5 ? `${endTime}:00` : endTime,
        session_order: Number(sessionOrder) || 1,
      });

      onSuccess();
      onClose();
    } catch (err: any) {
      setErrorMessage(
        err.message || "Không thể tạo lịch học. Vui lòng kiểm tra lại thông tin và xung đột phòng."
      );
    } finally {
      setIsLoading(false);
    }
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
                Xếp lịch học phần mới
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
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {errorMessage && (
            <div className="flex items-start gap-2.5 p-3 text-xs bg-rose-50 border border-rose-200 text-rose-700 rounded-md">
              <AlertTriangle size={16} className="shrink-0 text-rose-500 mt-0.5" />
              <div>
                <p className="font-semibold">Lỗi xếp lịch học:</p>
                <p className="mt-0.5">{errorMessage}</p>
              </div>
            </div>
          )}

          {/* Class Select */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Lớp học phần <span className="text-rose-500">*</span>
            </label>
            <select
              value={classId}
              onChange={(e) => setClassId(Number(e.target.value))}
              className="w-full px-3 py-2 text-xs rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900 focus:border-slate-900"
            >
              <option value="">-- Chọn lớp học phần --</option>
              {classes.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.class_code} - {c.course_name} (GV: {c.teacher_name})
                </option>
              ))}
            </select>
          </div>

          {/* Room Name & Session Order */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Phòng học <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                value={roomName}
                onChange={(e) => setRoomName(e.target.value)}
                placeholder="A1-301, LAB-AI"
                className="w-full px-3 py-2 text-xs font-mono rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900 focus:border-slate-900 uppercase"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Thứ tự buổi học <span className="text-rose-500">*</span>
              </label>
              <input
                type="number"
                min={1}
                max={30}
                value={sessionOrder}
                onChange={(e) => setSessionOrder(parseInt(e.target.value) || 1)}
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
                value={studyDate}
                onChange={(e) => setStudyDate(e.target.value)}
                className="w-full px-3 py-2 text-xs font-mono rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900 focus:border-slate-900"
              />
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
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
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
                value={endTime}
                onChange={(e) => setEndTime(e.target.value)}
                className="w-full px-3 py-2 text-xs font-mono rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900 focus:border-slate-900"
              />
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
                    setStartTime(slot.start);
                    setEndTime(slot.end);
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
              disabled={isLoading}
              className="px-4 py-2 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-md hover:bg-slate-50 transition-colors disabled:opacity-50 cursor-pointer"
            >
              Hủy bỏ
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="flex items-center gap-2 px-4 py-2 text-xs font-medium text-white bg-slate-900 hover:bg-slate-800 rounded-md transition-colors disabled:opacity-50 cursor-pointer"
            >
              {isLoading && <Loader2 size={14} className="animate-spin" />}
              Lưu lịch học
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
