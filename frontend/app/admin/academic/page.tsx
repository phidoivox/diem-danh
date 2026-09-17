"use client";

import React, { useState, useEffect, useCallback } from "react";
import { RoleGuard } from "@/components/layout/role-guard";
import {
  AdminClass,
  AdminSchedule,
  StudentInClass,
  AdminUser,
  getAdminClasses,
  createAdminClass,
  deleteAdminClass,
  getAdminClassStudents,
  addStudentToClass,
  removeStudentFromClass,
  getAdminSchedules,
  deleteAdminSchedule,
  getAdminUsers,
} from "@/lib/api";
import { ScheduleFormModal } from "@/components/admin/schedule-form-modal";
import {
  Layers,
  Calendar,
  Search,
  Plus,
  Trash2,
  Users,
  Clock,
  BookOpen,
  GraduationCap,
  Loader2,
  X,
  UserPlus,
  AlertCircle,
  Filter,
} from "lucide-react";

export default function AdminAcademicPage() {
  const [activeTab, setActiveTab] = useState<"CLASSES" | "SCHEDULES">("CLASSES");

  // Classes state
  const [classes, setClasses] = useState<AdminClass[]>([]);
  const [classesTotal, setClassesTotal] = useState(0);
  const [classesPage, setClassesPage] = useState(1);
  const [classesSize] = useState(15);
  const [classesSearch, setClassesSearch] = useState("");
  const [isClassesLoading, setIsClassesLoading] = useState(true);

  // Schedules state
  const [schedules, setSchedules] = useState<AdminSchedule[]>([]);
  const [filterClassId, setFilterClassId] = useState<number | "">("");
  const [filterDate, setFilterDate] = useState("");
  const [filterRoom, setFilterRoom] = useState("");
  const [isSchedulesLoading, setIsSchedulesLoading] = useState(false);

  // Teachers & Students lookup for dropdowns
  const [teachers, setTeachers] = useState<AdminUser[]>([]);
  const [availableStudents, setAvailableStudents] = useState<AdminUser[]>([]);

  // Class create modal
  const [isCreateClassOpen, setIsCreateClassOpen] = useState(false);
  const [newClassCode, setNewClassCode] = useState("");
  const [newCourseName, setNewCourseName] = useState("");
  const [newTeacherId, setNewTeacherId] = useState<number | "">("");
  const [newSemester, setNewSemester] = useState("2026.1");
  const [newTotalSessions, setNewTotalSessions] = useState(15);
  const [isCreatingClass, setIsCreatingClass] = useState(false);
  const [createClassError, setCreateClassError] = useState<string | null>(null);

  // Class students modal
  const [selectedClassForStudents, setSelectedClassForStudents] = useState<AdminClass | null>(null);
  const [enrolledStudents, setEnrolledStudents] = useState<StudentInClass[]>([]);
  const [isLoadingStudents, setIsLoadingStudents] = useState(false);
  const [selectedStudentToAdd, setSelectedStudentToAdd] = useState<number | "">("");
  const [isAddingStudent, setIsAddingStudent] = useState(false);
  const [studentsModalError, setStudentsModalError] = useState<string | null>(null);

  // Schedule modal
  const [isScheduleModalOpen, setIsScheduleModalOpen] = useState(false);

  // Feedback message
  const [feedbackMsg, setFeedbackMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Load teachers for class creation
  useEffect(() => {
    getAdminUsers({ role: "TEACHER", size: 100 })
      .then((res) => setTeachers(res.items || []))
      .catch(() => {});

    getAdminUsers({ role: "STUDENT", size: 200 })
      .then((res) => setAvailableStudents(res.items || []))
      .catch(() => {});
  }, []);

  // Fetch classes
  const fetchClasses = useCallback(async () => {
    setIsClassesLoading(true);
    try {
      const res = await getAdminClasses({
        page: classesPage,
        size: classesSize,
        q: classesSearch,
      });
      setClasses(res.items || []);
      setClassesTotal(res.total || 0);
    } catch (err: any) {
      setFeedbackMsg({
        type: "error",
        text: err.message || "Không thể tải danh sách lớp học",
      });
    } finally {
      setIsClassesLoading(false);
    }
  }, [classesPage, classesSize, classesSearch]);

  // Fetch schedules
  const fetchSchedules = useCallback(async () => {
    setIsSchedulesLoading(true);
    try {
      const res = await getAdminSchedules({
        class_id: filterClassId ? Number(filterClassId) : undefined,
        study_date: filterDate || undefined,
        room_name: filterRoom || undefined,
      });
      setSchedules(res || []);
    } catch (err: any) {
      setFeedbackMsg({
        type: "error",
        text: err.message || "Không thể tải danh sách thời khóa biểu",
      });
    } finally {
      setIsSchedulesLoading(false);
    }
  }, [filterClassId, filterDate, filterRoom]);

  useEffect(() => {
    if (activeTab === "CLASSES") {
      fetchClasses();
    } else {
      fetchSchedules();
    }
  }, [activeTab, fetchClasses, fetchSchedules]);

  // Handle class creation
  const handleCreateClassSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateClassError(null);

    if (!newClassCode.trim() || !newCourseName.trim() || !newTeacherId || !newSemester.trim()) {
      setCreateClassError("Vui lòng điền đầy đủ thông tin lớp học");
      return;
    }

    setIsCreatingClass(true);
    try {
      await createAdminClass({
        class_code: newClassCode.trim().toUpperCase(),
        course_name: newCourseName.trim(),
        teacher_id: Number(newTeacherId),
        semester: newSemester.trim(),
        total_sessions: Number(newTotalSessions) || 15,
      });
      setIsCreateClassOpen(false);
      setNewClassCode("");
      setNewCourseName("");
      setFeedbackMsg({ type: "success", text: "Tạo lớp học phần mới thành công" });
      fetchClasses();
    } catch (err: any) {
      setCreateClassError(err.message || "Không thể tạo lớp học phần");
    } finally {
      setIsCreatingClass(false);
    }
  };

  // Handle class deletion
  const handleDeleteClass = async (c: AdminClass) => {
    if (!window.confirm(`Bạn có chắc chắn muốn xóa lớp học phần [${c.class_code}] ${c.course_name}?`)) {
      return;
    }
    try {
      await deleteAdminClass(c.id);
      setFeedbackMsg({ type: "success", text: `Đã xóa lớp học ${c.class_code}` });
      fetchClasses();
    } catch (err: any) {
      setFeedbackMsg({ type: "error", text: err.message || "Không thể xóa lớp học" });
    }
  };

  // Open students modal
  const handleOpenStudentsModal = async (c: AdminClass) => {
    setSelectedClassForStudents(c);
    setIsLoadingStudents(true);
    setStudentsModalError(null);
    try {
      const res = await getAdminClassStudents(c.id);
      setEnrolledStudents(res || []);
    } catch (err: any) {
      setStudentsModalError(err.message || "Không thể tải danh sách sinh viên trong lớp");
    } finally {
      setIsLoadingStudents(false);
    }
  };

  // Add student to class
  const handleAddStudent = async () => {
    if (!selectedClassForStudents || !selectedStudentToAdd) return;
    setIsAddingStudent(true);
    setStudentsModalError(null);
    try {
      await addStudentToClass(selectedClassForStudents.id, Number(selectedStudentToAdd));
      const res = await getAdminClassStudents(selectedClassForStudents.id);
      setEnrolledStudents(res || []);
      setSelectedStudentToAdd("");
      fetchClasses(); // refresh count
    } catch (err: any) {
      setStudentsModalError(err.message || "Không thể thêm sinh viên vào lớp");
    } finally {
      setIsAddingStudent(false);
    }
  };

  // Remove student from class
  const handleRemoveStudent = async (studentId: number, studentCode: string) => {
    if (!selectedClassForStudents) return;
    if (!window.confirm(`Xóa sinh viên ${studentCode} khỏi lớp học phần này?`)) return;

    try {
      await removeStudentFromClass(selectedClassForStudents.id, studentId);
      const res = await getAdminClassStudents(selectedClassForStudents.id);
      setEnrolledStudents(res || []);
      fetchClasses(); // refresh count
    } catch (err: any) {
      setStudentsModalError(err.message || "Không thể xóa sinh viên khỏi lớp");
    }
  };

  // Delete schedule
  const handleDeleteSchedule = async (s: AdminSchedule) => {
    if (!window.confirm(`Xóa lịch học ngày ${s.study_date} (${s.room_name})?`)) return;
    try {
      await deleteAdminSchedule(s.id);
      setFeedbackMsg({ type: "success", text: "Đã xóa lịch học thành công" });
      fetchSchedules();
    } catch (err: any) {
      setFeedbackMsg({ type: "error", text: err.message || "Không thể xóa lịch học" });
    }
  };

  return (
    <RoleGuard allowedRoles={["ADMIN"]}>
      <div className="space-y-4">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-200">
          <div>
            <h2 className="text-lg font-semibold text-slate-900 tracking-tight flex items-center gap-2">
              <Layers size={20} className="text-slate-700" />
              Quản lý Lớp học phần & Thời khóa biểu
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Tổ chức lớp học, phân bổ sinh viên ghi danh và xếp lịch phòng học chống trùng lịch
            </p>
          </div>

          <div className="flex items-center gap-2">
            {activeTab === "CLASSES" ? (
              <button
                onClick={() => {
                  setCreateClassError(null);
                  if (teachers.length > 0 && !newTeacherId) {
                    setNewTeacherId(teachers[0].id);
                  }
                  setIsCreateClassOpen(true);
                }}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium text-white bg-slate-900 hover:bg-slate-800 rounded-md transition-colors cursor-pointer shadow-xs"
              >
                <Plus size={15} />
                Tạo lớp học mới
              </button>
            ) : (
              <button
                onClick={() => setIsScheduleModalOpen(true)}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium text-white bg-slate-900 hover:bg-slate-800 rounded-md transition-colors cursor-pointer shadow-xs"
              >
                <Plus size={15} />
                Xếp lịch học phần
              </button>
            )}
          </div>
        </div>

        {/* Global Feedback Alert */}
        {feedbackMsg && (
          <div
            className={`p-3 text-xs rounded-md border flex items-center justify-between ${
              feedbackMsg.type === "success"
                ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                : "bg-rose-50 text-rose-800 border-rose-200"
            }`}
          >
            <span>{feedbackMsg.text}</span>
            <button
              onClick={() => setFeedbackMsg(null)}
              className="text-xs font-semibold underline hover:opacity-75 cursor-pointer ml-4"
            >
              Đóng
            </button>
          </div>
        )}

        {/* Navigation Tabs */}
        <div className="flex items-center gap-2 border-b border-slate-200">
          <button
            onClick={() => setActiveTab("CLASSES")}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold border-b-2 -mb-px transition-colors cursor-pointer ${
              activeTab === "CLASSES"
                ? "border-slate-900 text-slate-900"
                : "border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300"
            }`}
          >
            <BookOpen size={16} />
            Lớp học phần ({classesTotal})
          </button>
          <button
            onClick={() => setActiveTab("SCHEDULES")}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold border-b-2 -mb-px transition-colors cursor-pointer ${
              activeTab === "SCHEDULES"
                ? "border-slate-900 text-slate-900"
                : "border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300"
            }`}
          >
            <Calendar size={16} />
            Thời khóa biểu (Schedules)
          </button>
        </div>

        {/* ===================================================================== */}
        {/* TAB 1: CLASSES LIST */}
        {/* ===================================================================== */}
        {activeTab === "CLASSES" && (
          <div className="space-y-3">
            {/* Search toolbar */}
            <div className="flex items-center justify-between gap-3 bg-white p-3 rounded-lg border border-slate-200 shadow-xs">
              <div className="relative max-w-sm w-full">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  value={classesSearch}
                  onChange={(e) => {
                    setClassesSearch(e.target.value);
                    setClassesPage(1);
                  }}
                  placeholder="Tìm theo mã lớp hoặc tên môn..."
                  className="w-full pl-8 pr-3 py-1.5 text-xs rounded-md border border-slate-200 bg-slate-50/50 focus:bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900 focus:border-slate-900"
                />
              </div>
            </div>

            {/* Classes Table */}
            <div className="bg-white rounded-lg border border-slate-200 shadow-xs overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                      <th className="px-4 py-3 w-12 text-center">STT</th>
                      <th className="px-4 py-3">Mã lớp</th>
                      <th className="px-4 py-3">Tên môn học</th>
                      <th className="px-4 py-3">Giảng viên phụ trách</th>
                      <th className="px-4 py-3">Học kỳ</th>
                      <th className="px-4 py-3 text-center">Số buổi</th>
                      <th className="px-4 py-3 text-center">Sinh viên</th>
                      <th className="px-4 py-3 text-right">Thao tác</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-xs text-slate-700">
                    {isClassesLoading ? (
                      <tr>
                        <td colSpan={8} className="px-4 py-12 text-center text-slate-400">
                          <div className="flex flex-col items-center justify-center gap-2">
                            <Loader2 size={24} className="animate-spin text-slate-500" />
                            <span>Đang tải danh sách lớp học phần...</span>
                          </div>
                        </td>
                      </tr>
                    ) : classes.length === 0 ? (
                      <tr>
                        <td colSpan={8} className="px-4 py-12 text-center text-slate-400">
                          Chưa có lớp học phần nào được tạo
                        </td>
                      </tr>
                    ) : (
                      classes.map((c, idx) => (
                        <tr key={c.id} className="hover:bg-slate-50/75 transition-colors">
                          <td className="px-4 py-3 text-center font-mono tabular-nums text-slate-400">
                            {idx + 1}
                          </td>
                          <td className="px-4 py-3 font-mono font-semibold text-slate-900 tabular-nums">
                            {c.class_code}
                          </td>
                          <td className="px-4 py-3 font-medium text-slate-900">
                            {c.course_name}
                          </td>
                          <td className="px-4 py-3 text-slate-700">
                            {c.teacher_name || "Chưa phân công"}
                          </td>
                          <td className="px-4 py-3 font-mono text-slate-600">
                            {c.semester}
                          </td>
                          <td className="px-4 py-3 text-center font-mono tabular-nums text-slate-700">
                            {c.total_sessions}
                          </td>
                          <td className="px-4 py-3 text-center">
                            <button
                              onClick={() => handleOpenStudentsModal(c)}
                              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-mono font-medium bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 transition-colors cursor-pointer"
                            >
                              <Users size={12} />
                              <span className="tabular-nums">{c.student_count}</span> SV
                            </button>
                          </td>
                          <td className="px-4 py-3 text-right">
                            <div className="flex items-center justify-end gap-1.5">
                              <button
                                onClick={() => handleOpenStudentsModal(c)}
                                className="px-2 py-1 text-xs text-slate-700 hover:bg-slate-100 rounded border border-slate-200 transition-colors cursor-pointer"
                              >
                                Ghi danh SV
                              </button>
                              <button
                                onClick={() => handleDeleteClass(c)}
                                title="Xóa lớp học phần"
                                className="p-1.5 text-rose-600 hover:bg-rose-50 rounded transition-colors cursor-pointer"
                              >
                                <Trash2 size={14} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ===================================================================== */}
        {/* TAB 2: SCHEDULES LIST */}
        {/* ===================================================================== */}
        {activeTab === "SCHEDULES" && (
          <div className="space-y-3">
            {/* Filter toolbar */}
            <div className="flex flex-wrap items-center gap-3 bg-white p-3 rounded-lg border border-slate-200 shadow-xs">
              <div className="flex items-center gap-1 text-xs text-slate-500 font-medium">
                <Filter size={14} />
                Lọc:
              </div>

              {/* Class filter */}
              <select
                value={filterClassId}
                onChange={(e) => setFilterClassId(e.target.value ? Number(e.target.value) : "")}
                className="px-2.5 py-1.5 text-xs rounded-md border border-slate-200 bg-slate-50/50 focus:bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
              >
                <option value="">-- Tất cả lớp --</option>
                {classes.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.class_code} - {c.course_name}
                  </option>
                ))}
              </select>

              {/* Date filter */}
              <input
                type="date"
                value={filterDate}
                onChange={(e) => setFilterDate(e.target.value)}
                className="px-2.5 py-1.5 text-xs font-mono rounded-md border border-slate-200 bg-slate-50/50 focus:bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
              />

              {/* Room filter */}
              <input
                type="text"
                value={filterRoom}
                onChange={(e) => setFilterRoom(e.target.value)}
                placeholder="Phòng (VD: A1-301)"
                className="px-2.5 py-1.5 text-xs font-mono uppercase rounded-md border border-slate-200 bg-slate-50/50 focus:bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900 max-w-[140px]"
              />

              {(filterClassId || filterDate || filterRoom) && (
                <button
                  onClick={() => {
                    setFilterClassId("");
                    setFilterDate("");
                    setFilterRoom("");
                  }}
                  className="text-xs text-slate-500 hover:text-slate-800 underline cursor-pointer"
                >
                  Xóa bộ lọc
                </button>
              )}
            </div>

            {/* Schedules Table */}
            <div className="bg-white rounded-lg border border-slate-200 shadow-xs overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                      <th className="px-4 py-3 w-12 text-center">Buổi</th>
                      <th className="px-4 py-3">Lớp học phần</th>
                      <th className="px-4 py-3">Tên môn học</th>
                      <th className="px-4 py-3">Phòng học</th>
                      <th className="px-4 py-3">Ngày học</th>
                      <th className="px-4 py-3">Khung giờ</th>
                      <th className="px-4 py-3 text-right">Thao tác</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-xs text-slate-700">
                    {isSchedulesLoading ? (
                      <tr>
                        <td colSpan={7} className="px-4 py-12 text-center text-slate-400">
                          <div className="flex flex-col items-center justify-center gap-2">
                            <Loader2 size={24} className="animate-spin text-slate-500" />
                            <span>Đang tải thời khóa biểu...</span>
                          </div>
                        </td>
                      </tr>
                    ) : schedules.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="px-4 py-12 text-center text-slate-400">
                          Không có lịch học nào phù hợp với bộ lọc
                        </td>
                      </tr>
                    ) : (
                      schedules.map((s) => (
                        <tr key={s.id} className="hover:bg-slate-50/75 transition-colors">
                          <td className="px-4 py-3 text-center font-mono tabular-nums font-semibold text-slate-600">
                            #{s.session_order}
                          </td>
                          <td className="px-4 py-3 font-mono font-medium text-slate-900 tabular-nums">
                            {s.class_code || `Lớp #${s.class_id}`}
                          </td>
                          <td className="px-4 py-3 font-medium text-slate-900">
                            {s.course_name || "-"}
                          </td>
                          <td className="px-4 py-3">
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
                              {s.room_name}
                            </span>
                          </td>
                          <td className="px-4 py-3 font-mono tabular-nums text-slate-800">
                            {s.study_date}
                          </td>
                          <td className="px-4 py-3 font-mono tabular-nums text-slate-600">
                            <span className="inline-flex items-center gap-1">
                              <Clock size={12} className="text-slate-400" />
                              {s.start_time.slice(0, 5)} - {s.end_time.slice(0, 5)}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-right">
                            <button
                              onClick={() => handleDeleteSchedule(s)}
                              title="Xóa buổi học này"
                              className="p-1.5 text-rose-600 hover:bg-rose-50 rounded transition-colors cursor-pointer"
                            >
                              <Trash2 size={14} />
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ===================================================================== */}
        {/* MODAL: CREATE CLASS */}
        {/* ===================================================================== */}
        {isCreateClassOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
            <div className="relative w-full max-w-lg bg-white rounded-lg shadow-xl border border-slate-200 overflow-hidden">
              <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50/50">
                <h3 className="text-base font-semibold text-slate-900">Tạo mới lớp học phần</h3>
                <button
                  onClick={() => setIsCreateClassOpen(false)}
                  className="p-1.5 text-slate-400 hover:text-slate-600 rounded-md hover:bg-slate-100 transition-colors cursor-pointer"
                >
                  <X size={18} />
                </button>
              </div>

              <form onSubmit={handleCreateClassSubmit} className="p-6 space-y-4">
                {createClassError && (
                  <div className="flex items-start gap-2 p-3 text-xs bg-rose-50 border border-rose-200 text-rose-700 rounded-md">
                    <AlertCircle size={15} className="shrink-0 mt-0.5" />
                    <span>{createClassError}</span>
                  </div>
                )}

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Mã lớp học phần <span className="text-rose-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={newClassCode}
                      onChange={(e) => setNewClassCode(e.target.value)}
                      placeholder="IT4010_20261"
                      className="w-full px-3 py-2 text-xs font-mono uppercase rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Học kỳ <span className="text-rose-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={newSemester}
                      onChange={(e) => setNewSemester(e.target.value)}
                      placeholder="2026.1"
                      className="w-full px-3 py-2 text-xs font-mono rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Tên học phần / Môn học <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={newCourseName}
                    onChange={(e) => setNewCourseName(e.target.value)}
                    placeholder="Nhập môn Trí tuệ Nhân tạo"
                    className="w-full px-3 py-2 text-xs rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Giảng viên phụ trách <span className="text-rose-500">*</span>
                    </label>
                    <select
                      value={newTeacherId}
                      onChange={(e) => setNewTeacherId(Number(e.target.value))}
                      className="w-full px-3 py-2 text-xs rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                    >
                      <option value="">-- Chọn giảng viên --</option>
                      {teachers.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.user_code} - {t.full_name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Tổng số buổi học <span className="text-rose-500">*</span>
                    </label>
                    <input
                      type="number"
                      min={1}
                      max={45}
                      value={newTotalSessions}
                      onChange={(e) => setNewTotalSessions(parseInt(e.target.value) || 15)}
                      className="w-full px-3 py-2 text-xs font-mono rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                    />
                  </div>
                </div>

                <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-200">
                  <button
                    type="button"
                    onClick={() => setIsCreateClassOpen(false)}
                    className="px-4 py-2 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-md hover:bg-slate-50 transition-colors cursor-pointer"
                  >
                    Hủy bỏ
                  </button>
                  <button
                    type="submit"
                    disabled={isCreatingClass}
                    className="flex items-center gap-2 px-4 py-2 text-xs font-medium text-white bg-slate-900 hover:bg-slate-800 rounded-md transition-colors disabled:opacity-50 cursor-pointer"
                  >
                    {isCreatingClass && <Loader2 size={14} className="animate-spin" />}
                    Tạo lớp
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* ===================================================================== */}
        {/* MODAL: CLASS STUDENTS ENROLLMENT */}
        {/* ===================================================================== */}
        {selectedClassForStudents && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
            <div className="relative w-full max-w-3xl bg-white rounded-lg shadow-xl border border-slate-200 overflow-hidden flex flex-col max-h-[85vh]">
              {/* Header */}
              <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50/50">
                <div>
                  <h3 className="text-base font-semibold text-slate-900">
                    Danh sách sinh viên ghi danh
                  </h3>
                  <p className="text-xs text-slate-500 font-mono">
                    Lớp: {selectedClassForStudents.class_code} - {selectedClassForStudents.course_name} (
                    {enrolledStudents.length} SV)
                  </p>
                </div>
                <button
                  onClick={() => setSelectedClassForStudents(null)}
                  className="p-1.5 text-slate-400 hover:text-slate-600 rounded-md hover:bg-slate-100 transition-colors cursor-pointer"
                >
                  <X size={18} />
                </button>
              </div>

              {/* Add Student Bar */}
              <div className="p-4 bg-slate-50 border-b border-slate-200 space-y-2">
                {studentsModalError && (
                  <div className="flex items-start gap-2 p-2.5 text-xs bg-rose-50 border border-rose-200 text-rose-700 rounded-md">
                    <AlertCircle size={15} className="shrink-0 mt-0.5" />
                    <span>{studentsModalError}</span>
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <div className="flex-1">
                    <select
                      value={selectedStudentToAdd}
                      onChange={(e) => setSelectedStudentToAdd(e.target.value ? Number(e.target.value) : "")}
                      className="w-full px-3 py-1.5 text-xs rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                    >
                      <option value="">-- Chọn sinh viên để ghi danh vào lớp --</option>
                      {availableStudents
                        .filter((st) => !enrolledStudents.some((es) => es.id === st.id))
                        .map((st) => (
                          <option key={st.id} value={st.id}>
                            {st.user_code} - {st.full_name} ({st.student_profile?.class_name || "Lớp SH"})
                          </option>
                        ))}
                    </select>
                  </div>
                  <button
                    onClick={handleAddStudent}
                    disabled={isAddingStudent || !selectedStudentToAdd}
                    className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-white bg-slate-900 hover:bg-slate-800 rounded-md transition-colors disabled:opacity-50 cursor-pointer"
                  >
                    {isAddingStudent ? <Loader2 size={13} className="animate-spin" /> : <UserPlus size={14} />}
                    Thêm vào lớp
                  </button>
                </div>
              </div>

              {/* Student Table */}
              <div className="overflow-y-auto flex-1 p-4">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                      <th className="px-3 py-2 w-10 text-center">STT</th>
                      <th className="px-3 py-2">Mã SV</th>
                      <th className="px-3 py-2">Họ và tên</th>
                      <th className="px-3 py-2">Lớp SH</th>
                      <th className="px-3 py-2">Chuyên ngành</th>
                      <th className="px-3 py-2 text-center">Điểm RL</th>
                      <th className="px-3 py-2 text-right">Xóa</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-xs text-slate-700">
                    {isLoadingStudents ? (
                      <tr>
                        <td colSpan={7} className="px-4 py-8 text-center text-slate-400">
                          <Loader2 size={20} className="animate-spin mx-auto text-slate-400 mb-1" />
                          Đang tải danh sách...
                        </td>
                      </tr>
                    ) : enrolledStudents.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="px-4 py-8 text-center text-slate-400">
                          Chưa có sinh viên nào ghi danh vào lớp học này
                        </td>
                      </tr>
                    ) : (
                      enrolledStudents.map((st, idx) => (
                        <tr key={st.id} className="hover:bg-slate-50">
                          <td className="px-3 py-2 text-center font-mono tabular-nums text-slate-400">
                            {idx + 1}
                          </td>
                          <td className="px-3 py-2 font-mono font-medium text-slate-900 tabular-nums">
                            {st.user_code}
                          </td>
                          <td className="px-3 py-2 font-medium text-slate-900">
                            {st.full_name}
                          </td>
                          <td className="px-3 py-2 font-mono text-slate-600">
                            {st.class_name || "-"}
                          </td>
                          <td className="px-3 py-2 text-slate-600">
                            {st.major || "-"}
                          </td>
                          <td className="px-3 py-2 text-center font-mono tabular-nums text-emerald-700 font-semibold">
                            {st.total_point ?? 100}đ
                          </td>
                          <td className="px-3 py-2 text-right">
                            <button
                              onClick={() => handleRemoveStudent(st.id, st.user_code)}
                              title="Xóa sinh viên khỏi lớp"
                              className="p-1 text-rose-600 hover:bg-rose-50 rounded transition-colors cursor-pointer"
                            >
                              <Trash2 size={14} />
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {/* Footer */}
              <div className="flex items-center justify-end px-6 py-3 border-t border-slate-200 bg-slate-50/50">
                <button
                  onClick={() => setSelectedClassForStudents(null)}
                  className="px-4 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-md hover:bg-slate-50 transition-colors cursor-pointer"
                >
                  Đóng
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Schedule Form Modal */}
        <ScheduleFormModal
          isOpen={isScheduleModalOpen}
          onClose={() => setIsScheduleModalOpen(false)}
          onSuccess={() => {
            fetchSchedules();
            setFeedbackMsg({ type: "success", text: "Xếp lịch học phần thành công" });
          }}
          classes={classes}
        />
      </div>
    </RoleGuard>
  );
}
