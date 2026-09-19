"use client";

import React, { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { RoleGuard } from "@/components/layout/role-guard";
import {
  getTeacherClasses,
  downloadTeacherExamBanExcel,
  TeacherClass,
} from "@/lib/api";
import {
  BookOpen,
  Users,
  Calendar,
  Radio,
  FileSpreadsheet,
  AlertTriangle,
  Search,
  RefreshCw,
  LayoutGrid,
  List as ListIcon,
  Loader2,
  CheckCircle2,
  Clock,
  ExternalLink,
} from "lucide-react";

export default function TeacherClassesPage() {
  const [classes, setClasses] = useState<TeacherClass[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState<string>("");
  const [selectedSemester, setSelectedSemester] = useState<string>("ALL");
  const [viewMode, setViewMode] = useState<"grid" | "table">("grid");
  const [downloadingId, setDownloadingId] = useState<number | null>(null);

  const fetchClasses = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getTeacherClasses();
      setClasses(data);
    } catch (err: any) {
      setError(err?.message || "Không thể tải danh sách lớp học phần.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchClasses();
  }, []);

  // Distinct semesters for filter
  const semesters = useMemo(() => {
    const s = new Set<string>();
    classes.forEach((c) => {
      if (c.semester) s.add(c.semester);
    });
    return Array.from(s);
  }, [classes]);

  // Filtered classes
  const filteredClasses = useMemo(() => {
    return classes.filter((c) => {
      const matchSearch =
        c.class_code.toLowerCase().includes(searchQuery.toLowerCase()) ||
        c.course_name.toLowerCase().includes(searchQuery.toLowerCase());
      const matchSemester =
        selectedSemester === "ALL" || c.semester === selectedSemester;
      return matchSearch && matchSemester;
    });
  }, [classes, searchQuery, selectedSemester]);

  // Statistics
  const stats = useMemo(() => {
    const totalClasses = classes.length;
    const totalStudents = classes.reduce((sum, c) => sum + (c.student_count || 0), 0);
    return { totalClasses, totalStudents };
  }, [classes]);

  const handleDownloadExcel = async (c: TeacherClass) => {
    try {
      setDownloadingId(c.id);
      await downloadTeacherExamBanExcel(c.id, `cam_thi_${c.class_code}.xlsx`);
    } catch (err: any) {
      toast.error(err?.message || "Lỗi khi tải file báo cáo Excel");
    } finally {
      setDownloadingId(null);
    }
  };

  return (
    <RoleGuard allowedRoles={["TEACHER"]}>
      <div className="p-6 max-w-7xl mx-auto space-y-6">
        {/* Top Header */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-200 pb-5">
          <div>
            <div className="flex items-center gap-2 text-slate-500 text-xs font-semibold uppercase tracking-wider mb-1">
              <BookOpen size={15} />
              <span>Phân hệ Giảng viên</span>
            </div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
              Lớp học phần phụ trách
            </h1>
            <p className="text-sm text-slate-500 mt-0.5">
              Theo dõi sĩ số trực tiếp ca học, quản lý vắng phép và xuất báo cáo cấm thi
            </p>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              onClick={fetchClasses}
              disabled={loading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium text-slate-700 bg-white hover:bg-slate-50 border border-slate-200 shadow-sm transition-colors disabled:opacity-50"
            >
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
              <span>Làm mới</span>
            </button>
          </div>
        </div>

        {/* Quick Stats Banner */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <div className="p-4 bg-white rounded-lg border border-slate-200 shadow-sm flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">
                Tổng số lớp phụ trách
              </p>
              <p className="text-2xl font-bold font-mono tabular-nums text-slate-900 mt-1">
                {stats.totalClasses}
              </p>
            </div>
            <div className="w-10 h-10 rounded-md bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-600">
              <BookOpen size={20} />
            </div>
          </div>

          <div className="p-4 bg-white rounded-lg border border-slate-200 shadow-sm flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">
                Tổng sinh viên giảng dạy
              </p>
              <p className="text-2xl font-bold font-mono tabular-nums text-slate-900 mt-1">
                {stats.totalStudents}
              </p>
            </div>
            <div className="w-10 h-10 rounded-md bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-600">
              <Users size={20} />
            </div>
          </div>

          <div className="p-4 bg-white rounded-lg border border-slate-200 shadow-sm flex items-center justify-between sm:col-span-2 lg:col-span-1">
            <div>
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">
                Điểm danh
              </p>
              <div className="flex items-center gap-2 mt-1.5">
                <span className="text-sm font-semibold text-slate-800">
                  Giảng viên điểm danh thủ công
                </span>
              </div>
            </div>
            <div className="w-10 h-10 rounded-md bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-600">
              <Radio size={20} />
            </div>
          </div>
        </div>

        {/* Toolbar: Search, Filters, View toggle */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 p-3 bg-white rounded-lg border border-slate-200 shadow-sm">
          <div className="flex flex-1 items-center gap-2.5 w-full sm:w-auto">
            {/* Search input */}
            <div className="relative flex-1 sm:max-w-xs">
              <Search
                size={16}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
              />
              <input
                type="text"
                placeholder="Tìm mã lớp, tên môn học..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 text-sm rounded-md border border-slate-200 bg-slate-50/50 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400 focus:border-slate-400"
              />
            </div>

            {/* Semester filter */}
            {semesters.length > 0 && (
              <select
                value={selectedSemester}
                onChange={(e) => setSelectedSemester(e.target.value)}
                className="px-3 py-1.5 text-sm rounded-md border border-slate-200 bg-slate-50/50 text-slate-800 focus:outline-none focus:ring-1 focus:ring-slate-400"
              >
                <option value="ALL">Tất cả học kỳ</option>
                {semesters.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div className="flex items-center gap-2 self-end sm:self-auto">
            <span className="text-xs text-slate-500 font-mono tabular-nums mr-1">
              Hiển thị {filteredClasses.length}/{classes.length} lớp
            </span>
            <div className="flex items-center border border-slate-200 rounded-md p-0.5 bg-slate-50">
              <button
                type="button"
                onClick={() => setViewMode("grid")}
                className={`p-1 rounded ${
                  viewMode === "grid"
                    ? "bg-white text-slate-900 shadow-xs"
                    : "text-slate-500 hover:text-slate-700"
                }`}
                title="Dạng lưới thẻ"
              >
                <LayoutGrid size={15} />
              </button>
              <button
                type="button"
                onClick={() => setViewMode("table")}
                className={`p-1 rounded ${
                  viewMode === "table"
                    ? "bg-white text-slate-900 shadow-xs"
                    : "text-slate-500 hover:text-slate-700"
                }`}
                title="Dạng bảng"
              >
                <ListIcon size={15} />
              </button>
            </div>
          </div>
        </div>

        {/* Error Notice */}
        {error && (
          <div className="p-4 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-sm flex items-center justify-between">
            <span>{error}</span>
            <button
              onClick={fetchClasses}
              className="text-xs font-semibold underline hover:no-underline ml-4"
            >
              Thử lại
            </button>
          </div>
        )}

        {/* Loading Skeleton */}
        {loading && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-48 rounded-lg bg-slate-100 border border-slate-200 animate-pulse"
              />
            ))}
          </div>
        )}

        {/* Empty State */}
        {!loading && filteredClasses.length === 0 && (
          <div className="p-12 text-center bg-white rounded-lg border border-slate-200 shadow-sm">
            <BookOpen size={40} className="mx-auto text-slate-300 mb-3" />
            <h3 className="text-base font-semibold text-slate-800">
              Không tìm thấy lớp học phần nào
            </h3>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
              {searchQuery
                ? "Không có lớp học phần nào khớp với từ khóa tìm kiếm của bạn."
                : "Hiện tại bạn chưa được phân công phụ trách lớp học phần nào."}
            </p>
          </div>
        )}

        {/* Content View: Grid Mode */}
        {!loading && viewMode === "grid" && filteredClasses.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredClasses.map((c) => (
              <div
                key={c.id}
                className="bg-white rounded-lg border border-slate-200 shadow-sm hover:border-slate-300 transition-all flex flex-col justify-between overflow-hidden"
              >
                <div className="p-5">
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <span className="font-mono tabular-nums text-xs font-bold text-slate-700 px-2 py-0.5 rounded bg-slate-100 border border-slate-200">
                      {c.class_code}
                    </span>
                    <span className="text-[11px] font-medium text-slate-500 bg-slate-50 px-2 py-0.5 rounded border border-slate-200">
                      {c.semester || "Chính quy"}
                    </span>
                  </div>

                  <h3 className="text-base font-semibold text-slate-900 line-clamp-1 mb-4" title={c.course_name}>
                    {c.course_name}
                  </h3>

                  <div className="grid grid-cols-2 gap-3 pt-3 border-t border-slate-100 text-xs">
                    <div className="flex items-center gap-2 text-slate-600">
                      <Users size={15} className="text-slate-400" />
                      <span>
                        Sĩ số:{" "}
                        <strong className="font-mono tabular-nums text-slate-900">
                          {c.student_count}
                        </strong>{" "}
                        SV
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-slate-600">
                      <Calendar size={15} className="text-slate-400" />
                      <span>
                        Kế hoạch:{" "}
                        <strong className="font-mono tabular-nums text-slate-900">
                          {c.total_sessions}
                        </strong>{" "}
                        buổi
                      </span>
                    </div>
                  </div>

                  {/* Today schedule indicator */}
                  {c.today_schedule ? (
                    <div className="mt-3 p-2 rounded bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <span className="relative flex h-2 w-2">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                          <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                        </span>
                        <span className="font-medium">Tiết hôm nay:</span>
                        <span className="font-mono font-bold">
                          {c.today_schedule.start_time.slice(0, 5)} - {c.today_schedule.end_time.slice(0, 5)}
                        </span>
                      </div>
                      <span className="font-mono text-[11px] bg-emerald-100 text-emerald-900 px-1.5 py-0.5 rounded border border-emerald-300">
                        {c.today_schedule.room_name}
                      </span>
                    </div>
                  ) : (
                    <div className="mt-3 p-2 rounded bg-slate-50 border border-slate-200 text-[11px] text-slate-500 flex items-center gap-1.5">
                      <Clock size={12} className="text-slate-400" />
                      <span>Hôm nay không có tiết dạy</span>
                    </div>
                  )}
                </div>

                {/* Actions Footer */}
                <div className="px-4 py-3 bg-slate-50 border-t border-slate-200 flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5">
                    <Link
                      href={`/teacher/classes/${c.id}/live`}
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs transition-colors ${
                        c.today_schedule
                          ? "font-medium text-slate-700 bg-white hover:bg-slate-100 border border-slate-200 shadow-2xs"
                          : "font-semibold bg-slate-800 text-white hover:bg-slate-900 shadow-xs"
                      }`}
                    >
                      <Radio size={13} className={c.today_schedule ? "animate-pulse text-emerald-600" : ""} />
                      <span>{c.today_schedule ? "Live Sĩ số" : "Chi tiết lớp"}</span>
                    </Link>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <Link
                      href={`/teacher/reports?class_id=${c.id}`}
                      className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs font-medium text-slate-700 bg-white hover:bg-slate-100 border border-slate-200 transition-colors shadow-2xs"
                      title="Báo cáo cấm thi"
                    >
                      <AlertTriangle size={13} className="text-amber-500" />
                      <span>Cấm thi</span>
                    </Link>

                    <button
                      type="button"
                      onClick={() => handleDownloadExcel(c)}
                      disabled={downloadingId === c.id}
                      className="p-1.5 rounded-md text-slate-600 bg-white hover:bg-slate-100 border border-slate-200 hover:text-emerald-700 transition-colors shadow-2xs disabled:opacity-50"
                      title="Tải Excel báo cáo cấm thi"
                    >
                      {downloadingId === c.id ? (
                        <Loader2 size={14} className="animate-spin text-slate-600" />
                      ) : (
                        <FileSpreadsheet size={14} className="text-emerald-600" />
                      )}
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Content View: Table Mode */}
        {!loading && viewMode === "table" && filteredClasses.length > 0 && (
          <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                  <tr>
                    <th className="px-4 py-3 w-12 text-center">STT</th>
                    <th className="px-4 py-3">Mã lớp</th>
                    <th className="px-4 py-3">Tên môn học</th>
                    <th className="px-4 py-3">Học kỳ</th>
                    <th className="px-4 py-3 text-center">Sĩ số</th>
                    <th className="px-4 py-3 text-center">Số buổi</th>
                    <th className="px-4 py-3 text-right">Thao tác</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredClasses.map((c, idx) => (
                    <tr key={c.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="px-4 py-3 text-center text-xs text-slate-400 font-mono tabular-nums">
                        {idx + 1}
                      </td>
                      <td className="px-4 py-3 font-mono tabular-nums text-xs font-semibold text-slate-800">
                        {c.class_code}
                      </td>
                      <td className="px-4 py-3 font-medium text-slate-900">
                        {c.course_name}
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-600">
                        {c.semester || "--"}
                      </td>
                      <td className="px-4 py-3 text-center font-mono tabular-nums text-xs font-medium text-slate-800">
                        {c.student_count}
                      </td>
                      <td className="px-4 py-3 text-center font-mono tabular-nums text-xs text-slate-600">
                        {c.total_sessions}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Link
                            href={`/teacher/classes/${c.id}/live`}
                            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs transition-colors ${
                              c.today_schedule
                                ? "font-medium text-slate-700 bg-slate-100 hover:bg-slate-200"
                                : "font-semibold bg-slate-800 text-white hover:bg-slate-900 shadow-2xs"
                            }`}
                          >
                            <Radio size={12} className={c.today_schedule ? "animate-pulse text-emerald-600" : ""} />
                            <span>{c.today_schedule ? "Sĩ số" : "Chi tiết"}</span>
                          </Link>
                          <Link
                            href={`/teacher/reports?class_id=${c.id}`}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 transition-colors"
                          >
                            <AlertTriangle size={12} className="text-amber-500" />
                            <span>Cấm thi</span>
                          </Link>
                          <button
                            type="button"
                            onClick={() => handleDownloadExcel(c)}
                            disabled={downloadingId === c.id}
                            className="p-1.5 rounded text-emerald-700 hover:bg-emerald-50 border border-emerald-200 transition-colors disabled:opacity-50"
                            title="Tải Excel (.xlsx)"
                          >
                            {downloadingId === c.id ? (
                              <Loader2 size={13} className="animate-spin" />
                            ) : (
                              <FileSpreadsheet size={13} />
                            )}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </RoleGuard>
  );
}
