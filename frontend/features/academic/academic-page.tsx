"use client";

import React, { useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { RoleGuard } from "@/features/shell";
import {
  AdminClass,
  AdminCourse,
  AdminAdministrativeClass,
  AdminSchedule,
  StudentInClass,
  AdminUser,
  getAdminClasses,
  createAdminClass,
  updateAdminClass,
  deleteAdminClass,
  getAdminClassStudents,
  getAdminCourses,
  createAdminCourse,
  updateAdminCourse,
  deleteAdminCourse,
  getAdminAdministrativeClasses,
  createAdminAdministrativeClass,
  updateAdminAdministrativeClass,
  deleteAdminAdministrativeClass,
  addStudentsToClassBulk,
  removeStudentFromClass,
  getAdminSchedules,
  deleteAdminSchedule,
  getAdminUsers,
} from "@/features/shell";
import { ScheduleFormModal } from "./schedule-form-modal";
import { ScheduleBulkModal } from "./schedule-bulk-modal";
import { ConfirmDialog } from "@/features/shell";
import { SearchInput } from "@/features/shell";
import { useDebouncedValue } from "@/features/shell";
import { getConductRank } from "@/features/evaluation";
import {
  Layers,
  Calendar,
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
  const [activeTab, setActiveTab] = useState<"CLASSES" | "COURSES" | "ADMIN_CLASSES" | "SCHEDULES">("CLASSES");

  // Classes state (page/q là một phần của queryKey chuẩn).
  // Kiểu tìm kiếm thống nhất: gõ là lọc live, không nút Tìm;
  // server-side debounce 300ms rồi mới đổi queryKey (tránh spam API mỗi phím).
  const [classesPage, setClassesPage] = useState(1);
  const [classesSize] = useState(15);
  const [classesInput, setClassesInput] = useState("");
  const classesSearch = useDebouncedValue(classesInput.trim(), 300);
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
    // Filters là một phần của key (stale/miss đúng): đổi filter tự refetch,
    // không cần invalidate tay.
    queryKey: ["admin-schedules", filterClassId, filterDate, filterRoom],
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
  const [newCourseId, setNewCourseId] = useState<number | "">("");
  const [newCourseName, setNewCourseName] = useState("");
  const [newTeacherId, setNewTeacherId] = useState<number | "">("");
  const [newSemester, setNewSemester] = useState("2026.1");
  const [newTotalSessions, setNewTotalSessions] = useState(15);
  const [createClassError, setCreateClassError] = useState<string | null>(null);

  // Courses catalog tab state (danh mục học phần: mã môn, tín chỉ, số buổi mặc định)
  const [coursesPage, setCoursesPage] = useState(1);
  const [coursesSize] = useState(15);
  const [coursesInput, setCoursesInput] = useState("");
  const coursesSearch = useDebouncedValue(coursesInput.trim(), 300);
  const coursesQuery = useQuery({
    queryKey: ["admin-courses", coursesPage, coursesSearch],
    queryFn: () =>
      getAdminCourses({
        page: coursesPage,
        size: coursesSize,
        q: coursesSearch,
      }),
  });
  const courses: AdminCourse[] = coursesQuery.data?.items ?? [];
  const coursesTotal = coursesQuery.data?.total ?? 0;
  const isCoursesLoading = coursesQuery.isPending;
  const [isCourseModalOpen, setIsCourseModalOpen] = useState(false);
  const [editingCourse, setEditingCourse] = useState<AdminCourse | null>(null);
  const [courseCode, setCourseCode] = useState("");
  const [courseName, setCourseName] = useState("");
  const [courseCredits, setCourseCredits] = useState(3);
  const [courseDefaultSessions, setCourseDefaultSessions] = useState(15);
  const [courseDescription, setCourseDescription] = useState("");
  const [courseError, setCourseError] = useState<string | null>(null);
  const [courseToDelete, setCourseToDelete] = useState<AdminCourse | null>(null);

  // Administrative classes tab state (lớp sinh hoạt / niên chế cố định)
  const [adminClassesPage, setAdminClassesPage] = useState(1);
  const [adminClassesSize] = useState(15);
  const [adminClassesInput, setAdminClassesInput] = useState("");
  const adminClassesSearch = useDebouncedValue(adminClassesInput.trim(), 300);
  const adminClassesQuery = useQuery({
    queryKey: ["admin-administrative-classes", adminClassesPage, adminClassesSearch],
    queryFn: () =>
      getAdminAdministrativeClasses({
        page: adminClassesPage,
        size: adminClassesSize,
        q: adminClassesSearch,
      }),
  });
  const adminClasses: AdminAdministrativeClass[] = adminClassesQuery.data?.items ?? [];
  const adminClassesTotal = adminClassesQuery.data?.total ?? 0;
  const isAdminClassesLoading = adminClassesQuery.isPending;
  const [isAdminClassModalOpen, setIsAdminClassModalOpen] = useState(false);
  const [editingAdminClass, setEditingAdminClass] = useState<AdminAdministrativeClass | null>(null);
  const [adminClassCode, setAdminClassCode] = useState("");
  const [adminClassYear, setAdminClassYear] = useState("");
  const [adminClassFaculty, setAdminClassFaculty] = useState("");
  const [adminClassTeacherId, setAdminClassTeacherId] = useState<number | "">("");
  const [adminClassError, setAdminClassError] = useState<string | null>(null);
  const [adminClassToDelete, setAdminClassToDelete] = useState<AdminAdministrativeClass | null>(null);

  // Class students modal: chỉ xem danh sách belongs-to (điểm danh/tính điểm vẫn
  // đọc class_students ở backend; ghi danh thực hiện qua "Ghi danh theo lớp SH").
  const [selectedClassForStudents, setSelectedClassForStudents] = useState<AdminClass | null>(null);
  const [studentsModalSearch, setStudentsModalSearch] = useState("");
  const [shEnrollSearch, setShEnrollSearch] = useState("");
  const [shEnrollChecked, setShEnrollChecked] = useState<number[]>([]);
  const [studentsModalError, setStudentsModalError] = useState<string | null>(null);
  const studentsQuery = useQuery({
    queryKey: ["admin-classes", selectedClassForStudents?.id ?? 0, "students"],
    queryFn: () => getAdminClassStudents(selectedClassForStudents!.id),
    enabled: selectedClassForStudents !== null,
  });
  const enrolledStudents: StudentInClass[] = studentsQuery.data ?? [];
  const isLoadingStudents = studentsQuery.isPending && selectedClassForStudents !== null;
  const visibleStudents = enrolledStudents.filter((st) => {
    const q = studentsModalSearch.trim().toLowerCase();
    return (
      !q ||
      st.user_code.toLowerCase().includes(q) ||
      st.full_name.toLowerCase().includes(q)
    );
  });

  // Schedule modal (tạo mới khi editingSchedule = null, sửa khi có giá trị)
  const [isScheduleModalOpen, setIsScheduleModalOpen] = useState(false);
  const [isBulkModalOpen, setIsBulkModalOpen] = useState(false);
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
      course_id?: number;
      course_name?: string;
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
      setNewCourseId("");
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

  // Course catalog mutations (tạo/sửa/xóa học phần)
  const saveCourseMutation = useMutation({
    mutationFn: (payload: {
      course_code: string;
      course_name: string;
      credits: number;
      default_sessions: number;
      description?: string;
    }) =>
      editingCourse
        ? updateAdminCourse(editingCourse.id, payload)
        : createAdminCourse(payload),
    onSuccess: (_data, payload) => {
      toast.success(
        editingCourse
          ? `Đã cập nhật học phần ${payload.course_code}`
          : "Tạo học phần mới thành công"
      );
      setIsCourseModalOpen(false);
      setEditingCourse(null);
      setCourseCode("");
      setCourseName("");
      setCourseCredits(3);
      setCourseDefaultSessions(15);
      setCourseDescription("");
      queryClient.invalidateQueries({ queryKey: ["admin-courses"] });
      invalidateClasses();
    },
    onError: (err: unknown) => {
      setCourseError(
        err instanceof Error ? err.message : "Không thể lưu học phần"
      );
    },
  });
  const isSavingCourse = saveCourseMutation.isPending;

  const deleteCourseMutation = useMutation({
    mutationFn: (id: number) => deleteAdminCourse(id),
    onSuccess: () => {
      setFeedbackMsg({
        type: "success",
        text: `Đã xóa học phần ${courseToDelete?.course_code ?? ""}`,
      });
      setCourseToDelete(null);
      queryClient.invalidateQueries({ queryKey: ["admin-courses"] });
    },
    onError: (err: unknown) => {
      setFeedbackMsg({
        type: "error",
        text: err instanceof Error ? err.message : "Không thể xóa học phần",
      });
    },
  });
  const isDeletingCourse = deleteCourseMutation.isPending;

  // Administrative classes mutations (tạo/sửa/xóa lớp sinh hoạt)
  const saveAdminClassMutation = useMutation({
    mutationFn: (payload: {
      class_code: string;
      academic_year?: string;
      faculty?: string;
      homeroom_teacher_id?: number | null;
    }) =>
      editingAdminClass
        ? updateAdminAdministrativeClass(editingAdminClass.id, payload)
        : createAdminAdministrativeClass(payload),
    onSuccess: (_data, payload) => {
      toast.success(
        editingAdminClass
          ? `Đã cập nhật lớp sinh hoạt ${payload.class_code}`
          : "Tạo lớp sinh hoạt mới thành công"
      );
      setIsAdminClassModalOpen(false);
      setEditingAdminClass(null);
      setAdminClassCode("");
      setAdminClassYear("");
      setAdminClassFaculty("");
      setAdminClassTeacherId("");
      queryClient.invalidateQueries({ queryKey: ["admin-administrative-classes"] });
      // Đồng bộ dropdown ghi danh theo lớp SH trong modal SV.
      queryClient.invalidateQueries({ queryKey: ["student-class-names"] });
    },
    onError: (err: unknown) => {
      setAdminClassError(
        err instanceof Error ? err.message : "Không thể lưu lớp sinh hoạt"
      );
    },
  });
  const isSavingAdminClass = saveAdminClassMutation.isPending;

  const deleteAdminClassMutation = useMutation({
    mutationFn: (id: number) => deleteAdminAdministrativeClass(id),
    onSuccess: () => {
      setFeedbackMsg({
        type: "success",
        text: `Đã xóa lớp sinh hoạt ${adminClassToDelete?.class_code ?? ""}`,
      });
      setAdminClassToDelete(null);
      queryClient.invalidateQueries({ queryKey: ["admin-administrative-classes"] });
      queryClient.invalidateQueries({ queryKey: ["student-class-names"] });
    },
    onError: (err: unknown) => {
      setFeedbackMsg({
        type: "error",
        text: err instanceof Error ? err.message : "Không thể xóa lớp sinh hoạt",
      });
    },
  });
  const isDeletingAdminClass = deleteAdminClassMutation.isPending;

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
    mutationFn: (adminClassIds: number[]) =>
      addStudentsToClassBulk(selectedClassForStudents!.id, [], [], adminClassIds),
    onSuccess: (res) => {
      setShEnrollChecked([]);
      if (res.skipped?.length) {
        toast.warning(`Đã thêm ${res.enrolled.length} SV, bỏ qua ${res.skipped.length} SV (trùng/không hợp lệ)`);
      } else {
        toast.success(`Đã ghi danh ${res.enrolled.length} sinh viên vào lớp`);
      }
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

  // Teachers lookup cho dropdown tạo/sửa lớp (dùng lại key admin-users, không chạm trang users)
  const teachersQuery = useQuery({
    queryKey: ["admin-users", 1, "TEACHER", ""],
    queryFn: () => getAdminUsers({ role: "TEACHER", size: 100 }),
  });
  const teachers: AdminUser[] = teachersQuery.data?.items ?? [];
  // Danh sách lớp SH (dùng khi ghi danh cả lớp vào lớp học phần).
  const classNamesQuery = useQuery({
    queryKey: ["admin-administrative-classes", "enroll-options"],
    queryFn: () => getAdminAdministrativeClasses({ size: 500 }),
    enabled: selectedClassForStudents !== null,
  });
  const shClassOptions: AdminAdministrativeClass[] = classNamesQuery.data?.items ?? [];
  const visibleShOptions = shClassOptions.filter(
    (ac) =>
      ac.class_code.toLowerCase().includes(shEnrollSearch.trim().toLowerCase()) ||
      (ac.faculty || "").toLowerCase().includes(shEnrollSearch.trim().toLowerCase())
  );

  // Refetch schedules khi filter đổi (giữ key chuẩn ["admin-schedules"] đúng verbatim)
  useEffect(() => {
    queryClient.invalidateQueries({ queryKey: ["admin-schedules"] });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterClassId, filterDate, filterRoom]);

  // Surface query lỗi lớp lên feedback chung (render-phase update thay effect:
  // chỉ set khi error object đổi nên nút Đóng vẫn giữ được banner ẩn).
  const [surfacedClassesError, setSurfacedClassesError] = useState<unknown>(null);
  if (classesQuery.isError && classesQuery.error !== surfacedClassesError) {
    setSurfacedClassesError(classesQuery.error);
    setFeedbackMsg({
      type: "error",
      text:
        classesQuery.error instanceof Error
          ? classesQuery.error.message
          : "Không thể tải danh sách lớp học",
    });
  }

  // Mở modal tạo lớp mới (reset form)
  const openCreateClassModal = () => {
    setEditingClass(null);
    setNewClassCode("");
    setNewCourseId("");
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
    setNewCourseId(c.course_id ?? "");
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

    if (!newClassCode.trim() || !newTeacherId || !newSemester.trim()) {
      setCreateClassError("Vui lòng điền đầy đủ thông tin lớp học");
      return;
    }
    // Phải có học phần: trường hợp lớp được sửa từ trước khi có môn trong
    // danh mục giữ course_name cũ, lớp mới không chọn -> chặn thay vì tự sinh.
    if (!editingClass && !newCourseId && !newCourseName.trim()) {
      setCreateClassError("Vui lòng chọn học phần cho lớp học");
      return;
    }

    saveClassMutation.mutate({
      class_code: newClassCode.trim().toUpperCase(),
      course_id: newCourseId ? Number(newCourseId) : undefined,
      course_name: !newCourseId ? newCourseName.trim() : undefined,
      teacher_id: Number(newTeacherId),
      semester: newSemester.trim(),
      total_sessions: Number(newTotalSessions) || 15,
    });
  };

  // Mở modal tạo/sửa học phần
  const openCreateCourseModal = () => {
    setEditingCourse(null);
    setCourseCode("");
    setCourseName("");
    setCourseCredits(3);
    setCourseDefaultSessions(15);
    setCourseDescription("");
    setCourseError(null);
    setIsCourseModalOpen(true);
  };

  const openEditCourseModal = (c: AdminCourse) => {
    setEditingCourse(c);
    setCourseCode(c.course_code);
    setCourseName(c.course_name);
    setCourseCredits(c.credits);
    setCourseDefaultSessions(c.default_sessions);
    setCourseDescription(c.description ?? "");
    setCourseError(null);
    setIsCourseModalOpen(true);
  };

  const handleCourseSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setCourseError(null);

    if (!courseCode.trim() || !courseName.trim()) {
      setCourseError("Vui lòng nhập mã và tên học phần");
      return;
    }

    saveCourseMutation.mutate({
      course_code: courseCode.trim().toUpperCase(),
      course_name: courseName.trim(),
      credits: Number(courseCredits) || 3,
      default_sessions: Number(courseDefaultSessions) || 15,
      description: courseDescription.trim() || undefined,
    });
  };

  // Mở modal tạo/sửa lớp sinh hoạt
  const openCreateAdminClassModal = () => {
    setEditingAdminClass(null);
    setAdminClassCode("");
    setAdminClassYear("");
    setAdminClassFaculty("");
    setAdminClassTeacherId("");
    setAdminClassError(null);
    setIsAdminClassModalOpen(true);
  };

  const openEditAdminClassModal = (c: AdminAdministrativeClass) => {
    setEditingAdminClass(c);
    setAdminClassCode(c.class_code);
    setAdminClassYear(c.academic_year ?? "");
    setAdminClassFaculty(c.faculty ?? "");
    setAdminClassTeacherId(c.homeroom_teacher_id ?? "");
    setAdminClassError(null);
    setIsAdminClassModalOpen(true);
  };

  const handleAdminClassSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setAdminClassError(null);

    if (!adminClassCode.trim()) {
      setAdminClassError("Vui lòng nhập mã lớp sinh hoạt");
      return;
    }

    saveAdminClassMutation.mutate({
      class_code: adminClassCode.trim().toUpperCase(),
      academic_year: adminClassYear.trim(),
      faculty: adminClassFaculty.trim(),
      homeroom_teacher_id: adminClassTeacherId ? Number(adminClassTeacherId) : null,
    });
  };

  // Tự động điền số buổi chuẩn khi chọn môn học trong form lớp học phần.
  const handleCourseSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const raw = e.target.value;
    setNewCourseId(raw ? Number(raw) : "");
    const course = courses.find((c) => c.id === Number(raw));
    if (course) {
      setNewCourseName(course.course_name);
      // Lớp mới chưa mở lịch: dùng số buổi mặc định của môn, không ghi đè lớp đang sửa.
      if (!editingClass) {
        setNewTotalSessions(course.default_sessions);
      }
    } else {
      setNewCourseName("");
    }
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
    setStudentsModalSearch("");
    setShEnrollSearch("");
    setShEnrollChecked([]);
  };

  // Ghi danh cả lớp SH đã tick vào lớp học phần (1 request bulk)
  const handleAddShClasses = () => {
    if (!selectedClassForStudents || shEnrollChecked.length === 0) return;
    setStudentsModalError(null);
    addStudentMutation.mutate(shEnrollChecked);
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
            {activeTab === "CLASSES" || activeTab === "COURSES" || activeTab === "ADMIN_CLASSES" ? (
              <button
                onClick={activeTab === "CLASSES" ? openCreateClassModal : activeTab === "COURSES" ? openCreateCourseModal : openCreateAdminClassModal}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium text-white bg-slate-900 hover:bg-slate-800 rounded-md transition-colors cursor-pointer shadow-xs"
              >
                <Plus size={15} />
                {activeTab === "CLASSES" ? "Tạo lớp học mới" : activeTab === "COURSES" ? "Thêm học phần" : "Tạo lớp sinh hoạt"}
              </button>
            ) : (
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setIsBulkModalOpen(true)}
                  className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium text-slate-900 bg-amber-100 hover:bg-amber-200 border border-amber-300 rounded-md transition-colors cursor-pointer shadow-xs"
                >
                  <Plus size={15} />
                  Sinh hàng loạt
                </button>
                <button
                  onClick={() => setIsScheduleModalOpen(true)}
                  className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium text-white bg-slate-900 hover:bg-slate-800 rounded-md transition-colors cursor-pointer shadow-xs"
                >
                  <Plus size={15} />
                  Xếp lịch học phần
                </button>
              </div>
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
            onClick={() => setActiveTab("COURSES")}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold border-b-2 -mb-px transition-colors cursor-pointer ${
              activeTab === "COURSES"
                ? "border-slate-900 text-slate-900"
                : "border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300"
            }`}
          >
            <Layers size={16} />
            Học phần ({coursesTotal})
          </button>
          <button
            onClick={() => setActiveTab("ADMIN_CLASSES")}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold border-b-2 -mb-px transition-colors cursor-pointer ${
              activeTab === "ADMIN_CLASSES"
                ? "border-slate-900 text-slate-900"
                : "border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300"
            }`}
          >
            <Users size={16} />
            Lớp sinh hoạt ({adminClassesTotal})
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
              <SearchInput
                value={classesInput}
                onChange={(v) => {
                  setClassesInput(v);
                  setClassesPage(1);
                }}
                placeholder="Tìm theo mã lớp hoặc tên môn..."
                ariaLabel="Tìm kiếm lớp học phần"
                className="w-full sm:max-w-sm"
              />
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
                      <th className="px-4 py-3 text-right">Thao tác</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-xs text-slate-700">
                    {isClassesLoading ? (
                      <tr>
                        <td colSpan={7} className="px-4 py-12 text-center text-slate-400">
                          <div className="flex flex-col items-center justify-center gap-2">
                            <Loader2 size={24} className="animate-spin text-slate-500" />
                            <span>Đang tải danh sách lớp học phần...</span>
                          </div>
                        </td>
                      </tr>
                    ) : classes.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="px-4 py-12 text-center text-slate-400">
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
                            {c.course_code && (
                              <span className="ml-2 px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold bg-slate-100 text-slate-600 border border-slate-200">
                                {c.course_code}
                              </span>
                            )}
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
                          <td className="px-4 py-3 text-right">
                            <div className="flex items-center justify-end gap-1.5">
                              <button
                                onClick={() => handleOpenStudentsModal(c)}
                                className="px-2 py-1 text-xs text-slate-700 hover:bg-slate-100 rounded border border-slate-200 transition-colors cursor-pointer"
                              >
                                Xem SV
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
        {/* TAB 2: COURSES LIST (Danh mục học phần) */}
        {/* ===================================================================== */}
        {activeTab === "COURSES" && (
          <div className="space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between flex-wrap gap-2 sm:gap-3 bg-white p-3 rounded-lg border border-slate-200 shadow-xs">
              <SearchInput
                value={coursesInput}
                onChange={(v) => {
                  setCoursesInput(v);
                  setCoursesPage(1);
                }}
                placeholder="Tìm theo mã môn hoặc tên môn..."
                ariaLabel="Tìm kiếm học phần"
                className="w-full sm:max-w-sm"
              />
            </div>

            <div className="bg-white rounded-lg border border-slate-200 shadow-xs overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                      <th className="px-4 py-3 w-12 text-center">STT</th>
                      <th className="px-4 py-3">Mã môn</th>
                      <th className="px-4 py-3">Tên học phần</th>
                      <th className="px-4 py-3 text-center hidden md:table-cell">Tín chỉ</th>
                      <th className="px-4 py-3 text-center hidden md:table-cell">Số buổi chuẩn</th>
                      <th className="px-4 py-3 text-right">Thao tác</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-xs text-slate-700">
                    {isCoursesLoading ? (
                      <tr>
                        <td colSpan={6} className="px-4 py-12 text-center text-slate-400">
                          <div className="flex flex-col items-center justify-center gap-2">
                            <Loader2 size={24} className="animate-spin text-slate-500" />
                            <span>Đang tải danh mục học phần...</span>
                          </div>
                        </td>
                      </tr>
                    ) : courses.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="px-4 py-12 text-center text-slate-400">
                          Chưa có học phần nào. Hãy tạo học phần trước khi mở lớp.
                        </td>
                      </tr>
                    ) : (
                      courses.map((c, idx) => (
                        <tr key={c.id} className="hover:bg-slate-50/75 transition-colors">
                          <td className="px-4 py-3 text-center font-mono tabular-nums text-slate-400">
                            {idx + 1}
                          </td>
                          <td className="px-4 py-3 font-mono font-semibold text-slate-900 tabular-nums">
                            {c.course_code}
                          </td>
                          <td className="px-4 py-3 font-medium text-slate-900">
                            {c.course_name}
                          </td>
                          <td className="px-4 py-3 text-center font-mono tabular-nums text-slate-700 hidden md:table-cell">
                            {c.credits}
                          </td>
                          <td className="px-4 py-3 text-center font-mono tabular-nums text-slate-700 hidden md:table-cell">
                            {c.default_sessions}
                          </td>
                          <td className="px-4 py-3 text-right">
                            <div className="flex items-center justify-end gap-1.5">
                              <button
                                onClick={() => openEditCourseModal(c)}
                                title="Sửa học phần"
                                className="p-1.5 text-slate-600 hover:bg-slate-100 rounded transition-colors cursor-pointer"
                              >
                                <Pencil size={14} />
                              </button>
                              <button
                                onClick={() => setCourseToDelete(c)}
                                title="Xóa học phần"
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
        {/* TAB 3: ADMIN CLASSES LIST (Lớp sinh hoạt) */}
        {/* ===================================================================== */}
        {activeTab === "ADMIN_CLASSES" && (
          <div className="space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between flex-wrap gap-2 sm:gap-3 bg-white p-3 rounded-lg border border-slate-200 shadow-xs">
              <SearchInput
                value={adminClassesInput}
                onChange={(v) => {
                  setAdminClassesInput(v);
                  setAdminClassesPage(1);
                }}
                placeholder="Tìm theo mã lớp hoặc khoa..."
                ariaLabel="Tìm kiếm lớp sinh hoạt"
                className="w-full sm:max-w-sm"
              />
            </div>

            <div className="bg-white rounded-lg border border-slate-200 shadow-xs overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                      <th className="px-4 py-3 w-12 text-center">STT</th>
                      <th className="px-4 py-3">Mã lớp SH</th>
                      <th className="px-4 py-3 hidden md:table-cell">Niên khóa</th>
                      <th className="px-4 py-3 hidden md:table-cell">Khoa</th>
                      <th className="px-4 py-3">Cố vấn học tập</th>
                      <th className="px-4 py-3 text-center">Sĩ số</th>
                      <th className="px-4 py-3 text-right">Thao tác</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-xs text-slate-700">
                    {isAdminClassesLoading ? (
                      <tr>
                        <td colSpan={7} className="px-4 py-12 text-center text-slate-400">
                          <div className="flex flex-col items-center justify-center gap-2">
                            <Loader2 size={24} className="animate-spin text-slate-500" />
                            <span>Đang tải danh sách lớp sinh hoạt...</span>
                          </div>
                        </td>
                      </tr>
                    ) : adminClasses.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="px-4 py-12 text-center text-slate-400">
                          Chưa có lớp sinh hoạt nào được tạo
                        </td>
                      </tr>
                    ) : (
                      adminClasses.map((c, idx) => (
                        <tr key={c.id} className="hover:bg-slate-50/75 transition-colors">
                          <td className="px-4 py-3 text-center font-mono tabular-nums text-slate-400">
                            {idx + 1}
                          </td>
                          <td className="px-4 py-3 font-mono font-semibold text-slate-900 tabular-nums">
                            {c.class_code}
                          </td>
                          <td className="px-4 py-3 font-mono text-slate-600 hidden md:table-cell">
                            {c.academic_year || "-"}
                          </td>
                          <td className="px-4 py-3 text-slate-700 hidden md:table-cell">
                            {c.faculty || "-"}
                          </td>
                          <td className="px-4 py-3 text-slate-700">
                            {c.homeroom_teacher_name || "Chưa phân công"}
                          </td>
                          <td className="px-4 py-3 text-center">
                            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-mono font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                              <Users size={12} />
                              <span className="tabular-nums">{c.student_count}</span> SV
                            </span>
                          </td>
                          <td className="px-4 py-3 text-right">
                            <div className="flex items-center justify-end gap-1.5">
                              <button
                                onClick={() => openEditAdminClassModal(c)}
                                title="Sửa lớp sinh hoạt"
                                className="p-1.5 text-slate-600 hover:bg-slate-100 rounded transition-colors cursor-pointer"
                              >
                                <Pencil size={14} />
                              </button>
                              <button
                                onClick={() => setAdminClassToDelete(c)}
                                title="Xóa lớp sinh hoạt"
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
        {/* TAB 4: SCHEDULES LIST */}
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
                    Học phần / Môn học <span className="text-rose-500">*</span>
                  </label>
                  <select
                    value={newCourseId}
                    onChange={handleCourseSelect}
                    className="w-full px-3 py-2 text-xs rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                  >
                    <option value="">-- Chọn học phần --</option>
                    {courses.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.course_code} - {c.course_name}
                      </option>
                    ))}
                  </select>
                  {/* Lớp cũ chưa gán môn: giữ tên môn cũ và cho phép nhập tay sang môn mới. */}
                  {(!newCourseId || editingClass) && (
                    <input
                      type="text"
                      value={newCourseName}
                      onChange={(e) => setNewCourseName(e.target.value)}
                      placeholder="Hoặc nhập tên môn học mới..."
                      className="mt-2 w-full px-3 py-2 text-xs rounded-md border border-dashed border-slate-300 bg-slate-50 focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                    />
                  )}
                  {courses.length === 0 && (
                    <p className="mt-1.5 text-[11px] text-amber-600">
                      Chưa có học phần nào. Hãy tạo ở tab Học phần trước, hoặc nhập tên môn để hệ thống tự tạo.
                    </p>
                  )}
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
                    Sinh viên trong lớp học phần
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

              {/* Ghi danh theo lớp SH — cố định (lớp SH quản lý ở tab "Lớp sinh hoạt") */}
              <div className="p-3 sm:p-4 bg-slate-50 border-b border-slate-200 space-y-2 shrink-0">
                {studentsModalError && (
                  <div className="flex items-start gap-2 p-2.5 text-xs bg-rose-50 border border-rose-200 text-rose-700 rounded-md">
                    <AlertCircle size={15} className="shrink-0 mt-0.5" />
                    <span>{studentsModalError}</span>
                  </div>
                )}
                <p className="text-[11px] text-slate-500">
                  Ghi danh cả lớp sinh hoạt (quản lý ở tab Lớp sinh hoạt) vào lớp học phần này. SV chưa
                  đúng lớp SH thì sửa ở Quản lý người dùng.
                </p>
                <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
                  <SearchInput
                    value={shEnrollSearch}
                    onChange={setShEnrollSearch}
                    placeholder="Tìm lớp SH..."
                    ariaLabel="Tìm kiếm lớp sinh hoạt để ghi danh"
                    className="flex-1"
                  />
                  <button
                    onClick={handleAddShClasses}
                    disabled={isAddingStudent || shEnrollChecked.length === 0}
                    className="flex items-center justify-center gap-1 px-3 py-2 sm:py-1.5 min-h-[38px] text-xs font-medium text-white bg-slate-900 hover:bg-slate-800 rounded-md transition-colors disabled:opacity-50 cursor-pointer shrink-0"
                  >
                    {isAddingStudent ? <Loader2 size={13} className="animate-spin" /> : <UserPlus size={14} />}
                    <span>Ghi danh{shEnrollChecked.length > 0 ? ` (${shEnrollChecked.length} lớp)` : ""}</span>
                  </button>
                </div>
                <div className="max-h-40 overflow-y-auto rounded-md border border-slate-200 bg-white divide-y divide-slate-100">
                  {visibleShOptions.length === 0 ? (
                    <p className="px-3 py-4 text-xs text-slate-400 text-center">
                      {shClassOptions.length === 0 ? "Chưa có lớp SH nào" : "Không tìm thấy lớp SH phù hợp"}
                    </p>
                  ) : (
                    visibleShOptions.map((ac) => (
                      <label
                        key={ac.id}
                        className="flex items-center gap-2 px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50 cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={shEnrollChecked.includes(ac.id)}
                          onChange={(e) =>
                            setShEnrollChecked((prev) =>
                              e.target.checked ? [...prev, ac.id] : prev.filter((id) => id !== ac.id)
                            )
                          }
                          className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-900 cursor-pointer"
                        />
                        <span className="font-mono font-medium tabular-nums">{ac.class_code}</span>
                        <span className="text-slate-400 truncate">
                          {ac.faculty ? `· ${ac.faculty}` : ""}{" "}
                          <span className="tabular-nums">({ac.student_count} SV)</span>
                        </span>
                      </label>
                    ))
                  )}
                </div>
              </div>

              {/* Student Table + search */}
              <div className="px-3 sm:px-4 pt-3">
                <SearchInput
                  value={studentsModalSearch}
                  onChange={setStudentsModalSearch}
                  placeholder="Tìm trong lớp: MSSV / tên..."
                  ariaLabel="Tìm kiếm sinh viên trong lớp"
                  className="w-full"
                />
              </div>
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
                        <th className="px-3 py-2 text-center">Xếp loại</th>
                        <th className="px-3 py-2 text-right">Xóa</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 text-xs text-slate-700">
                      {isLoadingStudents ? (
                        <tr>
                          <td colSpan={8} className="px-4 py-8 text-center text-slate-400">
                            <Loader2 size={20} className="animate-spin mx-auto text-slate-400 mb-1" />
                            Đang tải danh sách...
                          </td>
                        </tr>
                      ) : visibleStudents.length === 0 ? (
                        <tr>
                          <td colSpan={8} className="px-4 py-8 text-center text-slate-400">
                            Không tìm thấy sinh viên phù hợp
                          </td>
                        </tr>
                      ) : (
                        visibleStudents.map((st, idx) => (
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
                              {st.total_point ?? (st.is_officer ? 100 : 95)}đ
                            </td>
                            <td className="px-3 py-2 text-center">
                              {(() => {
                                const rank = getConductRank(st.total_point ?? (st.is_officer ? 100 : 95), null, st.is_officer);
                                return (
                                  <span
                                    className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold border ${rank.color}`}
                                  >
                                    {rank.label}
                                  </span>
                                );
                              })()}
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
        <ScheduleBulkModal
          isOpen={isBulkModalOpen}
          onClose={() => setIsBulkModalOpen(false)}
          onSuccess={(info) => {
            queryClient.invalidateQueries({ queryKey: ["admin-schedules"] });
            setFeedbackMsg({
              type: "success",
              text: `Đã sinh ${info.created} buổi học` + (info.skipped > 0 ? `, bỏ qua ${info.skipped} ngày trùng` : ""),
            });
          }}
          classes={classes}
        />

        {/* ===================================================================== */}
        {/* MODAL: CREATE / EDIT COURSE */}
        {/* ===================================================================== */}
        {isCourseModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
            <div className="relative w-full max-w-lg max-h-[90vh] flex flex-col bg-white rounded-lg shadow-xl border border-slate-200 overflow-hidden">
              <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50/50 shrink-0">
                <h3 className="text-base font-semibold text-slate-900">
                  {editingCourse ? `Sửa học phần ${editingCourse.course_code}` : "Thêm học phần mới"}
                </h3>
                <button
                  onClick={() => {
                    setIsCourseModalOpen(false);
                    setEditingCourse(null);
                  }}
                  className="p-1.5 text-slate-400 hover:text-slate-600 rounded-md hover:bg-slate-100 transition-colors cursor-pointer"
                >
                  <X size={18} />
                </button>
              </div>

              <form onSubmit={handleCourseSubmit} className="flex flex-col min-h-0 flex-1 overflow-hidden">
                <div className="flex-1 overflow-y-auto overscroll-contain p-6 space-y-4">
                  {courseError && (
                    <div className="flex items-start gap-2 p-3 text-xs bg-rose-50 border border-rose-200 text-rose-700 rounded-md">
                      <AlertCircle size={15} className="shrink-0 mt-0.5" />
                      <span>{courseError}</span>
                    </div>
                  )}

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">
                        Mã môn <span className="text-rose-500">*</span>
                      </label>
                      <input
                        type="text"
                        value={courseCode}
                        onChange={(e) => setCourseCode(e.target.value)}
                        placeholder="INT101"
                        className="w-full px-3 py-2 text-xs font-mono uppercase rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">
                        Số tín chỉ <span className="text-rose-500">*</span>
                      </label>
                      <input
                        type="number"
                        min={1}
                        max={10}
                        value={courseCredits}
                        onChange={(e) => setCourseCredits(parseInt(e.target.value) || 3)}
                        className="w-full px-3 py-2 text-xs font-mono rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Tên học phần <span className="text-rose-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={courseName}
                      onChange={(e) => setCourseName(e.target.value)}
                      placeholder="Nhập môn Trí tuệ Nhân tạo"
                      className="w-full px-3 py-2 text-xs rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                    />
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">
                        Số buổi chuẩn <span className="text-rose-500">*</span>
                      </label>
                      <input
                        type="number"
                        min={1}
                        max={45}
                        value={courseDefaultSessions}
                        onChange={(e) => setCourseDefaultSessions(parseInt(e.target.value) || 15)}
                        className="w-full px-3 py-2 text-xs font-mono rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">
                        Mô tả
                      </label>
                      <input
                        type="text"
                        value={courseDescription}
                        onChange={(e) => setCourseDescription(e.target.value)}
                        placeholder="Đề cương môn học (tùy chọn)"
                        className="w-full px-3 py-2 text-xs rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                      />
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-end gap-3 px-6 py-3 border-t border-slate-200 bg-slate-50/50 shrink-0">
                  <button
                    type="button"
                    onClick={() => {
                      setIsCourseModalOpen(false);
                      setEditingCourse(null);
                    }}
                    className="px-4 py-2 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-md hover:bg-slate-50 transition-colors cursor-pointer"
                  >
                    Hủy bỏ
                  </button>
                  <button
                    type="submit"
                    disabled={isSavingCourse}
                    className="flex items-center gap-2 px-4 py-2 text-xs font-medium text-white bg-slate-900 hover:bg-slate-800 rounded-md transition-colors disabled:opacity-50 cursor-pointer"
                  >
                    {isSavingCourse && <Loader2 size={14} className="animate-spin" />}
                    {editingCourse ? "Lưu thay đổi" : "Tạo học phần"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* ===================================================================== */}
        {/* MODAL: CREATE / EDIT ADMIN CLASS */}
        {/* ===================================================================== */}
        {isAdminClassModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
            <div className="relative w-full max-w-lg max-h-[90vh] flex flex-col bg-white rounded-lg shadow-xl border border-slate-200 overflow-hidden">
              <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50/50 shrink-0">
                <h3 className="text-base font-semibold text-slate-900">
                  {editingAdminClass ? `Sửa lớp sinh hoạt ${editingAdminClass.class_code}` : "Tạo lớp sinh hoạt mới"}
                </h3>
                <button
                  onClick={() => {
                    setIsAdminClassModalOpen(false);
                    setEditingAdminClass(null);
                  }}
                  className="p-1.5 text-slate-400 hover:text-slate-600 rounded-md hover:bg-slate-100 transition-colors cursor-pointer"
                >
                  <X size={18} />
                </button>
              </div>

              <form onSubmit={handleAdminClassSubmit} className="flex flex-col min-h-0 flex-1 overflow-hidden">
                <div className="flex-1 overflow-y-auto overscroll-contain p-6 space-y-4">
                  {adminClassError && (
                    <div className="flex items-start gap-2 p-3 text-xs bg-rose-50 border border-rose-200 text-rose-700 rounded-md">
                      <AlertCircle size={15} className="shrink-0 mt-0.5" />
                      <span>{adminClassError}</span>
                    </div>
                  )}

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">
                        Mã lớp sinh hoạt <span className="text-rose-500">*</span>
                      </label>
                      <input
                        type="text"
                        value={adminClassCode}
                        onChange={(e) => setAdminClassCode(e.target.value)}
                        placeholder="24CNTT1A"
                        className="w-full px-3 py-2 text-xs font-mono uppercase rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">
                        Niên khóa
                      </label>
                      <input
                        type="text"
                        value={adminClassYear}
                        onChange={(e) => setAdminClassYear(e.target.value)}
                        placeholder="2024-2028"
                        className="w-full px-3 py-2 text-xs font-mono rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Khoa / Viện
                    </label>
                    <input
                      type="text"
                      value={adminClassFaculty}
                      onChange={(e) => setAdminClassFaculty(e.target.value)}
                      placeholder="Công nghệ Thông tin"
                      className="w-full px-3 py-2 text-xs rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Cố vấn học tập
                    </label>
                    <select
                      value={adminClassTeacherId}
                      onChange={(e) => setAdminClassTeacherId(e.target.value ? Number(e.target.value) : "")}
                      className="w-full px-3 py-2 text-xs rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                    >
                      <option value="">-- Chưa phân công --</option>
                      {teachers.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.user_code} - {t.full_name}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="flex items-center justify-end gap-3 px-6 py-3 border-t border-slate-200 bg-slate-50/50 shrink-0">
                  <button
                    type="button"
                    onClick={() => {
                      setIsAdminClassModalOpen(false);
                      setEditingAdminClass(null);
                    }}
                    className="px-4 py-2 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-md hover:bg-slate-50 transition-colors cursor-pointer"
                  >
                    Hủy bỏ
                  </button>
                  <button
                    type="submit"
                    disabled={isSavingAdminClass}
                    className="flex items-center gap-2 px-4 py-2 text-xs font-medium text-white bg-slate-900 hover:bg-slate-800 rounded-md transition-colors disabled:opacity-50 cursor-pointer"
                  >
                    {isSavingAdminClass && <Loader2 size={14} className="animate-spin" />}
                    {editingAdminClass ? "Lưu thay đổi" : "Tạo lớp"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

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
        <ConfirmDialog
          open={courseToDelete !== null}
          onOpenChange={(open) => {
            if (!open) setCourseToDelete(null);
          }}
          title="Xóa học phần"
          description={
            courseToDelete
              ? `Bạn có chắc chắn muốn xóa học phần [${courseToDelete.course_code}] ${courseToDelete.course_name}?`
              : ""
          }
          confirmLabel={isDeletingCourse ? "Đang xử lý..." : "Xóa học phần"}
          onConfirm={() => {
            if (!courseToDelete || isDeletingCourse) return;
            deleteCourseMutation.mutate(courseToDelete.id);
          }}
          isPending={isDeletingCourse}
        />
        <ConfirmDialog
          open={adminClassToDelete !== null}
          onOpenChange={(open) => {
            if (!open) setAdminClassToDelete(null);
          }}
          title="Xóa lớp sinh hoạt"
          description={
            adminClassToDelete
              ? `Bạn có chắc chắn muốn xóa lớp sinh hoạt [${adminClassToDelete.class_code}]?`
              : ""
          }
          confirmLabel={isDeletingAdminClass ? "Đang xử lý..." : "Xóa lớp"}
          onConfirm={() => {
            if (!adminClassToDelete || isDeletingAdminClass) return;
            deleteAdminClassMutation.mutate(adminClassToDelete.id);
          }}
          isPending={isDeletingAdminClass}
        />
      </div>
    </RoleGuard>
  );
}
