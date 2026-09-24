"use client";

import React, { useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { RoleGuard } from "@/components/layout/role-guard";
import {
  AdminClass,
  AdminSchedule,
  StudentInClass,
  AdminUser,
  getAdminClasses,
  createAdminClass,
  updateAdminClass,
  deleteAdminClass,
  getAdminClassStudents,
  addStudentToClass,
  removeStudentFromClass,
  getAdminSchedules,
  deleteAdminSchedule,
  getAdminUsers,
} from "@/lib/api";
import { ScheduleFormModal } from "@/components/admin/schedule-form-modal";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  Layers,
  Calendar,
  Search,
  Plus,
  Pencil,
  Trash2,
  Users,
  Clock,
  BookOpen,
  Loader2,
  X,
  UserPlus,
  AlertCircle,
  Filter,
} from "lucide-react";

export default function AdminAcademicPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<"CLASSES" | "SCHEDULES">("CLASSES");

  // Classes state (page/q là một phần của queryKey chuẩn)
  const [classesPage, setClassesPage] = useState(1);
  const [classesSize] = useState(15);
  const [classesSearch, setClassesSearch] = useState("");
  const classesQuery = useQuery({
    queryKey: ["admin-classes", classesPage, classesSearch],
    queryFn: () =>
      getAdminClasses({
        page: classesPage,
        size: classesSize,
        q: classesSearch,
      }),
  });
  const classes: AdminClass[] = classesQuery.data?.items ?? [];
  const classesTotal = classesQuery.data?.total ?? 0;
  const isClassesLoading = classesQuery.isPending;

  // Schedules state
  const [filterClassId, setFilterClassId] = useState<number | "">("");
  const [filterDate, setFilterDate] = useState("");
  const [filterRoom, setFilterRoom] = useState("");
  const schedulesQuery = useQuery({
    queryKey: ["admin-schedules"],
    queryFn: () =>
      getAdminSchedules({
        class_id: filterClassId ? Number(filterClassId) : undefined,
        study_date: filterDate || undefined,
        room_name: filterRoom || undefined,
      }),
  });
  const schedules: AdminSchedule[] = schedulesQuery.data ?? [];
  const isSchedulesLoading = schedulesQuery.isPending;

  // Class create/edit modal (dùng chung form; có editingClass = chế độ sửa)
  const [isCreateClassOpen, setIsCreateClassOpen] = useState(false);
  const [editingClass, setEditingClass] = useState<AdminClass | null>(null);
  const [newClassCode, setNewClassCode] = useState("");
  const [newCourseName, setNewCourseName] = useState("");
  const [newTeacherId, setNewTeacherId] = useState<number | "">("");
  const [newSemester, setNewSemester] = useState("2026.1");
  const [newTotalSessions, setNewTotalSessions] = useState(15);
  const [createClassError, setCreateClassError] = useState<string | null>(null);

  // Class students modal (danh sách ghi danh là query theo lớp đang mở)
  const [selectedClassForStudents, setSelectedClassForStudents] = useState<AdminClass | null>(null);
  const [selectedStudentToAdd, setSelectedStudentToAdd] = useState<number | "">("");
  const [studentsModalError, setStudentsModalError] = useState<string | null>(null);
  const studentsQuery = useQuery({
    queryKey: ["admin-classes", selectedClassForStudents?.id ?? 0, "students"],
    queryFn: () => getAdminClassStudents(selectedClassForStudents!.id),
    enabled: selectedClassForStudents !== null,
  });
  const enrolledStudents: StudentInClass[] = studentsQuery.data ?? [];
  const isLoadingStudents = studentsQuery.isPending && selectedClassForStudents !== null;

  // Schedule modal (tạo mới khi editingSchedule = null, sửa khi có giá trị)
  const [isScheduleModalOpen, setIsScheduleModalOpen] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<AdminSchedule | null>(null);

  // ConfirmDialog states (thay window.confirm chặn thread)
  const [classToDelete, setClassToDelete] = useState<AdminClass | null>(null);
  const [studentToRemove, setStudentToRemove] = useState<{ id: number; code: string } | null>(null);
  const [scheduleToDelete, setScheduleToDelete] = useState<AdminSchedule | null>(null);
  const [feedbackMsg, setFeedbackMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const invalidateClasses = () =>
    queryClient.invalidateQueries({ queryKey: ["admin-classes"] });
  const invalidateStudents = () => {
    if (selectedClassForStudents) {
      queryClient.invalidateQueries({
        queryKey: ["admin-classes", selectedClassForStudents.id, "students"],
      });
    }
  };

  const saveClassMutation = useMutation({
    mutationFn: (payload: {
      class_code: string;
      course_name: string;
      teacher_id: number;
      semester: string;
      total_sessions: number;
    }) =>
      editingClass
        ? updateAdminClass(editingClass.id, payload)
        : createAdminClass(payload),
    onSuccess: (_data, payload) => {
      toast.success(
        editingClass
          ? `Đã cập nhật lớp học ${payload.class_code}`
          : "Tạo lớp học phần mới thành công"
      );
      setIsCreateClassOpen(false);
      setEditingClass(null);
      setNewClassCode("");
      setNewCourseName("");
      invalidateClasses();
    },
    onError: (err: unknown) => {
      setCreateClassError(
        err instanceof Error ? err.message : "Không thể lưu lớp học phần"
      );
    },
  });
  const isCreatingClass = saveClassMutation.isPending;

  const deleteClassMutation = useMutation({
    mutationFn: (id: number) => deleteAdminClass(id),
    onSuccess: () => {
      setFeedbackMsg({
        type: "success",
        text: `Đã xóa lớp học ${classToDelete?.class_code ?? ""}`,
      });
      setClassToDelete(null);
      invalidateClasses();
    },
    onError: (err: unknown) => {
      setFeedbackMsg({
        type: "error",
        text: err instanceof Error ? err.message : "Không thể xóa lớp học",
      });
    },
  });
  const isDeletingClass = deleteClassMutation.isPending;

  const addStudentMutation = useMutation({
    mutationFn: (studentId: number) =>
      addStudentToClass(selectedClassForStudents!.id, studentId),
    onSuccess: () => {
      setSelectedStudentToAdd("");
      invalidateStudents();
      invalidateClasses();
    },
    onError: (err: unknown) => {
      setStudentsModalError(
        err instanceof Error ? err.message : "Không thể thêm sinh viên vào lớp"
      );
    },
  });
  const isAddingStudent = addStudentMutation.isPending;

  const removeStudentMutation = useMutation({
    mutationFn: (studentId: number) =>
      removeStudentFromClass(selectedClassForStudents!.id, studentId),
    onSuccess: () => {
      setStudentToRemove(null);
      invalidateStudents();
      invalidateClasses();
    },
    onError: (err: unknown) => {
      setStudentsModalError(
        err instanceof Error ? err.message : "Không thể xóa sinh viên khỏi lớp"
      );
    },
  });
  const isRemovingStudent = removeStudentMutation.isPending;

  const deleteScheduleMutation = useMutation({
    mutationFn: (id: number) => deleteAdminSchedule(id),
    onSuccess: () => {
      setFeedbackMsg({ type: "success", text: "Đã xóa lịch học thành công" });
      setScheduleToDelete(null);
      queryClient.invalidateQueries({ queryKey: ["admin-schedules"] });
    },
    onError: (err: unknown) => {
      setFeedbackMsg({
        type: "error",
        text: err instanceof Error ? err.message : "Không thể xóa lịch học",
      });
    },
  });
  const isDeletingSchedule = deleteScheduleMutation.isPending;

  // Teachers & Students lookup cho dropdown (dùng lại key admin-users, không chạm trang users)
  const teachersQuery = useQuery({
    queryKey: ["admin-users", 1, "TEACHER", ""],
    queryFn: () => getAdminUsers({ role: "TEACHER", size: 100 }),
  });
  const studentsLookupQuery = useQuery({
    queryKey: ["admin-users", 1, "STUDENT", ""],
    queryFn: () => getAdminUsers({ role: "STUDENT", size: 200 }),
  });
  const teachers: AdminUser[] = teachersQuery.data?.items ?? [];
  const availableStudents: AdminUser[] = studentsLookupQuery.data?.items ?? [];

  // Refetch schedules khi filter đổi (giữ key chuẩn ["admin-schedules"] đúng verbatim)
  useEffect(() => {
    queryClient.invalidateQueries({ queryKey: ["admin-schedules"] });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterClassId, filterDate, filterRoom]);

  // Surface query lỗi lớp lên feedback chung
  useEffect(() => {
    if (classesQuery.isError) {
      const msg =
        classesQuery.error instanceof Error
          ? classesQuery.error.message
          : "Không thể tải danh sách lớp học";
      setFeedbackMsg({ type: "error", text: msg });
    }
  }, [classesQuery.isError, classesQuery.error]);

  // Mở modal tạo lớp mới (reset form)
  const openCreateClassModal = () => {
    setEditingClass(null);
    setNewClassCode("");
    setNewCourseName("");
    setNewSemester("2026.1");
    setNewTotalSessions(15);
    setCreateClassError(null);
    if (teachers.length > 0 && !newTeacherId) {
      setNewTeacherId(teachers[0].id);
    }
    setIsCreateClassOpen(true);
  };

  // Mở modal sửa lớp (nạp sẵn giá trị hiện tại)
  const openEditClassModal = (c: AdminClass) => {
    setEditingClass(c);
    setNewClassCode(c.class_code);
    setNewCourseName(c.course_name);
    setNewTeacherId(c.teacher_id);
    setNewSemester(c.semester);
    setNewTotalSessions(c.total_sessions);
    setCreateClassError(null);
    setIsCreateClassOpen(true);
  };

  // Handle class creation / update (qua useMutation + invalidate ["admin-classes"])
  const handleCreateClassSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setCreateClassError(null);

    if (!newClassCode.trim() || !newCourseName.trim() || !newTeacherId || !newSemester.trim()) {
      setCreateClassError("Vui lòng điền đầy đủ thông tin lớp học");
      return;
    }

    saveClassMutation.mutate({
      class_code: newClassCode.trim().toUpperCase(),
      course_name: newCourseName.trim(),
      teacher_id: Number(newTeacherId),
      semester: newSemester.trim(),
      total_sessions: Number(newTotalSessions) || 15,
    });
  };

  // Handle class deletion
  const handleDeleteClass = (c: AdminClass) => {
    setClassToDelete(c);
  };

  const handleConfirmDeleteClass = () => {
    if (!classToDelete || isDeletingClass) return;
    deleteClassMutation.mutate(classToDelete.id);
  };

  // Open students modal (query tự fetch theo selectedClassForStudents)
  const handleOpenStudentsModal = (c: AdminClass) => {
    setSelectedClassForStudents(c);
    setStudentsModalError(null);
  };

  // Add student to class
  const handleAddStudent = () => {
    if (!selectedClassForStudents || !selectedStudentToAdd) return;
    setStudentsModalError(null);
    addStudentMutation.mutate(Number(selectedStudentToAdd));
  };

  // Remove student from class
  const handleRemoveStudent = (studentId: number, studentCode: string) => {
    if (!selectedClassForStudents) return;
    setStudentToRemove({ id: studentId, code: studentCode });
  };

  const handleConfirmRemoveStudent = () => {
    if (!selectedClassForStudents || !studentToRemove || isRemovingStudent) return;
    removeStudentMutation.mutate(studentToRemove.id);
  };

  // Delete schedule
  const handleDeleteSchedule = (s: AdminSchedule) => {
    setScheduleToDelete(s);
  };

  const handleConfirmDeleteSchedule = () => {
    if (!scheduleToDelete || isDeletingSchedule) return;
    deleteScheduleMutation.mutate(scheduleToDelete.id);
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
                onClick={openCreateClassModal}
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
        <div className="flex items-center gap-2 border-b border-slate-200 overflow-x-auto">
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
            <div className="flex flex-col sm:flex-row sm:items-center justify-between flex-wrap gap-2 sm:gap-3 bg-white p-3 rounded-lg border border-slate-200 shadow-xs">
              <div className="relative w-full sm:max-w-sm">
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
                      <th className="px-4 py-3 hidden md:table-cell">Học kỳ</th>
                      <th className="px-4 py-3 text-center hidden md:table-cell">Số buổi</th>
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
                          <td className="px-4 py-3 font-mono text-slate-600 hidden md:table-cell">
                            {c.semester}
                          </td>
                          <td className="px-4 py-3 text-center font-mono tabular-nums text-slate-700 hidden md:table-cell">
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
                                onClick={() => openEditClassModal(c)}
                                title="Sửa thông tin lớp học phần"
                                className="p-1.5 text-slate-600 hover:bg-slate-100 rounded transition-colors cursor-pointer"
                              >
                                <Pencil size={14} />
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
            <div className="flex flex-col sm:flex-row sm:flex-wrap sm:items-center gap-2 sm:gap-3 bg-white p-3 rounded-lg border border-slate-200 shadow-xs">
              <div className="flex items-center gap-1 text-xs text-slate-500 font-medium">
                <Filter size={14} />
                Lọc:
              </div>

              {/* Class filter */}
              <select
                value={filterClassId}
                onChange={(e) => setFilterClassId(e.target.value ? Number(e.target.value) : "")}
                className="w-full sm:w-auto px-2.5 py-1.5 text-xs rounded-md border border-slate-200 bg-slate-50/50 focus:bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
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
                className="w-full sm:w-auto px-2.5 py-1.5 text-xs font-mono rounded-md border border-slate-200 bg-slate-50/50 focus:bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
              />

              {/* Room filter */}
              <input
                type="text"
                value={filterRoom}
                onChange={(e) => setFilterRoom(e.target.value)}
                placeholder="Phòng (VD: A1-301)"
                className="w-full sm:w-auto px-2.5 py-1.5 text-xs font-mono uppercase rounded-md border border-slate-200 bg-slate-50/50 focus:bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900 sm:max-w-[140px]"
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
                      <th className="px-4 py-3 hidden md:table-cell">Tên môn học</th>
                      <th className="px-4 py-3 hidden md:table-cell">Phòng học</th>
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
                          <td className="px-4 py-3 font-medium text-slate-900 hidden md:table-cell">
                            {s.course_name || "-"}
                          </td>
                          <td className="px-4 py-3 hidden md:table-cell">
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
                            <div className="flex items-center justify-end gap-1">
                              <button
                                onClick={() => {
                                  setEditingSchedule(s);
                                  setIsScheduleModalOpen(true);
                                }}
                                title="Sửa buổi học này"
                                className="p-1.5 text-slate-600 hover:bg-slate-100 rounded transition-colors cursor-pointer"
                              >
                                <Pencil size={14} />
                              </button>
                              <button
                                onClick={() => handleDeleteSchedule(s)}
                                title="Xóa buổi học này"
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
        {/* MODAL: CREATE / EDIT CLASS */}
        {/* ===================================================================== */}
        {isCreateClassOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
            <div className="relative w-full max-w-lg max-h-[90vh] flex flex-col bg-white rounded-lg shadow-xl border border-slate-200 overflow-hidden">
              <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50/50 shrink-0">
                <h3 className="text-base font-semibold text-slate-900">
                  {editingClass ? `Sửa lớp học phần ${editingClass.class_code}` : "Tạo mới lớp học phần"}
                </h3>
                <button
                  onClick={() => {
                    setIsCreateClassOpen(false);
                    setEditingClass(null);
                  }}
                  className="p-1.5 text-slate-400 hover:text-slate-600 rounded-md hover:bg-slate-100 transition-colors cursor-pointer"
                >
                  <X size={18} />
                </button>
              </div>

              <form onSubmit={handleCreateClassSubmit} className="flex flex-col min-h-0 flex-1 overflow-hidden">
                <div className="flex-1 overflow-y-auto overscroll-contain p-6 space-y-4">
                {createClassError && (
                  <div className="flex items-start gap-2 p-3 text-xs bg-rose-50 border border-rose-200 text-rose-700 rounded-md">
                    <AlertCircle size={15} className="shrink-0 mt-0.5" />
                    <span>{createClassError}</span>
                  </div>
                )}

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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

                </div>

                <div className="flex items-center justify-end gap-3 px-6 py-3 border-t border-slate-200 bg-slate-50/50 shrink-0">
                  <button
                    type="button"
                    onClick={() => {
                      setIsCreateClassOpen(false);
                      setEditingClass(null);
                    }}
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
                    {editingClass ? "Lưu thay đổi" : "Tạo lớp"}
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
              {/* Header — cố định */}
              <div className="flex items-center justify-between px-4 sm:px-6 py-3 sm:py-4 border-b border-slate-200 bg-slate-50/50 shrink-0">
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

              {/* Add Student Bar — cố định */}
              <div className="p-3 sm:p-4 bg-slate-50 border-b border-slate-200 space-y-2 shrink-0">
                {studentsModalError && (
                  <div className="flex items-start gap-2 p-2.5 text-xs bg-rose-50 border border-rose-200 text-rose-700 rounded-md">
                    <AlertCircle size={15} className="shrink-0 mt-0.5" />
                    <span>{studentsModalError}</span>
                  </div>
                )}
                <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
                  <div className="flex-1">
                    <select
                      value={selectedStudentToAdd}
                      onChange={(e) => setSelectedStudentToAdd(e.target.value ? Number(e.target.value) : "")}
                      className="w-full px-3 py-2 sm:py-1.5 min-h-[38px] text-xs rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
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
                    className="flex items-center justify-center gap-1 px-3 py-2 sm:py-1.5 min-h-[38px] text-xs font-medium text-white bg-slate-900 hover:bg-slate-800 rounded-md transition-colors disabled:opacity-50 cursor-pointer shrink-0"
                  >
                    {isAddingStudent ? <Loader2 size={13} className="animate-spin" /> : <UserPlus size={14} />}
                    <span>Thêm vào lớp</span>
                  </button>
                </div>
              </div>

              {/* Student Table */}
              <div className="overflow-y-auto flex-1 p-3 sm:p-4">
                <div className="overflow-x-auto [scrollbar-width:thin]">
                  <table className="w-full min-w-[560px] text-left border-collapse">
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
              </div>

              {/* Footer */}
              <div className="flex items-center justify-end px-4 sm:px-6 py-3 border-t border-slate-200 bg-slate-50/50">
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

        {/* Schedule Form Modal (tạo mới / sửa buổi học) */}
        <ScheduleFormModal
          isOpen={isScheduleModalOpen}
          onClose={() => {
            setIsScheduleModalOpen(false);
            setEditingSchedule(null);
          }}
          onSuccess={() => {
            queryClient.invalidateQueries({ queryKey: ["admin-schedules"] });
            setEditingSchedule(null);
            setFeedbackMsg({
              type: "success",
              text: editingSchedule ? "Cập nhật lịch học thành công" : "Xếp lịch học phần thành công",
            });
          }}
          classes={classes}
          initialSchedule={editingSchedule}
        />

        {/* ConfirmDialogs thay window.confirm */}
        <ConfirmDialog
          open={classToDelete !== null}
          onOpenChange={(open) => {
            if (!open) setClassToDelete(null);
          }}
          title="Xóa lớp học phần"
          description={
            classToDelete
              ? `Bạn có chắc chắn muốn xóa lớp học phần [${classToDelete.class_code}] ${classToDelete.course_name}?`
              : ""
          }
          confirmLabel={isDeletingClass ? "Đang xử lý..." : "Xóa lớp"}
          onConfirm={handleConfirmDeleteClass}
          isPending={isDeletingClass}
        />
        <ConfirmDialog
          open={studentToRemove !== null}
          onOpenChange={(open) => {
            if (!open) setStudentToRemove(null);
          }}
          title="Xóa sinh viên khỏi lớp"
          description={
            studentToRemove
              ? `Xóa sinh viên ${studentToRemove.code} khỏi lớp học phần này?`
              : ""
          }
          confirmLabel={isRemovingStudent ? "Đang xử lý..." : "Xóa khỏi lớp"}
          onConfirm={handleConfirmRemoveStudent}
          isPending={isRemovingStudent}
        />
        <ConfirmDialog
          open={scheduleToDelete !== null}
          onOpenChange={(open) => {
            if (!open) setScheduleToDelete(null);
          }}
          title="Xóa buổi học"
          description={
            scheduleToDelete
              ? `Xóa lịch học ngày ${scheduleToDelete.study_date} (${scheduleToDelete.room_name})?`
              : ""
          }
          confirmLabel={isDeletingSchedule ? "Đang xử lý..." : "Xóa lịch"}
          onConfirm={handleConfirmDeleteSchedule}
          isPending={isDeletingSchedule}
        />
      </div>
    </RoleGuard>
  );
}
