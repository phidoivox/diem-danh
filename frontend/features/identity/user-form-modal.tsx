"use client";

import React, { useEffect, useRef } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AdminAdministrativeClass, AdminUser, createAdminUser, getStudentAdministrativeClassOptions, mediaUrl, updateAdminUser, uploadUserAvatar } from "@/features/shell";
import {
  MAX_AVATAR_SIZE,
  userCreateSchema,
  userUpdateSchema,
  validateUploadFile,
  type UserCreateFormValues,
  type UserUpdateFormValues,
} from "@/features/shell";
import { X, Loader2, ShieldAlert, GraduationCap, Briefcase, Shield, ImagePlus, Trash2, Camera, ChevronDown } from "lucide-react";
import { UserAvatar } from "@/features/shell";

interface UserFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  user?: AdminUser | null;
}

export function UserFormModal({
  isOpen,
  onClose,
  onSuccess,
  user,
}: UserFormModalProps) {
  const isEdit = !!user;

  // Hai schema riêng: tạo mới bắt buộc user_code+password, sửa cho phép bỏ trống password.
  const createForm = useForm<UserCreateFormValues>({
    resolver: zodResolver(userCreateSchema),
    defaultValues: {
      role: "STUDENT",
      user_code: "",
      full_name: "",
      email: "",
      password: "",
      class_name: "",
      major: "",
      department: "",
      academic_title: "",
      office_room: "",
    },
  });
  const updateForm = useForm<UserUpdateFormValues>({
    resolver: zodResolver(userUpdateSchema),
    defaultValues: {
      full_name: "",
      email: "",
      password: "",
      class_name: "",
      major: "",
      department: "",
      academic_title: "",
      office_room: "",
    },
  });
  const [role, setRole] = React.useState<"STUDENT" | "TEACHER" | "ADMIN">("STUDENT");
  const [isActive, setIsActive] = React.useState(true);
  const [serverError, setServerError] = React.useState<string | null>(null);
  const [avatarFile, setAvatarFile] = React.useState<File | null>(null);
  const [avatarPreview, setAvatarPreview] = React.useState<string | null>(null);
  const [avatarError, setAvatarError] = React.useState<string | null>(null);
  const [isDragging, setIsDragging] = React.useState(false);
  const [classNameOptions, setClassNameOptions] = React.useState<AdminAdministrativeClass[]>([]);
  const [selectedAdminClassId, setSelectedAdminClassId] = React.useState<number | null>(null);
  const avatarInputRef = useRef<HTMLInputElement | null>(null);

  const activeForm = isEdit ? updateForm : createForm;
  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = activeForm as unknown as ReturnType<typeof useForm<UserCreateFormValues>>;
  const classNameValue = (watch("class_name") as string | undefined) ?? "";

  // Đồng bộ state hiển thị + reset form khi mở modal / đổi user (cần setState
  // trong effect theo đúng pattern modal edit).
  useEffect(() => {
    const userRole = (
      (user && (user.role_name || user.role)) ||
      "STUDENT"
    ).toUpperCase() as "STUDENT" | "TEACHER" | "ADMIN";
    /* eslint-disable react-hooks/set-state-in-effect -- modal cần đồng bộ state khi mở/đổi user */
    setRole(userRole);
    setIsActive(user?.is_active ?? true);
    setServerError(null);
    setAvatarError(null);
    setAvatarFile(null);
    setIsDragging(false);
    // Thu hồi preview blob cũ để tránh leak bộ nhớ khi đổi user / mở lại modal.
    setAvatarPreview((prev) => {
      if (prev?.startsWith("blob:")) URL.revokeObjectURL(prev);
      return null;
    });
    /* eslint-enable react-hooks/set-state-in-effect */
    if (user) {
      updateForm.reset({
        full_name: user.full_name || "",
        email: user.email || "",
        password: "",
        class_name: user.student_profile?.class_name || "",
        major: user.student_profile?.major || "",
        department: user.teacher_profile?.department || "",
        academic_title: user.teacher_profile?.academic_title || "",
        office_room: user.teacher_profile?.office_room || "",
      });
    } else {
      createForm.reset({
        role: "STUDENT",
        user_code: "",
        full_name: "",
        email: "",
        password: "",
        class_name: "",
        major: "",
        department: "",
        academic_title: "",
        office_room: "",
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, isOpen]);

  // Combobox lớp SH: state riêng cho ô tìm kiếm, đồng bộ với react-hook-form.
  const [classNameOpen, setClassNameOpen] = React.useState(false);
  const [classNameQuery, setClassNameQuery] = React.useState("");
  const classNameBoxRef = useRef<HTMLDivElement | null>(null);
  const filteredClassNames = classNameOptions.filter(
    (ac) =>
      ac.class_code.toLowerCase().includes(classNameQuery.trim().toLowerCase()) ||
      (ac.faculty || "").toLowerCase().includes(classNameQuery.trim().toLowerCase())
  );

  // Danh sách lớp SH đã có để chọn nhanh khi tạo/sửa SV (vẫn cho nhập tay lớp mới).
  useEffect(() => {
    if (!isOpen) return;
    setClassNameOpen(false);
    setClassNameQuery(user?.student_profile?.class_name || "");
    setSelectedAdminClassId(user?.student_profile?.admin_class_id ?? null);
    getStudentAdministrativeClassOptions()
      .then((items) => {
        setClassNameOptions(items);
        // SV cũ có mã lớp nhưng chưa có link id: map theo class_code để submit giữ nguyên.
        const cur = user?.student_profile;
        if (cur && !cur.admin_class_id && cur.class_name) {
          const hit = items.find((ac) => ac.class_code === cur.class_name);
          if (hit) setSelectedAdminClassId(hit.id);
        }
      })
      .catch(() => setClassNameOptions([]));
  }, [isOpen, user]);

  // Đóng dropdown lớp SH khi click ra ngoài.
  useEffect(() => {
    if (!classNameOpen) return;
    const onDown = (e: MouseEvent) => {
      if (!classNameBoxRef.current?.contains(e.target as Node)) setClassNameOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [classNameOpen]);

  if (!isOpen) return null;

  const existingAvatarSrc = mediaUrl(user?.avatar_url);
  const displayAvatarSrc = avatarPreview || existingAvatarSrc;

  const handleAvatarSelect = (file: File | undefined) => {
    if (!file) return;
    const err = validateUploadFile(file, {
      maxSize: MAX_AVATAR_SIZE,
      types: ["image/jpeg", "image/png"],
    });
    if (err) {
      setAvatarError(err);
      return;
    }
    setAvatarError(null);
    setAvatarPreview((prev) => {
      if (prev?.startsWith("blob:")) URL.revokeObjectURL(prev);
      return URL.createObjectURL(file);
    });
    setAvatarFile(file);
  };

  const handleAvatarRemove = () => {
    setAvatarFile(null);
    setAvatarError(null);
    setAvatarPreview((prev) => {
      if (prev?.startsWith("blob:")) URL.revokeObjectURL(prev);
      return null;
    });
    if (avatarInputRef.current) avatarInputRef.current.value = "";
  };

  const onSubmit = async (values: UserCreateFormValues & UserUpdateFormValues) => {
    setServerError(null);
    try {
      if (isEdit && user) {
        const updatePayload: Record<string, string | boolean | number> = {
          full_name: values.full_name,
          email: values.email,
          is_active: isActive,
        };
        if (values.password?.trim()) updatePayload.password = values.password.trim();
        if (role === "STUDENT") {
          updatePayload.class_name = values.class_name?.trim() ?? "";
          if (selectedAdminClassId) updatePayload.admin_class_id = selectedAdminClassId;
          updatePayload.major = values.major?.trim() ?? "";
        } else if (role === "TEACHER") {
          updatePayload.department = values.department?.trim() ?? "";
          updatePayload.academic_title = values.academic_title?.trim() ?? "";
          updatePayload.office_room = values.office_room?.trim() ?? "";
        }
        await updateAdminUser(user.id, updatePayload);
        // Bước 2: upload avatar (nếu có chọn file mới).
        if (avatarFile) {
          try {
            await uploadUserAvatar(user.id, avatarFile);
          } catch (avatarErr: unknown) {
            setServerError(
              `Đã lưu thông tin nhưng upload avatar thất bại: ${
                avatarErr instanceof Error ? avatarErr.message : "lỗi không xác định"
              }`
            );
            onSuccess();
            return;
          }
        }
      } else {
        const createPayload: Record<string, string | number | undefined> = {
          role_name: role,
          user_code: values.user_code,
          full_name: values.full_name,
          email: values.email,
          password: values.password?.trim(),
        };
        if (role === "STUDENT") {
          createPayload.class_name = values.class_name?.trim() ?? "";
          if (selectedAdminClassId) createPayload.admin_class_id = selectedAdminClassId;
          createPayload.major = values.major?.trim() ?? "";
        } else if (role === "TEACHER") {
          createPayload.department = values.department?.trim() ?? "";
          createPayload.academic_title = values.academic_title?.trim() ?? "";
          createPayload.office_room = values.office_room?.trim() ?? "";
        }
        // Tạo user trước (chưa có ID nên chưa upload được), rồi upload avatar sau.
        const created = await createAdminUser(createPayload);
        if (avatarFile) {
          try {
            await uploadUserAvatar(created.id, avatarFile);
          } catch (avatarErr: unknown) {
            setServerError(
              `Đã tạo tài khoản ${created.user_code} nhưng upload avatar thất bại: ${
                avatarErr instanceof Error ? avatarErr.message : "lỗi không xác định"
              }. Bạn có thể mở Sửa để thử lại.`
            );
            onSuccess();
            return;
          }
        }
      }
      onSuccess();
      onClose();
    } catch (err: unknown) {
      setServerError(err instanceof Error ? err.message : "Đã xảy ra lỗi trong quá trình lưu");
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/40 backdrop-blur-xs p-3 sm:p-4">
      <div className="flex min-h-full items-center justify-center">
      <div className="relative w-full max-w-2xl max-h-[90vh] flex flex-col bg-white rounded-lg shadow-xl border border-slate-200 overflow-hidden">
        {/* Header — cố định */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50/50 shrink-0">
          <div>
            <h3 className="text-base font-semibold text-slate-900">
              {isEdit ? "Chỉnh sửa thông tin người dùng" : "Thêm mới tài khoản người dùng"}
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              {isEdit
                ? `Cập nhật thông tin và quyền hạn cho ${user?.user_code}`
                : "Điền thông tin tài khoản và phân quyền người dùng trong hệ thống"}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-600 rounded-md hover:bg-slate-100 transition-colors cursor-pointer"
          >
            <X size={18} />
          </button>
        </div>

        {/* Form — body cuộn giữa, footer cố định đáy */}
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col min-h-0 flex-1 overflow-hidden">
          <div className="flex-1 overflow-y-auto overscroll-contain p-4 sm:p-6 space-y-4">
          {serverError && (
            <div className="flex items-start gap-2.5 p-3 text-xs bg-rose-50 border border-rose-200 text-rose-700 rounded-md">
              <ShieldAlert size={16} className="shrink-0 text-rose-500 mt-0.5" />
              <span>{serverError}</span>
            </div>
          )}

          {/* Avatar — preview lớn + dropzone + badge trạng thái */}
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setIsDragging(false);
              handleAvatarSelect(e.dataTransfer.files?.[0]);
            }}
            className={`flex flex-col sm:flex-row items-center sm:items-start gap-4 p-4 rounded-xl border transition-colors ${
              isDragging
                ? "border-dashed border-slate-900 bg-slate-50"
                : "bg-slate-50/60 border-slate-200"
            }`}
          >
            <div className="flex flex-col items-center gap-2 shrink-0">
              <div className="relative group">
                {displayAvatarSrc ? (
                  <UserAvatar
                    src={displayAvatarSrc}
                    name={user?.full_name || "Ảnh đại diện"}
                    size="xl"
                    showStatusDot={false}
                  />
                ) : (
                  <span className="inline-flex h-24 w-24 items-center justify-center rounded-full border-2 border-dashed border-slate-300 bg-slate-100 text-slate-400">
                    <ImagePlus size={28} />
                  </span>
                )}
                <button
                  type="button"
                  onClick={() => avatarInputRef.current?.click()}
                  disabled={isSubmitting}
                  title="Chọn / thay ảnh"
                  className="absolute bottom-0.5 right-0.5 p-1.5 rounded-full bg-slate-900 text-white shadow-md hover:bg-slate-700 transition-colors disabled:opacity-50 cursor-pointer"
                >
                  <Camera size={13} />
                </button>
              </div>
            </div>
            <div className="min-w-0 flex-1 text-center sm:text-left">
              <p className="text-xs font-semibold text-slate-800">Ảnh đại diện</p>
              <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">
                JPEG/PNG ≤ 10MB, rõ mặt chính diện — hệ thống cũng thử đăng ký FaceID từ ảnh này.
                {isEdit ? "" : " Ảnh tải lên sau khi tạo tài khoản."}
              </p>
              <p className="hidden sm:block text-[11px] text-slate-400 mt-1">
                Kéo-thả ảnh vào đây hoặc bấm chọn file.
              </p>
              <div className="flex flex-wrap justify-center sm:justify-start items-center gap-2 mt-2.5">
                <input
                  ref={avatarInputRef}
                  type="file"
                  accept="image/jpeg,image/png"
                  className="hidden"
                  onChange={(e) => {
                    handleAvatarSelect(e.target.files?.[0]);
                    e.target.value = "";
                  }}
                />
                <button
                  type="button"
                  onClick={() => avatarInputRef.current?.click()}
                  disabled={isSubmitting}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium text-white bg-slate-900 rounded-md hover:bg-slate-700 transition-colors disabled:opacity-50 cursor-pointer"
                >
                  <ImagePlus size={13} />
                  {displayAvatarSrc ? "Đổi ảnh" : "Chọn ảnh"}
                </button>
                {(avatarFile || avatarPreview) && (
                  <button
                    type="button"
                    onClick={handleAvatarRemove}
                    disabled={isSubmitting}
                    title="Xóa ảnh vừa chọn"
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 text-[11px] font-medium text-rose-600 bg-white border border-slate-200 rounded-md hover:bg-rose-50 hover:border-rose-200 transition-colors disabled:opacity-50 cursor-pointer"
                  >
                    <Trash2 size={12} />
                    Xóa
                  </button>
                )}
              </div>
              {avatarFile && (
                <p className="mt-1.5 text-[11px] text-slate-500 font-mono truncate">
                  {avatarFile.name} ({(avatarFile.size / 1024).toFixed(0)} KB)
                </p>
              )}
              {avatarError && <p className="mt-1 text-[11px] text-rose-600">{avatarError}</p>}
            </div>
          </div>

          {/* Role selector (only in create mode) */}
          {!isEdit ? (
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Vai trò hệ thống <span className="text-rose-500">*</span>
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                <button
                  type="button"
                  onClick={() => setRole("STUDENT")}
                  className={`flex items-center justify-center gap-2 p-2.5 rounded-md border text-xs font-medium transition-all cursor-pointer ${
                    role === "STUDENT"
                      ? "border-emerald-500 bg-emerald-50/60 text-emerald-800 ring-1 ring-emerald-500"
                      : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                  }`}
                >
                  <GraduationCap size={16} className={role === "STUDENT" ? "text-emerald-600" : "text-slate-400"} />
                  Sinh viên
                </button>

                <button
                  type="button"
                  onClick={() => setRole("TEACHER")}
                  className={`flex items-center justify-center gap-2 p-2.5 rounded-md border text-xs font-medium transition-all cursor-pointer ${
                    role === "TEACHER"
                      ? "border-sky-500 bg-sky-50/60 text-sky-800 ring-1 ring-sky-500"
                      : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                  }`}
                >
                  <Briefcase size={16} className={role === "TEACHER" ? "text-sky-600" : "text-slate-400"} />
                  Giảng viên
                </button>

                <button
                  type="button"
                  onClick={() => setRole("ADMIN")}
                  className={`flex items-center justify-center gap-2 p-2.5 rounded-md border text-xs font-medium transition-all cursor-pointer ${
                    role === "ADMIN"
                      ? "border-indigo-500 bg-indigo-50/60 text-indigo-800 ring-1 ring-indigo-500"
                      : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                  }`}
                >
                  <Shield size={16} className={role === "ADMIN" ? "text-indigo-600" : "text-slate-400"} />
                  Quản trị viên
                </button>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-2 p-2.5 bg-slate-50 rounded-md border border-slate-200">
              <span className="text-xs text-slate-500">Vai trò:</span>
              <span
                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium border ${
                  role === "ADMIN"
                    ? "bg-indigo-50 text-indigo-700 border-indigo-200"
                    : role === "TEACHER"
                    ? "bg-sky-50 text-sky-700 border-sky-200"
                    : "bg-emerald-50 text-emerald-700 border-emerald-200"
                }`}
              >
                {role === "ADMIN" ? "Quản trị viên" : role === "TEACHER" ? "Giảng viên" : "Sinh viên"}
              </span>
            </div>
          )}

          {/* User Code & Full Name */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Mã người dùng <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                {...register("user_code")}
                disabled={isEdit}
                placeholder={role === "STUDENT" ? "SV001" : role === "TEACHER" ? "GV001" : "AD001"}
                className="w-full px-3 py-2 text-xs font-mono rounded-md border border-slate-200 bg-white disabled:bg-slate-100 disabled:text-slate-500 focus:outline-hidden focus:ring-1 focus:ring-slate-900 focus:border-slate-900 uppercase"
              />
              {errors.user_code && (
                <p className="mt-1 text-[11px] text-rose-600">{errors.user_code.message}</p>
              )}
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Họ và tên <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                {...register("full_name")}
                placeholder="Nguyễn Văn A"
                className="w-full px-3 py-2 text-xs rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900 focus:border-slate-900"
              />
              {errors.full_name && (
                <p className="mt-1 text-[11px] text-rose-600">{errors.full_name.message}</p>
              )}
            </div>
          </div>

          {/* Email & Password */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Địa chỉ Email <span className="text-rose-500">*</span>
              </label>
              <input
                type="email"
                {...register("email")}
                placeholder="user@university.edu.vn"
                className="w-full px-3 py-2 text-xs font-mono rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900 focus:border-slate-900"
              />
              {errors.email && (
                <p className="mt-1 text-[11px] text-rose-600">{errors.email.message}</p>
              )}
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                {isEdit ? "Mật khẩu mới (bỏ trống nếu không đổi)" : "Mật khẩu khởi tạo"}{" "}
                {!isEdit && <span className="text-rose-500">*</span>}
              </label>
              <input
                type="password"
                {...register("password")}
                placeholder={isEdit ? "••••••••" : "Tối thiểu 6 ký tự"}
                className="w-full px-3 py-2 text-xs font-mono rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900 focus:border-slate-900"
              />
              {errors.password && (
                <p className="mt-1 text-[11px] text-rose-600">{errors.password.message}</p>
              )}
            </div>
          </div>

          {/* Edit mode: Active status */}
          {isEdit && (
            <div className="flex items-center gap-2 pt-1">
              <input
                type="checkbox"
                id="is_active"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-900 cursor-pointer"
              />
              <label htmlFor="is_active" className="text-xs text-slate-700 font-medium cursor-pointer">
                Tài khoản đang hoạt động (Active)
              </label>
            </div>
          )}

          {/* Profile Details depending on Role */}
          {role === "STUDENT" && (
            <div className="pt-2 border-t border-slate-200">
              <h4 className="text-xs font-semibold text-slate-800 mb-3 flex items-center gap-1.5">
                <GraduationCap size={15} className="text-emerald-600" />
                Thông tin hồ sơ Sinh viên
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Lớp sinh hoạt</label>
                  <div ref={classNameBoxRef} className="relative">
                    <input
                      type="text"
                      value={classNameOpen ? classNameQuery : classNameValue}
                      onChange={(e) => {
                        const v = e.target.value.toUpperCase();
                        setClassNameQuery(v);
                        setValue("class_name", v);
                        const hit = classNameOptions.find((ac) => ac.class_code === v);
                        setSelectedAdminClassId(hit ? hit.id : null);
                      }}
                      onFocus={() => {
                        setClassNameQuery(classNameValue || "");
                        setClassNameOpen(true);
                      }}
                      placeholder="Gõ để tìm hoặc thêm lớp mới (VD: 21KTPM01)"
                      className="w-full px-3 py-2 pr-8 text-xs rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900 focus:border-slate-900 uppercase font-mono"
                    />
                    <button
                      type="button"
                      tabIndex={-1}
                      onClick={() => {
                        setClassNameQuery(classNameValue || "");
                        setClassNameOpen((o) => !o);
                      }}
                      className="absolute right-1.5 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-700 cursor-pointer"
                      title="Mở danh sách lớp"
                    >
                      <ChevronDown size={14} className={`transition-transform ${classNameOpen ? "rotate-180" : ""}`} />
                    </button>
                    {classNameOpen && (
                      <div className="absolute z-10 mt-1 max-h-44 w-full overflow-y-auto rounded-md border border-slate-200 bg-white shadow-lg">
                        {filteredClassNames.length === 0 ? (
                          <button
                            type="button"
                            onMouseDown={(e) => e.preventDefault()}
                            onClick={() => {
                              setValue("class_name", classNameQuery.trim().toUpperCase());
                              setSelectedAdminClassId(null);
                              setClassNameOpen(false);
                            }}
                            className="block w-full px-3 py-2 text-left text-xs text-slate-700 hover:bg-slate-50 cursor-pointer"
                          >
                            {classNameQuery.trim()
                              ? `Dùng lớp mới "${classNameQuery.trim().toUpperCase()}"`
                              : "Chưa có lớp SH nào — gõ tên lớp mới"}
                          </button>
                        ) : (
                          filteredClassNames.map((ac) => (
                            <button
                              key={ac.id}
                              type="button"
                              onMouseDown={(e) => e.preventDefault()}
                              onClick={() => {
                                setValue("class_name", ac.class_code);
                                setSelectedAdminClassId(ac.id);
                                setClassNameOpen(false);
                              }}
                              className={`flex items-center justify-between gap-2 w-full px-3 py-2 text-left text-xs font-mono uppercase hover:bg-slate-50 cursor-pointer ${
                                ac.class_code === classNameValue ? "bg-emerald-50 text-emerald-800 font-semibold" : "text-slate-700"
                              }`}
                            >
                              <span>{ac.class_code}</span>
                              <span className="text-[10px] text-slate-400 normal-case tabular-nums">
                                {ac.student_count} SV{ac.faculty ? ` · ${ac.faculty}` : ""}
                              </span>
                            </button>
                          ))
                        )}
                      </div>
                    )}
                  </div>
                  <input type="hidden" {...register("class_name")} />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Chuyên ngành</label>
                  <input
                    type="text"
                    {...register("major")}
                    placeholder="Kỹ thuật phần mềm, Trí tuệ nhân tạo..."
                    className="w-full px-3 py-2 text-xs rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900 focus:border-slate-900"
                  />
                </div>
              </div>
            </div>
          )}

          {role === "TEACHER" && (
            <div className="pt-2 border-t border-slate-200">
              <h4 className="text-xs font-semibold text-slate-800 mb-3 flex items-center gap-1.5">
                <Briefcase size={15} className="text-sky-600" />
                Thông tin hồ sơ Giảng viên
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Khoa / Bộ môn</label>
                  <input
                    type="text"
                    {...register("department")}
                    placeholder="Khoa CNTT"
                    className="w-full px-3 py-2 text-xs rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900 focus:border-slate-900"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Học vị / Chức danh</label>
                  <input
                    type="text"
                    {...register("academic_title")}
                    placeholder="ThS, TS, PGS.TS"
                    className="w-full px-3 py-2 text-xs rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900 focus:border-slate-900"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Văn phòng</label>
                  <input
                    type="text"
                    {...register("office_room")}
                    placeholder="C2-301"
                    className="w-full px-3 py-2 text-xs font-mono rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900 focus:border-slate-900"
                  />
                </div>
              </div>
            </div>
          )}
          </div>

          {/* Footer Actions — cố định */}
          <div className="flex flex-col-reverse sm:flex-row sm:items-center sm:justify-end flex-wrap gap-2 sm:gap-3 px-4 sm:px-6 py-3 border-t border-slate-200 bg-slate-50/50 shrink-0">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="w-full sm:w-auto inline-flex justify-center px-4 py-2 min-h-[36px] items-center text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-md hover:bg-slate-50 transition-colors disabled:opacity-50 cursor-pointer"
            >
              Hủy bỏ
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full sm:w-auto flex items-center justify-center gap-2 px-4 py-2 min-h-[36px] text-xs font-medium text-white bg-slate-900 hover:bg-slate-800 rounded-md transition-colors disabled:opacity-50 cursor-pointer"
            >
              {isSubmitting && <Loader2 size={14} className="animate-spin" />}
              {isEdit ? "Lưu thay đổi" : "Tạo tài khoản"}
            </button>
          </div>
        </form>
      </div>
      </div>
    </div>
  );
}
