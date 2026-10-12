"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { RoleGuard } from "@/features/shell";
import { SearchInput } from "@/features/shell";
import {
  getTeacherHomeroomClasses,
  getTeacherHomeroomStudents,
  setTeacherHomeroomOfficer,
  HomeroomClass,
  HomeroomStudent,
} from "@/features/shell";
import { getConductRank } from "@/features/evaluation";
import { Award, Loader2, Users } from "lucide-react";

function HomeroomOfficerContent() {
  const searchParams = useSearchParams();
  const urlClassId = searchParams.get("class_id");
  const queryClient = useQueryClient();

  const [selectedClassId, setSelectedClassId] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [savingId, setSavingId] = useState<number | null>(null);

  const classesQuery = useQuery({
    queryKey: ["teacher-homeroom-classes"],
    queryFn: getTeacherHomeroomClasses,
  });
  const classes: HomeroomClass[] = classesQuery.data ?? [];

  const studentsQuery = useQuery({
    queryKey: ["teacher-homeroom-students", selectedClassId],
    queryFn: () => getTeacherHomeroomStudents(selectedClassId!),
    enabled: selectedClassId !== null,
  });
  const students: HomeroomStudent[] = studentsQuery.data ?? [];
  const loadingStudents = studentsQuery.isPending || studentsQuery.isFetching;

  useEffect(() => {
    if (classes.length > 0 && selectedClassId === null) {
      const matched = urlClassId
        ? classes.find((c) => c.id === Number(urlClassId))
        : null;
      // eslint-disable-next-line react-hooks/set-state-in-effect -- chọn lớp mặc định khi list về
      setSelectedClassId(matched ? matched.id : classes[0].id);
    }
  }, [classes, selectedClassId, urlClassId]);

  const filtered = students.filter((st) => {
    const q = searchQuery.toLowerCase().trim();
    return (
      !q ||
      st.user_code.toLowerCase().includes(q) ||
      st.full_name.toLowerCase().includes(q)
    );
  });
  const officerCount = students.filter((st) => st.is_officer).length;

  const handleToggle = async (st: HomeroomStudent) => {
    if (selectedClassId === null || savingId !== null) return;
    setSavingId(st.id);
    try {
      await setTeacherHomeroomOfficer(selectedClassId, st.id, !st.is_officer);
      await queryClient.invalidateQueries({
        queryKey: ["teacher-homeroom-students", selectedClassId],
      });
      toast.success(
        !st.is_officer
          ? `Đã gán ${st.full_name} làm cán sự`
          : `Đã bỏ cờ cán sự của ${st.full_name}`,
      );
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Không thể cập nhật cờ cán sự.");
    } finally {
      setSavingId(null);
    }
  };

  return (
    <div className="p-4 sm:p-6 max-w-7xl mx-auto space-y-4 sm:space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2 text-slate-500 text-xs font-semibold uppercase tracking-wider mb-1">
            <Award size={15} />
            <span>Phân hệ Giảng viên · Chủ nhiệm</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            Ban cán sự lớp sinh hoạt
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Chỉ cán sự có điểm ≥ 90 mới đạt Xuất sắc; sinh viên thường trần loại Tốt
          </p>
        </div>
      </div>

      {/* Class selector */}
      <div className="p-4 bg-white rounded-lg border border-slate-200 shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between flex-wrap gap-3">
        <div className="flex flex-col sm:flex-row sm:items-center gap-3 w-full sm:w-auto">
          <label
            htmlFor="select-homeroom"
            className="text-xs font-semibold text-slate-700 uppercase tracking-wider shrink-0"
          >
            Lớp sinh hoạt:
          </label>
          <select
            id="select-homeroom"
            value={selectedClassId || ""}
            onChange={(e) => setSelectedClassId(Number(e.target.value))}
            disabled={classesQuery.isPending || classes.length === 0}
            className="w-full sm:w-auto px-3 py-2 text-sm rounded-md border border-slate-200 bg-slate-50 text-slate-900 font-medium focus:outline-none focus:ring-1 focus:ring-slate-400 sm:min-w-[260px]"
          >
            {classes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.class_code}{c.faculty ? ` · ${c.faculty}` : ""}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <Users size={14} />
          <span className="font-mono tabular-nums">
            {students.length} SV · {officerCount} cán sự
          </span>
        </div>
      </div>

      {classesQuery.isPending ? (
        <div className="p-12 text-center bg-white rounded-lg border border-slate-200 text-xs text-slate-400">
          Đang tải lớp chủ nhiệm...
        </div>
      ) : classes.length === 0 ? (
        <div className="p-12 text-center bg-white rounded-lg border border-slate-200">
          <h3 className="text-sm font-semibold text-slate-800">Bạn chưa chủ nhiệm lớp nào</h3>
          <p className="text-xs text-slate-500 mt-1">
            Liên hệ admin gán GVCN để quản lý ban cán sự.
          </p>
        </div>
      ) : (
        <>
          <div className="p-3 bg-white rounded-lg border border-slate-200 shadow-sm">
            <SearchInput
              value={searchQuery}
              onChange={setSearchQuery}
              placeholder="Tìm theo MSSV, Họ tên..."
              ariaLabel="Tìm kiếm sinh viên lớp sinh hoạt"
              className="w-full sm:max-w-xs"
            />
          </div>
          <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                  <tr>
                    <th className="px-4 py-3 w-12 text-center">STT</th>
                    <th className="px-4 py-3">Mã SV</th>
                    <th className="px-4 py-3">Họ và tên</th>
                    <th className="px-4 py-3 text-center">Điểm RL</th>
                    <th className="px-4 py-3 text-center">Xếp loại</th>
                    <th className="px-4 py-3 text-center">Cán sự</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {loadingStudents ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-12 text-center text-xs text-slate-400">
                        <Loader2 size={20} className="animate-spin mx-auto mb-1" />
                        Đang tải sinh viên...
                      </td>
                    </tr>
                  ) : filtered.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-12 text-center text-xs text-slate-400">
                        Không có sinh viên nào khớp.
                      </td>
                    </tr>
                  ) : (
                    filtered.map((st, idx) => {
                      const rank = getConductRank(st.total_point, null, st.is_officer);
                      return (
                        <tr key={st.id} className="hover:bg-slate-50/70 transition-colors">
                          <td className="px-4 py-3 text-center text-xs text-slate-400 font-mono tabular-nums">
                            {idx + 1}
                          </td>
                          <td className="px-4 py-3 font-mono tabular-nums text-xs font-semibold text-slate-900">
                            {st.user_code}
                          </td>
                          <td className="px-4 py-3 font-medium text-slate-900">{st.full_name}</td>
                          <td className="px-4 py-3 text-center font-mono tabular-nums font-bold text-slate-900">
                            {st.total_point}
                          </td>
                          <td className="px-4 py-3 text-center">
                            <span
                              className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold border ${rank.color}`}
                            >
                              {rank.label}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-center">
                            <button
                              type="button"
                              role="switch"
                              aria-checked={st.is_officer}
                              aria-label={`Cán sự ${st.full_name}`}
                              disabled={savingId === st.id}
                              onClick={() => handleToggle(st)}
                              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors cursor-pointer disabled:opacity-50 ${
                                st.is_officer ? "bg-violet-600" : "bg-slate-200"
                              }`}
                            >
                              <span
                                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                                  st.is_officer ? "translate-x-6" : "translate-x-1"
                                }`}
                              />
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
        </>
      )}
    </div>
  );
}

export default function TeacherHomeroomPage() {
  return (
    <RoleGuard allowedRoles={["TEACHER"]}>
      <Suspense
        fallback={
          <div className="p-12 text-center bg-slate-50">
            <div className="flex items-center justify-center gap-3 text-slate-500 text-sm">
              <span className="w-5 h-5 rounded-full border-2 border-slate-300 border-t-slate-800 animate-spin" />
              <span>Đang tải ban cán sự...</span>
            </div>
          </div>
        }
      >
        <HomeroomOfficerContent />
      </Suspense>
    </RoleGuard>
  );
}
