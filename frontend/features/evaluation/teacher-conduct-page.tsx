"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { RoleGuard } from "@/features/shell";
import { toast } from "sonner";
import {
  downloadTeacherConductExcel,
  getTeacherClasses,
  getTeacherClassConduct,
  TeacherClass,
  ClassConductReport,
  ClassConductStudent,
} from "@/features/shell";
import { ClassConductTable } from "./class-conduct-table";
import { AttendanceHistoryModal, HistoryTarget } from "@/features/attendance";
import { Award, FileSpreadsheet, Loader2, RefreshCw } from "lucide-react";

function TeacherConductContent() {
  const searchParams = useSearchParams();
  const urlClassId = searchParams.get("class_id");

  const [selectedClassId, setSelectedClassId] = useState<number | null>(null);
  const [month, setMonth] = useState<string>("");
  const [downloading, setDownloading] = useState(false);
  const [historyTarget, setHistoryTarget] = useState<HistoryTarget | null>(null);

  const classesQuery = useQuery({
    queryKey: ["teacher-classes"],
    queryFn: getTeacherClasses,
  });
  const classes: TeacherClass[] = classesQuery.data ?? [];
  const loadingClasses = classesQuery.isPending;
  const classesError = classesQuery.isError
    ? classesQuery.error instanceof Error
      ? classesQuery.error.message
      : "Không thể tải danh sách lớp học phần."
    : null;

  const conductQuery = useQuery({
    queryKey: ["teacher-conduct", selectedClassId, month || "ALL"],
    queryFn: () => getTeacherClassConduct(selectedClassId!, month || undefined),
    enabled: selectedClassId !== null,
  });
  const conductReport: ClassConductReport | null = conductQuery.data ?? null;
  const loadingConduct = conductQuery.isPending || conductQuery.isFetching;
  const conductError = conductQuery.isError
    ? conductQuery.error instanceof Error
      ? conductQuery.error.message
      : "Không thể tải bảng điểm rèn luyện."
    : null;

  // Mặc định chọn lớp theo ?class_id= hoặc lớp đầu tiên khi classes về.
  // Chỉ chấp nhận id thuộc lớp mình đảm nhận; id lạ (dán tay URL) -> fallback
  // lớp đầu + báo rõ, backend cũng 403 nên không lọt dữ liệu lớp người khác.
  const [rejectedClassId, setRejectedClassId] = useState<string | null>(null);
  useEffect(() => {
    if (classes.length === 0) return;
    if (selectedClassId === null) {
      const matched = urlClassId
        ? classes.find((c) => c.id === Number(urlClassId))
        : null;
      if (urlClassId && !matched) {
        // eslint-disable-next-line react-hooks/set-state-in-effect -- báo id lạ 1 lần khi list về
        setRejectedClassId(urlClassId);
      }
      // eslint-disable-next-line react-hooks/set-state-in-effect -- chọn lớp mặc định khi list về
      setSelectedClassId(matched ? matched.id : classes[0].id);
    } else if (!classes.some((c) => c.id === selectedClassId)) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- ép về lớp mình khi id bị chèn ngoài list
      setRejectedClassId(String(selectedClassId));
      setSelectedClassId(classes[0].id);
    }
  }, [classes, selectedClassId, urlClassId]);

  const currentClass = classes.find((c) => c.id === selectedClassId);
  const error = classesError ?? conductError;

  const handleExport = async () => {
    if (selectedClassId === null || !currentClass) return;
    try {
      setDownloading(true);
      await downloadTeacherConductExcel(
        selectedClassId,
        month || undefined,
        `diem_ren_luyen_${currentClass.class_code}${month ? `_${month}` : ""}.xlsx`,
      );
    } catch (err: unknown) {
      toast.error(err instanceof Error && err.message ? err.message : "Không thể xuất file Excel.");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="p-4 sm:p-6 max-w-7xl mx-auto space-y-4 sm:space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2 text-slate-500 text-xs font-semibold uppercase tracking-wider mb-1">
            <Award size={15} />
            <span>Phân hệ Giảng viên</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            Điểm rèn luyện theo lớp
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Điểm rèn luyện và xếp loại Xuất sắc → Kém của các lớp bạn đảm nhận
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex flex-wrap items-center gap-2.5 self-start sm:self-auto">
          <button
            type="button"
            onClick={handleExport}
            disabled={downloading || !conductReport || loadingConduct}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-md text-sm font-medium text-white bg-slate-900 hover:bg-slate-800 shadow-sm transition-colors disabled:opacity-50"
          >
            {downloading ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <FileSpreadsheet size={15} className="text-emerald-400" />
            )}
            <span>Xuất file Excel (.xlsx)</span>
          </button>
        </div>
      </div>

      {/* Class Selector Bar */}
      <div className="p-4 bg-white rounded-lg border border-slate-200 shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between flex-wrap gap-3 sm:gap-4">
        <div className="flex flex-col sm:flex-row sm:items-center gap-3 w-full sm:w-auto">
          <label
            htmlFor="select-class"
            className="text-xs font-semibold text-slate-700 uppercase tracking-wider shrink-0"
          >
            Chọn lớp học phần:
          </label>
          <select
            id="select-class"
            value={selectedClassId || ""}
            onChange={(e) => setSelectedClassId(Number(e.target.value))}
            disabled={loadingClasses || classes.length === 0}
            className="w-full sm:w-auto px-3 py-2 text-sm rounded-md border border-slate-200 bg-slate-50 text-slate-900 font-medium focus:outline-none focus:ring-1 focus:ring-slate-400 sm:min-w-[260px]"
          >
            {classes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.class_code} - {c.course_name} ({c.semester})
              </option>
            ))}
          </select>
          <label htmlFor="filter-month" className="text-xs font-semibold text-slate-700 uppercase tracking-wider shrink-0">
            Tháng:
          </label>
          <input
            id="filter-month"
            type="month"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
            className="px-3 py-2 text-sm rounded-md border border-slate-200 bg-slate-50 text-slate-900 font-medium focus:outline-none focus:ring-1 focus:ring-slate-400"
          />
          {month && (
            <button type="button" onClick={() => setMonth("")} className="text-xs text-slate-500 underline underline-offset-2 hover:text-slate-800">
              Toàn kỳ
            </button>
          )}
        </div>

        {currentClass && conductReport && (
          <div className="flex items-center gap-4 text-xs text-slate-500 font-mono tabular-nums">
            <span>
              Đã chấm: <strong className="text-slate-800">{conductReport.evaluated_sessions}</strong>/
              {conductReport.total_sessions} buổi
            </span>
            <span>•</span>
            <span>
              Sĩ số: <strong className="text-slate-800">{currentClass.student_count}</strong> SV
            </span>
          </div>
        )}
      </div>

      {/* Error Notice */}
      {rejectedClassId && (
        <div className="p-4 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-sm">
          Lớp #{rejectedClassId} không thuộc phân công của bạn — đã chuyển về lớp đầu tiên.
        </div>
      )}
      {error && (
        <div className="p-4 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-sm flex items-center gap-2">
          <RefreshCw size={15} />
          <span>{error}</span>
        </div>
      )}

      <ClassConductTable
        report={conductReport}
        loading={loadingConduct}
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
        classId={selectedClassId}
        target={historyTarget}
      />
    </div>
  );
}

export default function TeacherConductPage() {
  return (
    <RoleGuard allowedRoles={["TEACHER"]}>
      <Suspense
        fallback={
          <div className="p-12 text-center bg-slate-50">
            <div className="flex items-center justify-center gap-3 text-slate-500 text-sm">
              <span className="w-5 h-5 rounded-full border-2 border-slate-300 border-t-slate-800 animate-spin" />
              <span>Đang tải bảng điểm rèn luyện...</span>
            </div>
          </div>
        }
      >
        <TeacherConductContent />
      </Suspense>
    </RoleGuard>
  );
}
