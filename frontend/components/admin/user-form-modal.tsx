"use client";

import React, { useState, useEffect } from "react";
import { AdminUser, createAdminUser, updateAdminUser } from "@/lib/api";
import { X, Loader2, ShieldAlert, GraduationCap, Briefcase, Shield } from "lucide-react";

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

  const [role, setRole] = useState<"STUDENT" | "TEACHER" | "ADMIN">("STUDENT");
  const [userCode, setUserCode] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isActive, setIsActive] = useState(true);

  // Student profile fields
  const [className, setClassName] = useState("");
  const [major, setMajor] = useState("");

  // Teacher profile fields
  const [department, setDepartment] = useState("");
  const [academicTitle, setAcademicTitle] = useState("");
  const [officeRoom, setOfficeRoom] = useState("");

  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (user) {
      const userRole = (user.role_name || user.role || "STUDENT").toUpperCase() as
        | "STUDENT"
        | "TEACHER"
        | "ADMIN";
      setRole(userRole);
      setUserCode(user.user_code || "");
      setFullName(user.full_name || "");
      setEmail(user.email || "");
      setPassword("");
      setIsActive(user.is_active ?? true);

      if (user.student_profile) {
        setClassName(user.student_profile.class_name || "");
        setMajor(user.student_profile.major || "");
      } else {
        setClassName("");
        setMajor("");
      }

      if (user.teacher_profile) {
        setDepartment(user.teacher_profile.department || "");
        setAcademicTitle(user.teacher_profile.academic_title || "");
        setOfficeRoom(user.teacher_profile.office_room || "");
      } else {
        setDepartment("");
        setAcademicTitle("");
        setOfficeRoom("");
      }
    } else {
      setRole("STUDENT");
      setUserCode("");
      setFullName("");
      setEmail("");
      setPassword("");
      setIsActive(true);
      setClassName("");
      setMajor("");
      setDepartment("");
      setAcademicTitle("");
      setOfficeRoom("");
    }
    setErrorMessage(null);
  }, [user, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!fullName.trim() || !email.trim()) {
      setErrorMessage("Vui lòng điền đầy đủ họ tên và email");
      return;
    }

    if (!isEdit) {
      if (!userCode.trim()) {
        setErrorMessage("Vui lòng nhập mã người dùng");
        return;
      }
      if (!password || password.length < 6) {
        setErrorMessage("Mật khẩu phải có ít nhất 6 ký tự");
        return;
      }
    }

    setIsLoading(true);

    try {
      if (isEdit && user) {
        const updatePayload: Record<string, any> = {
          full_name: fullName.trim(),
          email: email.trim().toLowerCase(),
          is_active: isActive,
        };
        if (password.trim()) {
          updatePayload.password = password.trim();
        }
        if (role === "STUDENT") {
          updatePayload.class_name = className.trim();
          updatePayload.major = major.trim();
        } else if (role === "TEACHER") {
          updatePayload.department = department.trim();
          updatePayload.academic_title = academicTitle.trim();
          updatePayload.office_room = officeRoom.trim();
        }

        await updateAdminUser(user.id, updatePayload);
      } else {
        const createPayload: Record<string, any> = {
          role_name: role,
          user_code: userCode.trim().toUpperCase(),
          full_name: fullName.trim(),
          email: email.trim().toLowerCase(),
          password: password.trim(),
        };
        if (role === "STUDENT") {
          createPayload.class_name = className.trim();
          createPayload.major = major.trim();
        } else if (role === "TEACHER") {
          createPayload.department = department.trim();
          createPayload.academic_title = academicTitle.trim();
          createPayload.office_room = officeRoom.trim();
        }

        await createAdminUser(createPayload);
      }

      onSuccess();
      onClose();
    } catch (err: any) {
      setErrorMessage(err.message || "Đã xảy ra lỗi trong quá trình lưu");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4 overflow-y-auto">
      <div className="relative w-full max-w-2xl bg-white rounded-lg shadow-xl border border-slate-200 overflow-hidden my-8">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50/50">
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

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {errorMessage && (
            <div className="flex items-start gap-2.5 p-3 text-xs bg-rose-50 border border-rose-200 text-rose-700 rounded-md">
              <ShieldAlert size={16} className="shrink-0 text-rose-500 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Role selector (only in create mode) */}
          {!isEdit ? (
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Vai trò hệ thống <span className="text-rose-500">*</span>
              </label>
              <div className="grid grid-cols-3 gap-2.5">
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
                value={userCode}
                onChange={(e) => setUserCode(e.target.value)}
                disabled={isEdit}
                placeholder={role === "STUDENT" ? "SV001" : role === "TEACHER" ? "GV001" : "AD001"}
                className="w-full px-3 py-2 text-xs font-mono rounded-md border border-slate-200 bg-white disabled:bg-slate-100 disabled:text-slate-500 focus:outline-hidden focus:ring-1 focus:ring-slate-900 focus:border-slate-900 uppercase"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Họ và tên <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Nguyễn Văn A"
                className="w-full px-3 py-2 text-xs rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900 focus:border-slate-900"
              />
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
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="user@university.edu.vn"
                className="w-full px-3 py-2 text-xs font-mono rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900 focus:border-slate-900"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                {isEdit ? "Mật khẩu mới (bỏ trống nếu không đổi)" : "Mật khẩu khởi tạo"}{" "}
                {!isEdit && <span className="text-rose-500">*</span>}
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={isEdit ? "••••••••" : "Tối thiểu 6 ký tự"}
                className="w-full px-3 py-2 text-xs font-mono rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900 focus:border-slate-900"
              />
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
                  <input
                    type="text"
                    value={className}
                    onChange={(e) => setClassName(e.target.value)}
                    placeholder="VD: 21KTPM01, 22CNTT02"
                    className="w-full px-3 py-2 text-xs rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900 focus:border-slate-900 uppercase font-mono"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Chuyên ngành</label>
                  <input
                    type="text"
                    value={major}
                    onChange={(e) => setMajor(e.target.value)}
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
                    value={department}
                    onChange={(e) => setDepartment(e.target.value)}
                    placeholder="Khoa CNTT"
                    className="w-full px-3 py-2 text-xs rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900 focus:border-slate-900"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Học vị / Chức danh</label>
                  <input
                    type="text"
                    value={academicTitle}
                    onChange={(e) => setAcademicTitle(e.target.value)}
                    placeholder="ThS, TS, PGS.TS"
                    className="w-full px-3 py-2 text-xs rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900 focus:border-slate-900"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Văn phòng</label>
                  <input
                    type="text"
                    value={officeRoom}
                    onChange={(e) => setOfficeRoom(e.target.value)}
                    placeholder="C2-301"
                    className="w-full px-3 py-2 text-xs font-mono rounded-md border border-slate-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900 focus:border-slate-900"
                  />
                </div>
              </div>
            </div>
          )}

          {/* Footer Actions */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-200">
            <button
              type="button"
              onClick={onClose}
              disabled={isLoading}
              className="px-4 py-2 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-md hover:bg-slate-50 transition-colors disabled:opacity-50 cursor-pointer"
            >
              Hủy bỏ
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="flex items-center gap-2 px-4 py-2 text-xs font-medium text-white bg-slate-900 hover:bg-slate-800 rounded-md transition-colors disabled:opacity-50 cursor-pointer"
            >
              {isLoading && <Loader2 size={14} className="animate-spin" />}
              {isEdit ? "Lưu thay đổi" : "Tạo tài khoản"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
