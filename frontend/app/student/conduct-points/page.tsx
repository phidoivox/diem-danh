"use client";

import React, { useState, useEffect, useMemo } from "react";
import { RoleGuard } from "@/components/layout/role-guard";
import { getStudentConductLedger, StudentConductLedger } from "@/lib/api";
import {
  Award,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Clock,
  ShieldCheck,
  AlertTriangle,
  FileText,
  Calendar,
  Filter,
} from "lucide-react";

export default function StudentConductPointsPage() {
  const [ledger, setLedger] = useState<StudentConductLedger>({
    total_point: 100,
    items: [],
  });
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [reasonFilter, setReasonFilter] = useState<string>("ALL");

  const fetchLedger = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getStudentConductLedger();
      setLedger(data);
    } catch (err: any) {
      setError(err?.message || "Không thể tải sổ cái điểm rèn luyện.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLedger();
  }, []);

  const totalPoint = ledger.total_point;

  // Grade classification
  const pointLevel = useMemo(() => {
    if (totalPoint >= 90) {
      return {
        label: "Xuất sắc",
        color: "text-emerald-700 bg-emerald-50 border-emerald-200",
        description: "Duy trì tác phong chuẩn mực và đi học đầy đủ.",
      };
    }
    if (totalPoint >= 80) {
      return {
        label: "Tốt",
        color: "text-sky-700 bg-sky-50 border-sky-200",
        description: "Điểm chuyên cần và nề nếp đạt chuẩn loại Tốt.",
      };
    }
    if (totalPoint >= 65) {
      return {
        label: "Khá",
        color: "text-amber-700 bg-amber-50 border-amber-200",
        description: "Cần lưu ý tuân thủ giờ giấc và quy định đồng phục.",
      };
    }
    return {
      label: "Cảnh báo học vụ",
      color: "text-rose-700 bg-rose-50 border-rose-200",
      description: "Điểm chuyên cần thấp! Nguy cơ bị cấm thi nếu tiếp tục vắng.",
    };
  }, [totalPoint]);

  // Aggregate stats from ledger
  const stats = useMemo(() => {
    let plusCount = 0;
    let minusCount = 0;
    let totalAdded = 0;
    let totalDeducted = 0;

    ledger.items.forEach((item) => {
      if (item.point_delta > 0) {
        plusCount++;
        totalAdded += item.point_delta;
      } else if (item.point_delta < 0) {
        minusCount++;
        totalDeducted += Math.abs(item.point_delta);
      }
    });

    return { plusCount, minusCount, totalAdded, totalDeducted };
  }, [ledger.items]);

  // Filter items
  const filteredItems = useMemo(() => {
    if (reasonFilter === "ALL") return ledger.items;
    if (reasonFilter === "PLUS") return ledger.items.filter((i) => i.point_delta > 0);
    if (reasonFilter === "MINUS") return ledger.items.filter((i) => i.point_delta < 0);
    return ledger.items.filter((i) => i.reason_code === reasonFilter);
  }, [ledger.items, reasonFilter]);

  const formatTimestamp = (ts: string) => {
    try {
      const d = new Date(ts);
      const dd = String(d.getDate()).padStart(2, "0");
      const mm = String(d.getMonth() + 1).padStart(2, "0");
      const yyyy = d.getFullYear();
      const hh = String(d.getHours()).padStart(2, "0");
      const min = String(d.getMinutes()).padStart(2, "0");
      return `${hh}:${min} - ${dd}/${mm}/${yyyy}`;
    } catch {
      return ts;
    }
  };

  const getReasonLabel = (code: string) => {
    switch (code) {
      case "ATTENDANCE_FULL":
        return "Chuyên cần & Đồng phục tốt";
      case "LATE_CHECKIN":
        return "Đi học muộn";
      case "UNIFORM_VIOLATION":
        return "Vi phạm đồng phục";
      case "UNEXCUSED_ABSENCE":
        return "Vắng không phép";
      case "HALF_ABSENT_NO_CHECKOUT":
        return "Quên Check-out ca học";
      case "LEAVE_REFUND":
        return "Hoàn điểm phép duyệt muộn";
      case "INITIAL":
        return "Điểm chuẩn đầu kỳ";
      default:
        return code;
    }
  };

  return (
    <RoleGuard allowedRoles={["STUDENT", "ADMIN"]}>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-200">
          <div>
            <h1 className="text-lg font-semibold text-slate-900 tracking-tight">
              Điểm Chuyên cần & Sổ cái Biến động
            </h1>
            <p className="text-xs text-slate-500 mt-0.5">
              Theo dõi biến động điểm rèn luyện, lịch sử thưởng/phạt và cơ chế hoàn điểm tự động
            </p>
          </div>
          <button
            onClick={fetchLedger}
            disabled={loading}
            className="h-8 px-3 rounded-md text-xs font-medium border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 transition-colors inline-flex items-center gap-1.5 shadow-sm self-start sm:self-auto"
          >
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
            <span>Làm mới</span>
          </button>
        </div>

        {/* Big KPI Card & Metric summary */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Main Current Score Hero Card */}
          <div className="lg:col-span-1 p-6 rounded-lg bg-white border border-slate-200 shadow-sm flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Điểm Chuyên cần Hiện tại
                </span>
                <span className={`px-2 py-0.5 rounded text-[11px] font-semibold border ${pointLevel.color}`}>
                  {pointLevel.label}
                </span>
              </div>

              <div className="mt-4 flex items-baseline gap-2">
                <span className="text-5xl font-bold text-slate-900 font-mono tabular-nums tracking-tight">
                  {totalPoint}
                </span>
                <span className="text-sm font-medium text-slate-400 font-mono">/ 100 điểm</span>
              </div>

              <p className="text-xs text-slate-500 mt-2">
                {pointLevel.description}
              </p>
            </div>

            {/* Progress bar */}
            <div className="mt-6 pt-4 border-t border-slate-100">
              <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1 font-mono">
                <span>0</span>
                <span>Thang điểm tối đa: 100</span>
              </div>
              <div className="w-full h-2 rounded-full bg-slate-100 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    totalPoint >= 80
                      ? "bg-emerald-600"
                      : totalPoint >= 65
                      ? "bg-amber-500"
                      : "bg-rose-500"
                  }`}
                  style={{ width: `${Math.max(0, Math.min(100, totalPoint))}%` }}
                />
              </div>
            </div>
          </div>

          {/* Sub-KPI Highlights */}
          <div className="lg:col-span-2 grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="p-5 rounded-lg bg-white border border-slate-200 shadow-sm flex flex-col justify-between">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium uppercase tracking-wider text-slate-500">
                  Lượt cộng điểm
                </span>
                <div className="w-7 h-7 rounded bg-emerald-50 text-emerald-700 flex items-center justify-center">
                  <TrendingUp size={15} />
                </div>
              </div>
              <div className="mt-3">
                <div className="text-2xl font-bold text-emerald-700 font-mono tabular-nums">
                  +{stats.totalAdded} <span className="text-xs font-normal text-slate-500">điểm</span>
                </div>
                <p className="text-xs text-slate-500 mt-1">
                  Được ghi nhận từ <span className="font-mono font-medium text-slate-800">{stats.plusCount}</span> lượt chuyên cần tốt & hoàn điểm
                </p>
              </div>
            </div>

            <div className="p-5 rounded-lg bg-white border border-slate-200 shadow-sm flex flex-col justify-between">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium uppercase tracking-wider text-slate-500">
                  Lượt trừ điểm
                </span>
                <div className="w-7 h-7 rounded bg-rose-50 text-rose-700 flex items-center justify-center">
                  <TrendingDown size={15} />
                </div>
              </div>
              <div className="mt-3">
                <div className="text-2xl font-bold text-rose-700 font-mono tabular-nums">
                  -{stats.totalDeducted} <span className="text-xs font-normal text-slate-500">điểm</span>
                </div>
                <p className="text-xs text-slate-500 mt-1">
                  Bị trừ do <span className="font-mono font-medium text-slate-800">{stats.minusCount}</span> lần vi phạm đồng phục, muộn hoặc vắng
                </p>
              </div>
            </div>

            <div className="p-5 rounded-lg bg-white border border-slate-200 shadow-sm sm:col-span-2">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded bg-slate-100 flex items-center justify-center text-slate-700 shrink-0 mt-0.5">
                  <ShieldCheck size={18} />
                </div>
                <div className="text-xs text-slate-600 leading-relaxed">
                  <span className="font-semibold text-slate-900 block mb-0.5">
                    Quy chế tính điểm & hoàn điểm chuyên cần tự động
                  </span>
                  Mỗi sinh viên bắt đầu với 100 điểm. Hệ thống AI & Cron 23h59 tự động đánh giá: cộng 2 điểm khi đi học đúng giờ và có đồng phục; trừ điểm khi muộn (-1), vi phạm đồng phục (-1) hoặc vắng (-5). Nếu nộp đơn xin nghỉ phép hợp lệ được giảng viên duyệt bổ sung, hệ thống sẽ tự động tạo giao dịch hoàn điểm (`LEAVE_REFUND`).
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Filter Toolbar */}
        <div className="p-3 bg-white rounded-lg border border-slate-200 shadow-sm flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Filter size={14} className="text-slate-400" />
            <span className="text-xs text-slate-600 font-medium">Lọc biến động:</span>
            <div className="inline-flex rounded-md p-0.5 bg-slate-100 border border-slate-200 ml-1">
              <button
                type="button"
                onClick={() => setReasonFilter("ALL")}
                className={`px-2.5 py-1 text-xs font-medium rounded ${
                  reasonFilter === "ALL"
                    ? "bg-white text-slate-900 shadow-xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Tất cả ({ledger.items.length})
              </button>
              <button
                type="button"
                onClick={() => setReasonFilter("PLUS")}
                className={`px-2.5 py-1 text-xs font-medium rounded ${
                  reasonFilter === "PLUS"
                    ? "bg-white text-emerald-700 shadow-xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Cộng điểm ({stats.plusCount})
              </button>
              <button
                type="button"
                onClick={() => setReasonFilter("MINUS")}
                className={`px-2.5 py-1 text-xs font-medium rounded ${
                  reasonFilter === "MINUS"
                    ? "bg-white text-rose-700 shadow-xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Trừ điểm ({stats.minusCount})
              </button>
            </div>
          </div>

          <div className="text-xs text-slate-500 font-mono">
            Hiển thị <span className="font-semibold text-slate-900">{filteredItems.length}</span> giao dịch
          </div>
        </div>

        {/* Ledger Table */}
        <div className="bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden">
          {loading ? (
            <div className="p-12 text-center">
              <RefreshCw size={24} className="animate-spin text-slate-400 mx-auto mb-2" />
              <p className="text-xs text-slate-500">Đang tải sổ cái biến động điểm...</p>
            </div>
          ) : error ? (
            <div className="p-6 text-center text-rose-700 bg-rose-50 text-xs">
              {error}
            </div>
          ) : filteredItems.length === 0 ? (
            <div className="p-12 text-center">
              <Award size={36} className="text-slate-300 mx-auto mb-2" />
              <h3 className="text-sm font-semibold text-slate-800">Chưa có bản ghi biến động</h3>
              <p className="text-xs text-slate-500 mt-1">
                Lịch sử cộng hoặc trừ điểm chuyên cần sẽ được ghi lại tại đây sau mỗi phiên đánh giá.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50/75 border-b border-slate-200 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                  <tr>
                    <th className="px-4 py-3 font-mono">Thời gian</th>
                    <th className="px-4 py-3 font-mono">Biến động</th>
                    <th className="px-4 py-3 font-mono">Mã lý do</th>
                    <th className="px-4 py-3">Loại biến động</th>
                    <th className="px-4 py-3">Diễn giải chi tiết</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 text-slate-700">
                  {filteredItems.map((item) => {
                    const isPositive = item.point_delta > 0;
                    return (
                      <tr key={item.id} className="hover:bg-slate-50/70 transition-colors">
                        {/* Timestamp */}
                        <td className="px-4 py-3 font-mono tabular-nums text-slate-600 whitespace-nowrap">
                          {formatTimestamp(item.created_at)}
                        </td>

                        {/* Point Delta */}
                        <td className="px-4 py-3 font-mono tabular-nums whitespace-nowrap">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${
                              isPositive
                                ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                : "bg-rose-50 text-rose-700 border border-rose-200"
                            }`}
                          >
                            {isPositive ? `+${item.point_delta}` : item.point_delta} điểm
                          </span>
                        </td>

                        {/* Reason Code */}
                        <td className="px-4 py-3 font-mono text-[11px] text-slate-500 whitespace-nowrap">
                          {item.reason_code}
                        </td>

                        {/* Friendly Category */}
                        <td className="px-4 py-3 font-medium text-slate-800 whitespace-nowrap">
                          {getReasonLabel(item.reason_code)}
                        </td>

                        {/* Description */}
                        <td className="px-4 py-3 text-slate-600">
                          {item.description || "--"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </RoleGuard>
  );
}
