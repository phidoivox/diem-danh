"use client";

import React, { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { RoleGuard } from "@/features/shell";
import {
  AdminClass,
  downloadAdminConductExcel,
  getAdminClasses,
  getAdminClassConduct,
  ClassConductReport,
  ClassConductStudent,
} from "@/features/shell";
import { ClassConductTable } from "@/features/evaluation";
import { AttendanceHistoryModal, HistoryTarget } from "@/features/attendance";
import { Award, FileSpreadsheet, Loader2 } from "lucide-react";

export default function AdminConductPage() {
  const [selectedClassId, setSelectedClassId] = useState<number | "">("");
  const [month, setMonth] = useState<string>("");
  const [downloading, setDownloading] = useState(false);
  const [historyTarget, setHistoryTarget] = useState<HistoryTarget | null>(null);

  const classesQuery = useQuery({
    queryKey: ["admin-classes", 1, ""],
    queryFn: () => getAdminClasses({ page: 1, size: 100, q: "" }),
  });
  const classes: AdminClass[] = classesQuery.data?.items ?? [];

  const currentClass = classes.find((c) => c.id === Number(selectedClassId));

  const handleExport = async () => {
    if (selectedClassId === "" || !currentClass) return;
    try {
      setDownloading(true);
      await downloadAdminConductExcel(
        Number(selectedClassId),
        month || undefined,
        `diem_ren_luyen_${currentClass.class_code}${month ? `_${month}` : ""}.xlsx`,
      );
    } catch (err: unknown) {
      toast.error(err instanceof Error && err.message ? err.message : "Không thể xuất file Excel.");
    } finally {
      setDownloading(false);
    }
  };

  const conductQuery = useQuery({
    queryKey: ["admin-conduct", selectedClassId === "" ? 0 : Number(selectedClassId), month || "ALL"],
    queryFn: () => getAdminClassConduct(Number(selectedClassId), month || undefined),
    enabled: selectedClassId !== "",
  });
  const conductReport: ClassConductReport | null = conductQuery.data ?? null;
  const isLoadingConduct = conductQuery.isPending || conductQuery.isFetching;

  // Mặc định chọn lớp đầu tiên khi danh sách về.
  useEffect(() => {
    if (selectedClassId === "" && classes.length > 0) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- chọn mặc định lớp đầu tiên khi list về
      setSelectedClassId(classes[0].id);
    }
  }, [classes, selectedClassId]);

  return (
    <RoleGuard allowedRoles={["ADMIN"]}>
      <div className="space-y-4 sm:space-y-6 max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-200">
          <div>
            <h2 className="text-lg font-semibold text-slate-900 tracking-tight flex items-center gap-2">
              <Award size={20} className="text-slate-700" />
              Điểm rèn luyện theo lớp
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Điểm RL toàn trường + biến động trong lớp + xếp loại Xuất sắc → Kém
            </p>
          </div>

          <button
            type="button"
            onClick={handleExport}
            disabled={downloading || !conductReport || isLoadingConduct}
            className="inline-flex items-center justify-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-slate-900 hover:bg-slate-800 rounded-md transition-colors disabled:opacity-50 cursor-pointer shadow-xs"
          >
            {downloading ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <FileSpreadsheet size={16} className="text-emerald-400" />
            )}
            Xuất file Excel (.xlsx)
          </button>
        </div>

        {/* Class selector */}
        <div className="bg-white rounded-lg border border-slate-200 shadow-xs p-4 flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3">
          <span className="text-xs font-semibold text-slate-700">Xem chi tiết lớp:</span>
          <select
            value={selectedClassId}
            onChange={(e) => setSelectedClassId(e.target.value ? Number(e.target.value) : "")}
            className="w-full sm:w-auto px-3 py-1.5 text-xs rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900 sm:max-w-sm"
          >
            {classes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.class_code} - {c.course_name} (GV: {c.teacher_name})
              </option>
            ))}
          </select>
          <span className="text-xs font-semibold text-slate-700">Tháng:</span>
          <input
            type="month"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
            className="px-3 py-1.5 text-xs rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
          />
          {month && (
            <button type="button" onClick={() => setMonth("")} className="text-xs text-slate-500 underline underline-offset-2 hover:text-slate-800">
              Toàn kỳ
            </button>
          )}
        </div>

        <ClassConductTable
          report={conductReport}
          loading={isLoadingConduct}
          onOpenHistory={(st: ClassConductStudent) =>
            setHistoryTarget({
              studentId: st.student_id,
              studentCode: st.student_code,
              studentName: st.full_name,
              className: st.class_name,
            })
          }
        />
        <AttendanceHistoryModal
          isOpen={historyTarget !== null}
          onClose={() => setHistoryTarget(null)}
          classId={selectedClassId === "" ? null : Number(selectedClassId)}
          target={historyTarget}
          scope="admin"
        />
      </div>
    </RoleGuard>
  );
}
