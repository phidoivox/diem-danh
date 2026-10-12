"use client";

import React, { useState } from "react";
import { SearchInput } from "@/features/shell";
import { ClassConductReport, ClassConductStudent } from "@/features/shell";
import { getConductRank } from "./conduct-rank";
import { Award, History } from "lucide-react";

interface ClassConductTableProps {
  report: ClassConductReport | null;
  loading: boolean;
  onOpenHistory: (st: ClassConductStudent) => void;
}

const RANK_ORDER = ["Xuất sắc", "Tốt", "Khá", "Trung bình", "Yếu", "Kém"];

export function ClassConductTable({ report, loading, onOpenHistory }: ClassConductTableProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [rankFilter, setRankFilter] = useState<string>("ALL");

  const students = report?.students ?? [];
  const filtered = students.filter((st) => {
    const q = searchQuery.toLowerCase().trim();
    const matchSearch =
      !q ||
      st.student_code.toLowerCase().includes(q) ||
      st.full_name.toLowerCase().includes(q);
    const matchRank = rankFilter === "ALL" || st.conduct_rank === rankFilter;
    return matchSearch && matchRank;
  });

  const byRank = report?.summary.by_rank ?? {};

  return (
    <div className="space-y-3">
      {/* KPI phân bố rank */}
      {report && (
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 font-medium">
            <Award size={12} />
            Sĩ số <strong className="font-mono tabular-nums ml-1">{report.summary.total}</strong>
          </span>
          {RANK_ORDER.map((rank) =>
            (byRank[rank] ?? 0) > 0 ? (
              <span
                key={rank}
                className="inline-flex items-center px-2 py-0.5 rounded-full bg-white border border-slate-200 text-slate-600 font-medium"
              >
                {rank} <strong className="font-mono tabular-nums ml-1">{byRank[rank]}</strong>
              </span>
            ) : null,
          )}
          <span className="ml-auto font-mono tabular-nums text-slate-400">
            Đã chấm {report.evaluated_sessions}/{report.total_sessions} buổi
          </span>
        </div>
      )}

      {/* Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-2 p-3 bg-white rounded-lg border border-slate-200 shadow-sm">
        <SearchInput
          value={searchQuery}
          onChange={setSearchQuery}
          placeholder="Tìm theo MSSV, Họ tên..."
          ariaLabel="Tìm kiếm sinh viên trong bảng điểm rèn luyện"
          className="w-full sm:w-auto flex-1 sm:max-w-xs"
        />
        <div className="flex flex-wrap items-center gap-1">
          {["ALL", ...RANK_ORDER].map((rank) => (
            <button
              key={rank}
              type="button"
              onClick={() => setRankFilter(rank)}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                rankFilter === rank
                  ? "bg-slate-900 text-white shadow-xs"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {rank === "ALL" ? `Tất cả (${students.length})` : rank}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-600 uppercase tracking-wider">
              <tr>
                <th className="px-4 py-3 w-12 text-center">STT</th>
                <th className="px-4 py-3">Mã SV</th>
                <th className="px-4 py-3">Họ và tên</th>
                <th className="px-4 py-3 text-center">Điểm RL</th>
                <th className="px-4 py-3 text-center">Biến động lớp</th>
                <th className="px-4 py-3 text-center">Xếp loại</th>
                <th className="px-4 py-3 text-right">Lịch sử</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-xs text-slate-400">
                    Đang tải bảng điểm rèn luyện...
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-xs text-slate-400">
                    Không có sinh viên nào khớp điều kiện lọc.
                  </td>
                </tr>
              ) : (
                filtered.map((st, idx) => {
                  const rank = getConductRank(st.total_point, st.conduct_rank, st.is_officer);
                  return (
                    <tr key={st.student_id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="px-4 py-3 text-center text-xs text-slate-400 font-mono tabular-nums">
                        {idx + 1}
                      </td>
                      <td className="px-4 py-3 font-mono tabular-nums text-xs font-semibold text-slate-900">
                        {st.student_code}
                      </td>
                      <td className="px-4 py-3 font-medium text-slate-900">
                        {st.full_name}
                        {st.is_officer && (
                          <span className="ml-1.5 inline-flex items-center px-1.5 py-px rounded text-[10px] font-semibold border text-violet-700 bg-violet-50 border-violet-200">
                            Cán sự
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-center font-mono tabular-nums font-bold text-slate-900">
                        {st.total_point}
                      </td>
                      <td className="px-4 py-3 text-center font-mono tabular-nums text-xs">
                        {st.class_delta === 0 ? (
                          <span className="text-slate-400">±0</span>
                        ) : (
                          <span className={st.class_delta > 0 ? "text-emerald-600" : "text-rose-600"}>
                            {st.class_delta > 0 ? `+${st.class_delta}` : st.class_delta}
                            <span className="text-slate-400">/{st.class_entries}</span>
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold border ${rank.color}`}
                        >
                          {rank.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          type="button"
                          onClick={() => onOpenHistory(st)}
                          title="Xem lịch sử điểm danh trong lớp"
                          className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-slate-600 border border-slate-200 rounded-md hover:bg-slate-50 transition-colors"
                        >
                          <History size={13} />
                          <span className="hidden sm:inline">Lịch sử</span>
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
