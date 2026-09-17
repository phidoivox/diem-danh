"use client";

import React, { useState, useEffect } from "react";
import { RoleGuard } from "@/components/layout/role-guard";
import {
  getAdminSettings,
  updateAdminSettings,
  triggerNightlyEvaluation,
  EvaluationResult,
} from "@/lib/api";
import {
  Settings,
  Save,
  Play,
  RotateCcw,
  CheckCircle2,
  AlertCircle,
  Clock,
  ShieldAlert,
  Award,
  Sliders,
  Calendar,
  Loader2,
  Check,
} from "lucide-react";

export default function AdminSettingsPage() {
  // Settings state
  const [pointFullAttendance, setPointFullAttendance] = useState("2");
  const [pointLate, setPointLate] = useState("-1");
  const [pointHalfAbsence, setPointHalfAbsence] = useState("-2");
  const [pointAbsenceWithoutLeave, setPointAbsenceWithoutLeave] = useState("-5");
  const [pointUniformViolation, setPointUniformViolation] = useState("-2");

  const [lateToleranceMinutes, setLateToleranceMinutes] = useState("15");
  const [requireCheckout, setRequireCheckout] = useState(false);
  const [maxAbsencePercentExamBan, setMaxAbsencePercentExamBan] = useState("20");
  const [warningAbsencePercent, setWarningAbsencePercent] = useState("15");

  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Nightly Evaluation state
  const [targetDate, setTargetDate] = useState(() => {
    return new Date().toISOString().split("T")[0];
  });
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [evalResult, setEvalResult] = useState<EvaluationResult | null>(null);
  const [evalError, setEvalError] = useState<string | null>(null);

  // Load existing settings
  const fetchSettings = async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const data = await getAdminSettings();
      const map = data.settings || {};

      if (map["POINT_FULL_ATTENDANCE"]) setPointFullAttendance(map["POINT_FULL_ATTENDANCE"]);
      if (map["POINT_LATE"]) setPointLate(map["POINT_LATE"]);
      if (map["POINT_HALF_ABSENCE"]) setPointHalfAbsence(map["POINT_HALF_ABSENCE"]);
      if (map["POINT_ABSENCE_WITHOUT_LEAVE"])
        setPointAbsenceWithoutLeave(map["POINT_ABSENCE_WITHOUT_LEAVE"]);
      if (map["POINT_UNIFORM_VIOLATION"]) setPointUniformViolation(map["POINT_UNIFORM_VIOLATION"]);

      if (map["LATE_TOLERANCE_MINUTES"]) setLateToleranceMinutes(map["LATE_TOLERANCE_MINUTES"]);
      if (map["REQUIRE_CHECKOUT"])
        setRequireCheckout(map["REQUIRE_CHECKOUT"].toLowerCase() === "true");
      if (map["MAX_ABSENCE_PERCENT_EXAM_BAN"])
        setMaxAbsencePercentExamBan(map["MAX_ABSENCE_PERCENT_EXAM_BAN"]);
      if (map["WARNING_ABSENCE_PERCENT"]) setWarningAbsencePercent(map["WARNING_ABSENCE_PERCENT"]);
    } catch (err: any) {
      setErrorMessage(err.message || "Không thể tải cấu hình tham số hệ thống");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchSettings();
  }, []);

  // Save Settings
  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setErrorMessage(null);
    setSaveSuccess(false);

    const payload: Record<string, string> = {
      POINT_FULL_ATTENDANCE: String(pointFullAttendance),
      POINT_LATE: String(pointLate),
      POINT_HALF_ABSENCE: String(pointHalfAbsence),
      POINT_ABSENCE_WITHOUT_LEAVE: String(pointAbsenceWithoutLeave),
      POINT_UNIFORM_VIOLATION: String(pointUniformViolation),
      LATE_TOLERANCE_MINUTES: String(lateToleranceMinutes),
      REQUIRE_CHECKOUT: String(requireCheckout),
      MAX_ABSENCE_PERCENT_EXAM_BAN: String(maxAbsencePercentExamBan),
      WARNING_ABSENCE_PERCENT: String(warningAbsencePercent),
    };

    try {
      await updateAdminSettings(payload);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: any) {
      setErrorMessage(err.message || "Không thể lưu cấu hình tham số");
    } finally {
      setIsSaving(false);
    }
  };

  // Run Nightly Evaluation Now
  const handleRunEvaluationNow = async () => {
    setIsEvaluating(true);
    setEvalError(null);
    setEvalResult(null);

    try {
      const res = await triggerNightlyEvaluation(targetDate || undefined);
      setEvalResult(res);
    } catch (err: any) {
      setEvalError(err.message || "Lỗi khi kích hoạt tính điểm chuyên cần");
    } finally {
      setIsEvaluating(false);
    }
  };

  return (
    <RoleGuard allowedRoles={["ADMIN"]}>
      <div className="space-y-6 max-w-5xl">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-200">
          <div>
            <h2 className="text-lg font-semibold text-slate-900 tracking-tight flex items-center gap-2">
              <Settings size={20} className="text-slate-700" />
              Cấu hình tham số hệ thống
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Thiết lập quy tắc tính điểm rèn luyện, ngưỡng cấm thi và vận hành đánh giá tự động 23h59
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={fetchSettings}
              disabled={isLoading || isSaving}
              className="p-2 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-md border border-slate-200 transition-colors cursor-pointer"
              title="Tải lại cài đặt"
            >
              <RotateCcw size={15} />
            </button>

            <button
              onClick={handleSaveSettings}
              disabled={isLoading || isSaving}
              className="flex items-center gap-1.5 px-4 py-2 text-xs font-medium text-white bg-slate-900 hover:bg-slate-800 rounded-md transition-colors disabled:opacity-50 cursor-pointer shadow-xs"
            >
              {isSaving ? (
                <Loader2 size={14} className="animate-spin" />
              ) : saveSuccess ? (
                <Check size={14} className="text-emerald-400" />
              ) : (
                <Save size={14} />
              )}
              {saveSuccess ? "Đã lưu thành công" : "Lưu cấu hình"}
            </button>
          </div>
        </div>

        {/* Global Alerts */}
        {errorMessage && (
          <div className="p-3 text-xs bg-rose-50 border border-rose-200 text-rose-800 rounded-md flex items-start gap-2">
            <AlertCircle size={16} className="shrink-0 mt-0.5 text-rose-500" />
            <span>{errorMessage}</span>
          </div>
        )}

        {saveSuccess && (
          <div className="p-3 text-xs bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-md flex items-center gap-2">
            <CheckCircle2 size={16} className="text-emerald-600" />
            <span>Toàn bộ tham số cấu hình đã được cập nhật đồng bộ vào hệ thống.</span>
          </div>
        )}

        {isLoading ? (
          <div className="p-12 text-center text-slate-400">
            <Loader2 size={24} className="animate-spin mx-auto text-slate-500 mb-2" />
            <span className="text-xs">Đang nạp tham số hệ thống...</span>
          </div>
        ) : (
          <form onSubmit={handleSaveSettings} className="space-y-6">
            {/* SECTION 1: ATTENDANCE CONDUCT POINTS */}
            <div className="bg-white rounded-lg border border-slate-200 shadow-xs overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-200 bg-slate-50/50 flex items-center gap-2.5">
                <div className="p-1.5 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-md">
                  <Award size={16} />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">
                    Quy tắc tính điểm Chuyên cần & Rèn luyện
                  </h3>
                  <p className="text-xs text-slate-500">
                    Cộng/trừ điểm trực tiếp vào sổ cái rèn luyện của sinh viên sau mỗi buổi học
                  </p>
                </div>
              </div>

              <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-5">
                {/* POINT_FULL_ATTENDANCE */}
                <div className="p-3.5 rounded-md border border-slate-200 bg-slate-50/40 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-slate-800">
                      Tham gia đủ buổi, đúng giờ, chuẩn đồng phục
                    </label>
                    <span className="text-[11px] font-mono text-emerald-600 font-semibold">+ điểm</span>
                  </div>
                  <p className="text-[11px] text-slate-500">
                    Mã cấu hình: <code className="font-mono text-slate-700">POINT_FULL_ATTENDANCE</code>
                  </p>
                  <div className="flex items-center gap-2 pt-1">
                    <input
                      type="number"
                      value={pointFullAttendance}
                      onChange={(e) => setPointFullAttendance(e.target.value)}
                      className="w-32 px-3 py-1.5 text-xs font-mono tabular-nums font-semibold rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                    />
                    <span className="text-xs text-slate-500">điểm / buổi</span>
                  </div>
                </div>

                {/* POINT_LATE */}
                <div className="p-3.5 rounded-md border border-slate-200 bg-slate-50/40 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-slate-800">
                      Đi muộn trong ngưỡng dung sai
                    </label>
                    <span className="text-[11px] font-mono text-amber-600 font-semibold">- điểm</span>
                  </div>
                  <p className="text-[11px] text-slate-500">
                    Mã cấu hình: <code className="font-mono text-slate-700">POINT_LATE</code>
                  </p>
                  <div className="flex items-center gap-2 pt-1">
                    <input
                      type="number"
                      value={pointLate}
                      onChange={(e) => setPointLate(e.target.value)}
                      className="w-32 px-3 py-1.5 text-xs font-mono tabular-nums font-semibold rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                    />
                    <span className="text-xs text-slate-500">điểm / lần</span>
                  </div>
                </div>

                {/* POINT_HALF_ABSENCE */}
                <div className="p-3.5 rounded-md border border-slate-200 bg-slate-50/40 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-slate-800">
                      Vắng nửa buổi (vào quá trễ hoặc về sớm)
                    </label>
                    <span className="text-[11px] font-mono text-amber-600 font-semibold">- điểm</span>
                  </div>
                  <p className="text-[11px] text-slate-500">
                    Mã cấu hình: <code className="font-mono text-slate-700">POINT_HALF_ABSENCE</code>
                  </p>
                  <div className="flex items-center gap-2 pt-1">
                    <input
                      type="number"
                      value={pointHalfAbsence}
                      onChange={(e) => setPointHalfAbsence(e.target.value)}
                      className="w-32 px-3 py-1.5 text-xs font-mono tabular-nums font-semibold rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                    />
                    <span className="text-xs text-slate-500">điểm / buổi (0.5 buổi vắng)</span>
                  </div>
                </div>

                {/* POINT_ABSENCE_WITHOUT_LEAVE */}
                <div className="p-3.5 rounded-md border border-slate-200 bg-slate-50/40 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-slate-800">
                      Vắng không phép (Nghỉ học không có đơn)
                    </label>
                    <span className="text-[11px] font-mono text-rose-600 font-semibold">- điểm</span>
                  </div>
                  <p className="text-[11px] text-slate-500">
                    Mã cấu hình: <code className="font-mono text-slate-700">POINT_ABSENCE_WITHOUT_LEAVE</code>
                  </p>
                  <div className="flex items-center gap-2 pt-1">
                    <input
                      type="number"
                      value={pointAbsenceWithoutLeave}
                      onChange={(e) => setPointAbsenceWithoutLeave(e.target.value)}
                      className="w-32 px-3 py-1.5 text-xs font-mono tabular-nums font-semibold rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                    />
                    <span className="text-xs text-slate-500">điểm / buổi (1.0 buổi vắng)</span>
                  </div>
                </div>

                {/* POINT_UNIFORM_VIOLATION */}
                <div className="p-3.5 rounded-md border border-slate-200 bg-slate-50/40 space-y-1.5 md:col-span-2">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-slate-800">
                      Vi phạm quy định đồng phục (quét AI Kiosk)
                    </label>
                    <span className="text-[11px] font-mono text-rose-600 font-semibold">- điểm</span>
                  </div>
                  <p className="text-[11px] text-slate-500">
                    Mã cấu hình: <code className="font-mono text-slate-700">POINT_UNIFORM_VIOLATION</code>
                  </p>
                  <div className="flex items-center gap-2 pt-1">
                    <input
                      type="number"
                      value={pointUniformViolation}
                      onChange={(e) => setPointUniformViolation(e.target.value)}
                      className="w-32 px-3 py-1.5 text-xs font-mono tabular-nums font-semibold rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                    />
                    <span className="text-xs text-slate-500">điểm / lần phát hiện</span>
                  </div>
                </div>
              </div>
            </div>

            {/* SECTION 2: ACADEMIC POLICIES & TOLERANCES */}
            <div className="bg-white rounded-lg border border-slate-200 shadow-xs overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-200 bg-slate-50/50 flex items-center gap-2.5">
                <div className="p-1.5 bg-indigo-50 text-indigo-700 border border-indigo-200 rounded-md">
                  <Sliders size={16} />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">
                    Quy chế Học vụ & Ngưỡng Cấm thi
                  </h3>
                  <p className="text-xs text-slate-500">
                    Thời gian dung sai điểm danh và tỷ lệ vắng áp dụng theo Quy chế đào tạo
                  </p>
                </div>
              </div>

              <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-5">
                {/* LATE_TOLERANCE_MINUTES */}
                <div className="p-3.5 rounded-md border border-slate-200 bg-slate-50/40 space-y-1.5">
                  <label className="text-xs font-semibold text-slate-800 flex items-center gap-1.5">
                    <Clock size={13} className="text-slate-500" />
                    Dung sai thời gian đi muộn
                  </label>
                  <p className="text-[11px] text-slate-500">
                    Mã: <code className="font-mono text-slate-700">LATE_TOLERANCE_MINUTES</code>
                  </p>
                  <div className="flex items-center gap-2 pt-1">
                    <input
                      type="number"
                      min={0}
                      max={120}
                      value={lateToleranceMinutes}
                      onChange={(e) => setLateToleranceMinutes(e.target.value)}
                      className="w-28 px-3 py-1.5 text-xs font-mono tabular-nums font-semibold rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                    />
                    <span className="text-xs text-slate-500">phút sau giờ bắt đầu ca</span>
                  </div>
                </div>

                {/* REQUIRE_CHECKOUT */}
                <div className="p-3.5 rounded-md border border-slate-200 bg-slate-50/40 space-y-2">
                  <label className="text-xs font-semibold text-slate-800">
                    Yêu cầu Check-out cuối buổi
                  </label>
                  <p className="text-[11px] text-slate-500">
                    Mã: <code className="font-mono text-slate-700">REQUIRE_CHECKOUT</code>
                  </p>
                  <div className="flex items-center gap-2.5 pt-1">
                    <input
                      type="checkbox"
                      id="require_checkout"
                      checked={requireCheckout}
                      onChange={(e) => setRequireCheckout(e.target.checked)}
                      className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-900 cursor-pointer"
                    />
                    <label htmlFor="require_checkout" className="text-xs text-slate-700 cursor-pointer font-medium">
                      Bắt buộc cả Check-in và Check-out (nếu quên check-out tính vắng nửa buổi)
                    </label>
                  </div>
                </div>

                {/* MAX_ABSENCE_PERCENT_EXAM_BAN */}
                <div className="p-3.5 rounded-md border border-slate-200 bg-slate-50/40 space-y-1.5">
                  <label className="text-xs font-semibold text-slate-800 flex items-center gap-1.5">
                    <ShieldAlert size={13} className="text-rose-500" />
                    Ngưỡng tỷ lệ vắng bị CẤM THI
                  </label>
                  <p className="text-[11px] text-slate-500">
                    Mã: <code className="font-mono text-slate-700">MAX_ABSENCE_PERCENT_EXAM_BAN</code>
                  </p>
                  <div className="flex items-center gap-2 pt-1">
                    <input
                      type="number"
                      min={1}
                      max={100}
                      value={maxAbsencePercentExamBan}
                      onChange={(e) => setMaxAbsencePercentExamBan(e.target.value)}
                      className="w-28 px-3 py-1.5 text-xs font-mono tabular-nums font-semibold rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                    />
                    <span className="text-xs text-slate-500">% tổng số buổi môn học (Chuẩn: 20%)</span>
                  </div>
                </div>

                {/* WARNING_ABSENCE_PERCENT */}
                <div className="p-3.5 rounded-md border border-slate-200 bg-slate-50/40 space-y-1.5">
                  <label className="text-xs font-semibold text-slate-800 flex items-center gap-1.5">
                    <AlertCircle size={13} className="text-amber-500" />
                    Ngưỡng tỷ lệ vắng CẢNH BÁO SỚM
                  </label>
                  <p className="text-[11px] text-slate-500">
                    Mã: <code className="font-mono text-slate-700">WARNING_ABSENCE_PERCENT</code>
                  </p>
                  <div className="flex items-center gap-2 pt-1">
                    <input
                      type="number"
                      min={1}
                      max={100}
                      value={warningAbsencePercent}
                      onChange={(e) => setWarningAbsencePercent(e.target.value)}
                      className="w-28 px-3 py-1.5 text-xs font-mono tabular-nums font-semibold rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                    />
                    <span className="text-xs text-slate-500">% tổng số buổi (Chuẩn: 15%)</span>
                  </div>
                </div>
              </div>
            </div>

            {/* SECTION 3: NIGHTLY EVALUATION RUN-NOW */}
            <div className="bg-white rounded-lg border border-slate-200 shadow-xs overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-200 bg-slate-50/50 flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="p-1.5 bg-sky-50 text-sky-700 border border-sky-200 rounded-md">
                    <Play size={16} />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-slate-900">
                      Tự động hóa 23h59 & Kích hoạt thủ công
                    </h3>
                    <p className="text-xs text-slate-500">
                      Hệ thống tự động chạy cron lúc 23:59. Quản trị viên có thể bấm chạy bù hoặc chạy thử nghiệm ngay lập tức.
                    </p>
                  </div>
                </div>
              </div>

              <div className="p-6 space-y-4">
                <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                      Ngày đánh giá chuyên cần:
                    </label>
                    <div className="relative">
                      <Calendar size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                      <input
                        type="date"
                        value={targetDate}
                        onChange={(e) => setTargetDate(e.target.value)}
                        className="pl-8 pr-3 py-1.5 text-xs font-mono rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                      />
                    </div>
                  </div>

                  <div className="sm:self-end">
                    <button
                      type="button"
                      onClick={handleRunEvaluationNow}
                      disabled={isEvaluating}
                      className="flex items-center justify-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-slate-900 hover:bg-slate-800 rounded-md transition-colors disabled:opacity-50 cursor-pointer w-full sm:w-auto shadow-xs"
                    >
                      {isEvaluating ? (
                        <Loader2 size={14} className="animate-spin" />
                      ) : (
                        <Play size={14} />
                      )}
                      Chạy tính điểm ngay (Run Now)
                    </button>
                  </div>
                </div>

                {evalError && (
                  <div className="p-3 text-xs bg-rose-50 border border-rose-200 text-rose-800 rounded-md flex items-start gap-2">
                    <AlertCircle size={15} className="shrink-0 mt-0.5 text-rose-500" />
                    <span>{evalError}</span>
                  </div>
                )}

                {evalResult && (
                  <div className="p-4 bg-slate-50 rounded-lg border border-slate-200 space-y-3">
                    <div className="flex items-center gap-2 text-xs font-semibold text-emerald-800">
                      <CheckCircle2 size={16} className="text-emerald-600" />
                      Đánh giá chuyên cần hoàn tất thành công cho ngày {evalResult.target_date}!
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                      <div className="p-3 bg-white rounded-md border border-slate-200">
                        <div className="text-[11px] text-slate-500">Số ca học đã duyệt</div>
                        <div className="text-lg font-bold font-mono tabular-nums text-slate-900 mt-0.5">
                          {evalResult.schedules_evaluated}
                        </div>
                      </div>

                      <div className="p-3 bg-white rounded-md border border-slate-200">
                        <div className="text-[11px] text-slate-500">Số sinh viên đánh giá</div>
                        <div className="text-lg font-bold font-mono tabular-nums text-slate-900 mt-0.5">
                          {evalResult.students_evaluated}
                        </div>
                      </div>

                      <div className="p-3 bg-white rounded-md border border-slate-200">
                        <div className="text-[11px] text-slate-500">Tổng bản ghi ghi nhận</div>
                        <div className="text-lg font-bold font-mono tabular-nums text-slate-900 mt-0.5">
                          {evalResult.total_records}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </form>
        )}
      </div>
    </RoleGuard>
  );
}
