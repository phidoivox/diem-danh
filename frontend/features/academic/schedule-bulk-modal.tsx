"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AdminClass,
  AdminScheduleBulkResponse,
  createAdminSchedulesBulk,
  todayVN,
} from "@/features/shell";
import { X, Zap, Clock, AlertTriangle, Loader2, CheckCircle2 } from "lucide-react";

const WEEKDAY_LABELS = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"];
const FULL_WEEKDAY = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"];

interface ScheduleBulkModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (info: { created: number; skipped: number }) => void;
  classes: AdminClass[];
  initialClassId?: number;
}

function toISO(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
}

function computePreview(startDate: string, weekdays: number[], total: number): { date: string; weekday: number }[] {
  if (!startDate || weekdays.length === 0) return [];
  const cur = new Date(startDate + "T00:00:00");
  if (Number.isNaN(cur.getTime())) return [];
  const set = new Set(weekdays);
  const out: { date: string; weekday: number }[] = [];
  const d = new Date(cur);
  let guard = 0;
  const want = Math.min(Math.max(total, 0), 60);
  while (out.length < want && guard < 500) {
    guard += 1;
    const w = (d.getDay() + 6) % 7;
    if (set.has(w)) out.push({ date: toISO(d), weekday: w });
    d.setDate(d.getDate() + 1);
  }
  return out;
}

export function ScheduleBulkModal({
  isOpen,
  onClose,
  onSuccess,
  classes,
  initialClassId,
}: ScheduleBulkModalProps) {
  const [classId, setClassId] = useState<number>(initialClassId ?? 0);
  const [roomName, setRoomName] = useState("A1-301");
  const [startDate, setStartDate] = useState(todayVN());
  const [startTime, setStartTime] = useState("07:30");
  const [endTime, setEndTime] = useState("11:30");
  const [weekdays, setWeekdays] = useState<number[]>([0, 3]);
  const [totalSessions, setTotalSessions] = useState(15);
  const [formError, setFormError] = useState<string | null>(null);
  const [result, setResult] = useState<AdminScheduleBulkResponse | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setClassId(initialClassId ?? classes[0]?.id ?? 0);
    setRoomName("A1-301");
    setStartDate(todayVN());
    setStartTime("07:30");
    setEndTime("11:30");
    setWeekdays([0, 3]);
    const cls = classes.find((c) => c.id === (initialClassId ?? classes[0]?.id));
    setTotalSessions(cls && cls.total_sessions > 0 ? cls.total_sessions : 15);
    setFormError(null);
    setResult(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  const queryClient = useQueryClient();
  const bulkMutation = useMutation({
    mutationFn: createAdminSchedulesBulk,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["admin-schedules"] });
      setResult(data);
      onSuccess({ created: data.created.length, skipped: data.skipped.length });
    },
  });
  const isSubmitting = bulkMutation.isPending;

  const preview = useMemo(
    () => computePreview(startDate, weekdays, totalSessions),
    [startDate, weekdays, totalSessions]
  );

  if (!isOpen) return null;

  const toggleWeekday = (w: number) =>
    setWeekdays((prev) => (prev.includes(w) ? prev.filter((x) => x !== w) : [...prev, w].sort()));

  const handleSubmit = () => {
    setFormError(null);
    if (!classId) return setFormError("Vui lòng chọn lớp học phần.");
    if (!roomName.trim()) return setFormError("Vui lòng nhập phòng học.");
    if (!startDate) return setFormError("Vui lòng chọn ngày bắt đầu.");
    if (weekdays.length === 0) return setFormError("Chọn ít nhất 1 buổi trong tuần.");
    if (startTime >= endTime) return setFormError("Giờ bắt đầu phải nhỏ hơn giờ kết thúc.");
    if (totalSessions < 1 || totalSessions > 60) return setFormError("Số buổi từ 1 đến 60.");
    bulkMutation.mutate({
      class_id: classId,
      room_name: roomName.trim().toUpperCase(),
      start_date: startDate,
      start_time: startTime.length === 5 ? startTime + ":00" : startTime,
      end_time: endTime.length === 5 ? endTime + ":00" : endTime,
      weekdays: [...weekdays].sort(),
      total_sessions: totalSessions,
    });
  };

  const serverError = bulkMutation.error instanceof Error ? bulkMutation.error.message : null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-3 sm:p-4 overflow-y-auto">
      <div className="relative w-full max-w-2xl max-h-[90vh] flex flex-col bg-white rounded-lg shadow-xl border border-slate-200 overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50/50 shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-amber-50 border border-amber-200 text-amber-700 rounded-md">
              <Zap size={18} />
            </div>
            <div>
              <h3 className="text-base font-semibold text-slate-900">Sinh lịch hàng loạt theo tuần</h3>
              <p className="text-xs text-slate-500">Chọn thứ + giờ + phòng, hệ tự sinh đủ số buổi</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 text-slate-400 hover:text-slate-600 rounded-md hover:bg-slate-100 transition-colors cursor-pointer">
            <X size={18} />
          </button>
        </div>

        {result ? (
          <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-3">
            <div className="flex items-start gap-2.5 p-3 text-xs bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-md">
              <CheckCircle2 size={16} className="shrink-0 mt-0.5" />
              <span>Đã tạo {result.created.length} buổi học, bỏ qua {result.skipped.length} ngày trùng.</span>
            </div>
            {result.skipped.length > 0 && (
              <div className="rounded-md border border-amber-200 bg-amber-50/60 overflow-hidden">
                <p className="px-3 py-2 text-[11px] font-semibold text-amber-800 uppercase tracking-wide">Ngày bị bỏ qua</p>
                <ul className="divide-y divide-amber-100 text-xs text-slate-700 max-h-48 overflow-y-auto">
                  {result.skipped.map((s) => (
                    <li key={s.study_date} className="px-3 py-1.5 flex items-center justify-between gap-2">
                      <span className="font-mono tabular-nums font-medium">{s.study_date}</span>
                      <span className="text-[11px] text-slate-500 text-right">{s.reason}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div className="flex justify-end gap-2 pt-1">
              <button onClick={() => setResult(null)} className="px-4 py-2 min-h-[36px] text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-md hover:bg-slate-50 cursor-pointer">
                Xếp tiếp đợt khác
              </button>
              <button onClick={onClose} className="px-4 py-2 min-h-[36px] text-xs font-medium text-white bg-slate-900 hover:bg-slate-800 rounded-md cursor-pointer">
                Đóng
              </button>
            </div>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto overscroll-contain p-4 sm:p-6 space-y-4">
            {(formError || serverError) && (
              <div className="flex items-start gap-2.5 p-3 text-xs bg-rose-50 border border-rose-200 text-rose-700 rounded-md">
                <AlertTriangle size={16} className="shrink-0 text-rose-500 mt-0.5" />
                <div>
                  <p className="font-semibold">Không thể sinh lịch:</p>
                  <p>{formError ?? serverError}</p>
                </div>
              </div>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="sm:col-span-2">
                <label className="block text-xs font-semibold text-slate-700 mb-1">Lớp học phần</label>
                <select value={classId} onChange={(e) => { const id = Number(e.target.value); setClassId(id); const cls = classes.find((c) => c.id === id); if (cls && cls.total_sessions) setTotalSessions(cls.total_sessions); }} className="w-full px-3 py-2 text-xs rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900">
                  <option value={0}>-- Chọn lớp học phần --</option>
                  {classes.map((c) => (
                    <option key={c.id} value={c.id}>{c.class_code} - {c.course_name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Phòng học</label>
                <input type="text" value={roomName} onChange={(e) => setRoomName(e.target.value)} placeholder="A1-301" className="w-full px-3 py-2 text-xs font-mono uppercase rounded-md border border-slate-200 focus:outline-hidden focus:ring-1 focus:ring-slate-900" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Số buổi cần sinh</label>
                <input type="number" min={1} max={60} value={totalSessions} onChange={(e) => setTotalSessions(Number(e.target.value) || 0)} className="w-full px-3 py-2 text-xs font-mono rounded-md border border-slate-200 focus:outline-hidden focus:ring-1 focus:ring-slate-900" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Ngày bắt đầu</label>
                <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="w-full px-3 py-2 text-xs font-mono rounded-md border border-slate-200 focus:outline-hidden focus:ring-1 focus:ring-slate-900" />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Bắt đầu</label>
                  <input type="time" value={startTime} onChange={(e) => setStartTime(e.target.value)} className="w-full px-3 py-2 text-xs font-mono rounded-md border border-slate-200 focus:outline-hidden focus:ring-1 focus:ring-slate-900" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Kết thúc</label>
                  <input type="time" value={endTime} onChange={(e) => setEndTime(e.target.value)} className="w-full px-3 py-2 text-xs font-mono rounded-md border border-slate-200 focus:outline-hidden focus:ring-1 focus:ring-slate-900" />
                </div>
              </div>
            </div>
            <div>
              <span className="text-[11px] text-slate-500">Khung giờ phổ biến:</span>
              <div className="flex flex-wrap gap-1.5 mt-1">
                {[
                  { label: "Sáng (07:30 - 11:30)", start: "07:30", end: "11:30" },
                  { label: "Chiều (13:00 - 17:00)", start: "13:00", end: "17:00" },
                  { label: "Tối (17:30 - 20:45)", start: "17:30", end: "20:45" },
                ].map((slot) => (
                  <button key={slot.label} type="button" onClick={() => { setStartTime(slot.start); setEndTime(slot.end); }} className="px-2 py-1 text-[11px] font-mono bg-slate-100 hover:bg-slate-200 text-slate-700 rounded transition-colors cursor-pointer">{slot.label}</button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">Học vào các thứ</label>
              <div className="flex flex-wrap gap-1.5">
                {WEEKDAY_LABELS.map((label, w) => (
                  <button key={label} type="button" onClick={() => toggleWeekday(w)} title={FULL_WEEKDAY[w]} className={weekdays.includes(w) ? "min-w-[44px] min-h-[36px] px-3 py-1.5 rounded-md text-xs font-semibold border transition-colors cursor-pointer bg-slate-900 text-white border-slate-900" : "min-w-[44px] min-h-[36px] px-3 py-1.5 rounded-md text-xs font-semibold border transition-colors cursor-pointer bg-white text-slate-600 border-slate-200 hover:bg-slate-50"}>
                    {label}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide flex items-center gap-1.5 mb-1">
                <Clock size={12} /> Xem trước {preview.length} buổi
              </p>
              {preview.length === 0 ? (
                <p className="text-xs text-slate-400">Chọn ngày bắt đầu và ít nhất 1 thứ để xem lịch sinh.</p>
              ) : (
                <ul className="divide-y divide-slate-100 text-xs max-h-44 overflow-y-auto rounded-md border border-slate-200 bg-white">
                  {preview.map((p, i) => (
                    <li key={p.date} className="px-3 py-1.5 flex items-center justify-between gap-2">
                      <span className="font-mono tabular-nums font-semibold text-slate-600">Buổi {i + 1}</span>
                      <span className="font-mono tabular-nums text-slate-800">{FULL_WEEKDAY[p.weekday]} {p.date}</span>
                      <span className="font-mono tabular-nums text-slate-500">{startTime} - {endTime}</span>
                    </li>
                  ))}
                </ul>
              )}
              <p className="text-[11px] text-slate-400 mt-1">STT tự nối sau buổi lớn nhất của lớp. Ngày trùng phòng sẽ bị bỏ qua và liệt kê sau khi lưu.</p>
            </div>
          </div>
        )}
        {!result && (
          <div className="flex flex-col-reverse sm:flex-row sm:items-center sm:justify-end gap-2 px-4 sm:px-6 py-3 border-t border-slate-200 bg-slate-50/50 shrink-0">
            <button type="button" onClick={onClose} disabled={isSubmitting} className="w-full sm:w-auto px-4 py-2 min-h-[36px] text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-md hover:bg-slate-50 disabled:opacity-50 cursor-pointer">Hủy bỏ</button>
            <button type="button" onClick={handleSubmit} disabled={isSubmitting} className="w-full sm:w-auto flex items-center justify-center gap-2 px-4 py-2 min-h-[36px] text-xs font-medium text-white bg-slate-900 hover:bg-slate-800 rounded-md disabled:opacity-50 cursor-pointer">
              {isSubmitting && <Loader2 size={14} className="animate-spin" />}
              Sinh {totalSessions || 0} buổi
            </button>
          </div>
        )}
      </div>
    </div>
  );
}