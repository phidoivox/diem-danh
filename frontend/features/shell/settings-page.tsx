"use client";

import React, { useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RoleGuard } from "./role-guard";
import { todayVN } from "./date";
import {
  getAdminSettings,
  updateAdminSettings,
  triggerNightlyEvaluation,
  sendTestEmail,
  EvaluationResult,
} from "./http";
import { toast } from "sonner";
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
  Mail,
  Loader2,
} from "lucide-react";

type SettingsTab = "points" | "academic" | "email" | "auto";

const TABS: { id: SettingsTab; label: string; icon: typeof Award }[] = [
  { id: "points", label: "Điểm chuyên cần", icon: Award },
  { id: "academic", label: "Học vụ & Cấm thi", icon: Sliders },
  { id: "email", label: "Email", icon: Mail },
  { id: "auto", label: "Tự động 23h59", icon: Play },
];

export default function AdminSettingsPage() {
  const queryClient = useQueryClient();
  const settingsQuery = useQuery({
    queryKey: ["admin-settings"],
    queryFn: getAdminSettings,
  });
  const [pointFullAttendance, setPointFullAttendance] = useState("2");
  const [pointLate, setPointLate] = useState("-1");
  const [pointHalfAbsence, setPointHalfAbsence] = useState("-2");
  const [pointAbsenceWithoutLeave, setPointAbsenceWithoutLeave] = useState("-5");
  const [pointUniformViolation, setPointUniformViolation] = useState("-2");

  const [lateToleranceMinutes, setLateToleranceMinutes] = useState("15");
  const [requireCheckout, setRequireCheckout] = useState(false);
  const [checkoutMinGapMinutes, setCheckoutMinGapMinutes] = useState("5");
  const [maxAbsencePercentExamBan, setMaxAbsencePercentExamBan] = useState("20");
  const [warningAbsencePercent, setWarningAbsencePercent] = useState("15");

  const [emailEnabled, setEmailEnabled] = useState(true);
  const [emailReminder, setEmailReminder] = useState(true);
  const [emailWarning, setEmailWarning] = useState(true);
  const [emailBan, setEmailBan] = useState(true);
  const [smtpEnabled, setSmtpEnabled] = useState(false);
  const [smtpHost, setSmtpHost] = useState("");
  const [smtpPort, setSmtpPort] = useState("587");
  const [smtpUser, setSmtpUser] = useState("");
  const [smtpPassword, setSmtpPassword] = useState("");
  const [smtpFrom, setSmtpFrom] = useState("");
  const [smtpUseTls, setSmtpUseTls] = useState(true);
  const [smtpTimeout, setSmtpTimeout] = useState("10");
  const [testTo, setTestTo] = useState("");
  const [testMsg, setTestMsg] = useState<string | null>(null);
  const [isTesting, setIsTesting] = useState(false);
  const [activeTab, setActiveTab] = useState<SettingsTab>("points");

  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Nightly Evaluation state (ngày VN, không lệch UTC như toISOString).
  const [targetDate, setTargetDate] = useState(() => todayVN());
  const [evalResult, setEvalResult] = useState<EvaluationResult | null>(null);
  const [evalError, setEvalError] = useState<string | null>(null);

  const isLoading = settingsQuery.isPending;
  const queryError = settingsQuery.isError
    ? settingsQuery.error instanceof Error
      ? settingsQuery.error.message
      : "Không thể tải cấu hình tham số hệ thống"
    : null;

  // Nạp settings từ cache query vào form cục bộ khi dữ liệu về.
  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect -- đồng bộ dữ liệu query vào form */
    const map = settingsQuery.data?.settings || {};
    if (!settingsQuery.data) return;
    if (map["POINT_FULL_ATTENDANCE"]) setPointFullAttendance(map["POINT_FULL_ATTENDANCE"]);
    if (map["POINT_LATE"]) setPointLate(map["POINT_LATE"]);
    if (map["POINT_HALF_ABSENCE"]) setPointHalfAbsence(map["POINT_HALF_ABSENCE"]);
    if (map["POINT_ABSENCE_WITHOUT_LEAVE"])
      setPointAbsenceWithoutLeave(map["POINT_ABSENCE_WITHOUT_LEAVE"]);
    if (map["POINT_UNIFORM_VIOLATION"]) setPointUniformViolation(map["POINT_UNIFORM_VIOLATION"]);

    if (map["LATE_TOLERANCE_MINUTES"]) setLateToleranceMinutes(map["LATE_TOLERANCE_MINUTES"]);
    if (map["REQUIRE_CHECKOUT"])
      setRequireCheckout(map["REQUIRE_CHECKOUT"].toLowerCase() === "true");
    if (map["CHECKOUT_MIN_GAP_MINUTES"])
      setCheckoutMinGapMinutes(map["CHECKOUT_MIN_GAP_MINUTES"]);
    if (map["MAX_ABSENCE_PERCENT_EXAM_BAN"])
      setMaxAbsencePercentExamBan(map["MAX_ABSENCE_PERCENT_EXAM_BAN"]);
    if (map["WARNING_ABSENCE_PERCENT"]) setWarningAbsencePercent(map["WARNING_ABSENCE_PERCENT"]);
    if (map["EMAIL_ENABLED"] !== undefined)
      setEmailEnabled(map["EMAIL_ENABLED"].toLowerCase() === "true");
    if (map["EMAIL_REMINDER_ENABLED"] !== undefined)
      setEmailReminder(map["EMAIL_REMINDER_ENABLED"].toLowerCase() === "true");
    if (map["EMAIL_WARNING_ENABLED"] !== undefined)
      setEmailWarning(map["EMAIL_WARNING_ENABLED"].toLowerCase() === "true");
    if (map["EMAIL_BAN_ENABLED"] !== undefined)
      setEmailBan(map["EMAIL_BAN_ENABLED"].toLowerCase() === "true");
    if (map["SMTP_ENABLED"] !== undefined)
      setSmtpEnabled(map["SMTP_ENABLED"].toLowerCase() === "true");
    if (map["SMTP_HOST"] !== undefined) setSmtpHost(map["SMTP_HOST"]);
    if (map["SMTP_PORT"] !== undefined) setSmtpPort(map["SMTP_PORT"]);
    if (map["SMTP_USER"] !== undefined) setSmtpUser(map["SMTP_USER"]);
    if (map["SMTP_FROM"] !== undefined) setSmtpFrom(map["SMTP_FROM"]);
    if (map["SMTP_USE_TLS"] !== undefined)
      setSmtpUseTls(map["SMTP_USE_TLS"].toLowerCase() === "true");
    if (map["SMTP_TIMEOUT_S"] !== undefined) setSmtpTimeout(map["SMTP_TIMEOUT_S"]);
    setSmtpPassword("");
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [settingsQuery.data]);

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    if (queryError) setErrorMessage(queryError);
    else setErrorMessage(null);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [queryError]);

  const fetchSettings = () =>
    queryClient.invalidateQueries({ queryKey: ["admin-settings"] });

  const saveMutation = useMutation({
    mutationFn: (payload: Record<string, string>) => updateAdminSettings(payload),
    onSuccess: () => {
      setSmtpPassword("");
      queryClient.invalidateQueries({ queryKey: ["admin-settings"] });
      toast.success("Toàn bộ tham số cấu hình đã được cập nhật đồng bộ vào hệ thống.");
    },
    onError: (err: unknown) => {
      toast.error(
        err instanceof Error ? err.message : "Không thể lưu cấu hình tham số"
      );
    },
  });
  const isSaving = saveMutation.isPending;

  const evalMutation = useMutation({
    mutationFn: (date?: string) => triggerNightlyEvaluation(date),
    onSuccess: (res) => {
      setEvalError(null);
      setEvalResult(res);
    },
    onError: (err: unknown) => {
      setEvalError(
        err instanceof Error ? err.message : "Lỗi khi kích hoạt tính điểm chuyên cần"
      );
    },
  });
  const isEvaluating = evalMutation.isPending;

  // Save Settings
  const handleSaveSettings = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    const payload: Record<string, string> = {
      POINT_FULL_ATTENDANCE: String(pointFullAttendance),
      POINT_LATE: String(pointLate),
      POINT_HALF_ABSENCE: String(pointHalfAbsence),
      POINT_ABSENCE_WITHOUT_LEAVE: String(pointAbsenceWithoutLeave),
      POINT_UNIFORM_VIOLATION: String(pointUniformViolation),
      LATE_TOLERANCE_MINUTES: String(lateToleranceMinutes),
      REQUIRE_CHECKOUT: String(requireCheckout),
      CHECKOUT_MIN_GAP_MINUTES: String(checkoutMinGapMinutes),
      MAX_ABSENCE_PERCENT_EXAM_BAN: String(maxAbsencePercentExamBan),
      WARNING_ABSENCE_PERCENT: String(warningAbsencePercent),
      EMAIL_ENABLED: String(emailEnabled),
      EMAIL_REMINDER_ENABLED: String(emailReminder),
      EMAIL_WARNING_ENABLED: String(emailWarning),
      EMAIL_BAN_ENABLED: String(emailBan),
      SMTP_ENABLED: String(smtpEnabled),
      SMTP_HOST: smtpHost.trim(),
      SMTP_PORT: String(smtpPort),
      SMTP_USER: smtpUser.trim(),
      SMTP_FROM: smtpFrom.trim(),
      SMTP_USE_TLS: String(smtpUseTls),
      SMTP_TIMEOUT_S: String(smtpTimeout),
      ...(smtpPassword ? { SMTP_PASSWORD: smtpPassword } : {}),
    };

    saveMutation.mutate(payload);
  };

  // Run Nightly Evaluation Now
  const handleRunEvaluationNow = () => {
    setEvalError(null);
    setEvalResult(null);
    evalMutation.mutate(targetDate || undefined);
  };

  const handleSendTest = async () => {
    if (!testTo.trim()) return setTestMsg("Nhập email nhận test.");
    setIsTesting(true);
    setTestMsg(null);
    try {
      const r = await sendTestEmail(testTo.trim());
      setTestMsg(r?.ok ? "Đã gửi mail test." : `Không gửi được: ${JSON.stringify(r)}`);
    } catch (e) {
      setTestMsg(e instanceof Error ? e.message : "Lỗi gửi mail test");
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <RoleGuard allowedRoles={["ADMIN"]}>
      <div className="space-y-4 sm:space-y-6 max-w-5xl">
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

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={fetchSettings}
              disabled={isLoading || isSaving}
              className="p-2 min-h-[38px] min-w-[38px] flex items-center justify-center text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-md border border-slate-200 transition-colors cursor-pointer"
              title="Tải lại cài đặt"
            >
              <RotateCcw size={15} />
            </button>

            <button
              onClick={handleSaveSettings}
              disabled={isLoading || isSaving}
              className="flex items-center justify-center gap-1.5 px-4 py-2 min-h-[38px] text-xs font-medium text-white bg-slate-900 hover:bg-slate-800 rounded-md transition-colors disabled:opacity-50 cursor-pointer shadow-xs"
            >
              {isSaving ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Save size={14} />
              )}
              <span>Lưu cấu hình</span>
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

        {isLoading ? (
          <div className="p-12 text-center text-slate-400">
            <Loader2 size={24} className="animate-spin mx-auto text-slate-500 mb-2" />
            <span className="text-xs">Đang nạp tham số hệ thống...</span>
          </div>
        ) : (
          <form onSubmit={handleSaveSettings} className="space-y-4">
            {/* Tab bar */}
            <div className="flex gap-1 p-1 bg-slate-100 rounded-lg border border-slate-200 overflow-x-auto">
              {TABS.map((t) => {
                const Icon = t.icon;
                const active = activeTab === t.id;
                return (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setActiveTab(t.id)}
                    className={`flex items-center gap-1.5 px-3 py-2 min-h-[36px] text-xs font-medium rounded-md whitespace-nowrap transition-colors cursor-pointer ${
                      active
                        ? "bg-white text-slate-900 shadow-xs border border-slate-200"
                        : "text-slate-500 hover:text-slate-800"
                    }`}
                  >
                    <Icon size={14} />
                    <span>{t.label}</span>
                  </button>
                );
              })}
            </div>

            {activeTab === "points" && (
            <div className="bg-white rounded-lg border border-slate-200 shadow-xs overflow-hidden">
              <div className="px-4 sm:px-6 py-4 border-b border-slate-200 bg-slate-50/50 flex items-center gap-2.5">
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

              <div className="p-4 sm:p-6 grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-5">
                {/* POINT_FULL_ATTENDANCE */}
                <div className="p-3.5 rounded-md border border-slate-200 bg-slate-50/40 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-slate-800">
                      Tham gia đủ buổi, đúng giờ, chuẩn đồng phục
                    </label>
                    <span className="text-[11px] font-mono text-emerald-600 font-semibold">+ điểm</span>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 pt-1">
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
                  <div className="flex flex-wrap items-center gap-2 pt-1">
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
                  <div className="flex flex-wrap items-center gap-2 pt-1">
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
                  <div className="flex flex-wrap items-center gap-2 pt-1">
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
                <div className="p-3.5 rounded-md border border-slate-200 bg-slate-50/40 space-y-1.5 sm:col-span-2">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-slate-800">
                      Vi phạm quy định đồng phục
                    </label>
                    <span className="text-[11px] font-mono text-rose-600 font-semibold">- điểm</span>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 pt-1">
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
            )}

            {activeTab === "academic" && (
            <div className="bg-white rounded-lg border border-slate-200 shadow-xs overflow-hidden">
              <div className="px-4 sm:px-6 py-4 border-b border-slate-200 bg-slate-50/50 flex items-center gap-2.5">
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

              <div className="p-4 sm:p-6 grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-5">
                {/* LATE_TOLERANCE_MINUTES */}
                <div className="p-3.5 rounded-md border border-slate-200 bg-slate-50/40 space-y-1.5">
                  <label className="text-xs font-semibold text-slate-800 flex items-center gap-1.5">
                    <Clock size={13} className="text-slate-500" />
                    Dung sai thời gian đi muộn
                  </label>
                  <div className="flex flex-wrap items-center gap-2 pt-1">
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

                {/* CHECKOUT_MIN_GAP_MINUTES */}
                <div className="p-3.5 rounded-md border border-slate-200 bg-slate-50/40 space-y-1.5">
                  <label className="text-xs font-semibold text-slate-800 flex items-center gap-1.5">
                    <Clock size={13} className="text-slate-500" />
                    Khoảng cách tối thiểu Check-in → Check-out
                  </label>
                  <div className="flex flex-wrap items-center gap-2 pt-1">
                    <input
                      type="number"
                      min={0}
                      max={60}
                      value={checkoutMinGapMinutes}
                      onChange={(e) => setCheckoutMinGapMinutes(e.target.value)}
                      className="w-28 px-3 py-1.5 text-xs font-mono tabular-nums font-semibold rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                    />
                    <span className="text-xs text-slate-500">phút (0 = cho check-out ngay)</span>
                  </div>
                </div>

                {/* MAX_ABSENCE_PERCENT_EXAM_BAN */}
                <div className="p-3.5 rounded-md border border-slate-200 bg-slate-50/40 space-y-1.5">
                  <label className="text-xs font-semibold text-slate-800 flex items-center gap-1.5">
                    <ShieldAlert size={13} className="text-rose-500" />
                    Ngưỡng tỷ lệ vắng bị CẤM THI
                  </label>
                  <div className="flex flex-wrap items-center gap-2 pt-1">
                    <input
                      type="number"
                      min={0}
                      max={100}
                      step={0.1}
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
                  <div className="flex flex-wrap items-center gap-2 pt-1">
                    <input
                      type="number"
                      min={0}
                      max={100}
                      step={0.1}
                      value={warningAbsencePercent}
                      onChange={(e) => setWarningAbsencePercent(e.target.value)}
                      className="w-28 px-3 py-1.5 text-xs font-mono tabular-nums font-semibold rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                    />
                    <span className="text-xs text-slate-500">% tổng số buổi (Chuẩn: 15%)</span>
                  </div>
                </div>
              </div>
            </div>
            )}

            {activeTab === "email" && (
            <div className="bg-white rounded-lg border border-slate-200 shadow-xs overflow-hidden">
              <div className="px-4 sm:px-6 py-4 border-b border-slate-200 bg-slate-50/50">
                <h3 className="text-sm font-semibold text-slate-900">
                  Thông báo Email (lịch học, cảnh báo, cấm thi)
                </h3>
                <p className="text-xs text-slate-500">
                  SMTP cấu hình tại đây, lưu database. Tắt gửi thật thì mail chạy log-only.
                </p>
              </div>
              <div className="p-4 sm:p-6 grid grid-cols-1 sm:grid-cols-2 gap-4">
                {[
                  ["Bật gửi mail", emailEnabled, setEmailEnabled],
                  ["Mail nhắc lịch học", emailReminder, setEmailReminder],
                  ["Mail cảnh báo", emailWarning, setEmailWarning],
                  ["Mail cấm thi", emailBan, setEmailBan],
                ].map(([label, val, set]) => (
                  <label key={label as string} className="flex items-center gap-2 text-xs text-slate-700">
                    <input
                      type="checkbox"
                      checked={val as boolean}
                      onChange={(e) => (set as (v: boolean) => void)(e.target.checked)}
                      className="h-4 w-4 rounded border-slate-300 text-slate-900 cursor-pointer"
                    />
                    {label as string}
                  </label>
                ))}
                <div className="sm:col-span-2 grid grid-cols-1 sm:grid-cols-2 gap-3 p-3 rounded-md border border-slate-200 bg-slate-50/40">
                  <label className="flex items-center gap-2 text-xs text-slate-700 sm:col-span-2">
                    <input
                      type="checkbox"
                      checked={smtpEnabled}
                      onChange={(e) => setSmtpEnabled(e.target.checked)}
                      className="h-4 w-4 rounded border-slate-300 text-slate-900 cursor-pointer"
                    />
                    Bật gửi SMTP thật
                  </label>
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-700 mb-1">SMTP host</label>
                    <input value={smtpHost} onChange={(e) => setSmtpHost(e.target.value)} placeholder="smtp.gmail.com" className="w-full px-3 py-2 min-h-[38px] text-xs font-mono rounded-md border border-slate-200 bg-white" />
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-700 mb-1">Port</label>
                    <input type="number" min={1} max={65535} value={smtpPort} onChange={(e) => setSmtpPort(e.target.value)} className="w-full px-3 py-2 min-h-[38px] text-xs font-mono rounded-md border border-slate-200 bg-white" />
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-700 mb-1">User đăng nhập</label>
                    <input value={smtpUser} onChange={(e) => setSmtpUser(e.target.value)} placeholder="you@gmail.com" className="w-full px-3 py-2 min-h-[38px] text-xs font-mono rounded-md border border-slate-200 bg-white" />
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-700 mb-1">Mật khẩu / App password</label>
                    <input type="password" value={smtpPassword} onChange={(e) => setSmtpPassword(e.target.value)} placeholder={settingsQuery.data?.has_smtp_password ? "•••••••• (để trống = giữ nguyên)" : "xxxx-xxxx-xxxx-xxxx"} className="w-full px-3 py-2 min-h-[38px] text-xs font-mono rounded-md border border-slate-200 bg-white" />
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-700 mb-1">Địa chỉ From</label>
                    <input value={smtpFrom} onChange={(e) => setSmtpFrom(e.target.value)} placeholder="you@gmail.com" className="w-full px-3 py-2 min-h-[38px] text-xs font-mono rounded-md border border-slate-200 bg-white" />
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-700 mb-1">Timeout (giây)</label>
                    <input type="number" min={1} max={120} value={smtpTimeout} onChange={(e) => setSmtpTimeout(e.target.value)} className="w-full px-3 py-2 min-h-[38px] text-xs font-mono rounded-md border border-slate-200 bg-white" />
                  </div>
                  <label className="flex items-center gap-2 text-xs text-slate-700 sm:col-span-2">
                    <input
                      type="checkbox"
                      checked={smtpUseTls}
                      onChange={(e) => setSmtpUseTls(e.target.checked)}
                      className="h-4 w-4 rounded border-slate-300 text-slate-900 cursor-pointer"
                    />
                    Bật STARTTLS
                  </label>
                </div>
                <div className="sm:col-span-2 flex flex-col sm:flex-row gap-2 items-stretch sm:items-end">
                  <div className="flex-1">
                    <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                      Email nhận test:
                    </label>
                    <input
                      type="email"
                      value={testTo}
                      onChange={(e) => setTestTo(e.target.value)}
                      placeholder="sv@student.edu.vn"
                      className="w-full px-3 py-2 min-h-[38px] text-xs rounded-md border border-slate-200 bg-white"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={handleSendTest}
                    disabled={isTesting}
                    className="px-4 py-2 min-h-[38px] text-xs font-semibold text-white bg-slate-900 hover:bg-slate-800 rounded-md disabled:opacity-50 cursor-pointer"
                  >
                    {isTesting ? "Đang gửi..." : "Gửi mail test"}
                  </button>
                </div>
                {testMsg && <p className="sm:col-span-2 text-xs text-slate-600">{testMsg}</p>}
              </div>
            </div>
            )}

            {activeTab === "auto" && (
            <div className="bg-white rounded-lg border border-slate-200 shadow-xs overflow-hidden">
              <div className="px-4 sm:px-6 py-4 border-b border-slate-200 bg-slate-50/50 flex flex-wrap items-center justify-between gap-2">
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

              <div className="p-4 sm:p-6 space-y-4">
                <div className="flex flex-col sm:flex-row items-stretch sm:items-end gap-3">
                  <div className="w-full sm:w-auto">
                    <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                      Ngày đánh giá chuyên cần:
                    </label>
                    <div className="relative">
                      <Calendar size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                      <input
                        type="date"
                        value={targetDate}
                        onChange={(e) => setTargetDate(e.target.value)}
                        className="w-full sm:w-auto pl-8 pr-3 py-2 sm:py-1.5 min-h-[38px] text-xs font-mono rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                      />
                    </div>
                  </div>

                  <div className="w-full sm:w-auto">
                    <button
                      type="button"
                      onClick={handleRunEvaluationNow}
                      disabled={isEvaluating}
                      className="flex items-center justify-center gap-2 px-4 py-2 min-h-[38px] text-xs font-semibold text-white bg-slate-900 hover:bg-slate-800 rounded-md transition-colors disabled:opacity-50 cursor-pointer w-full sm:w-auto shadow-xs"
                    >
                      {isEvaluating ? (
                        <Loader2 size={14} className="animate-spin" />
                      ) : (
                        <Play size={14} />
                      )}
                      <span>Chạy tính điểm ngay (Run Now)</span>
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
            )}
          </form>
        )}
      </div>
    </RoleGuard>
  );
}
