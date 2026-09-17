"use client";

import React, { useState, useEffect, useCallback } from "react";
import { RoleGuard } from "@/components/layout/role-guard";
import {
  AdminUser,
  getAdminUsers,
  deleteAdminUser,
} from "@/lib/api";
import { UserFormModal } from "@/components/admin/user-form-modal";
import { FaceEnrollModal } from "@/components/admin/face-enroll-modal";
import {
  Users,
  Search,
  Plus,
  Edit2,
  Trash2,
  Camera,
  Shield,
  GraduationCap,
  Briefcase,
  CheckCircle2,
  XCircle,
  ChevronLeft,
  ChevronRight,
  Loader2,
  RotateCcw,
} from "lucide-react";

export default function AdminUsersPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [size] = useState(15);
  const [roleFilter, setRoleFilter] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  // Modal states
  const [isUserModalOpen, setIsUserModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<AdminUser | null>(null);

  const [isFaceModalOpen, setIsFaceModalOpen] = useState(false);
  const [faceEnrollTarget, setFaceEnrollTarget] = useState<AdminUser | null>(null);

  const [feedbackMsg, setFeedbackMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const fetchUsers = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await getAdminUsers({
        page,
        size,
        role: roleFilter,
        q: searchTerm,
      });
      setUsers(data.items || []);
      setTotal(data.total || 0);
    } catch (err: any) {
      setFeedbackMsg({
        type: "error",
        text: err.message || "Không thể tải danh sách người dùng",
      });
    } finally {
      setIsLoading(false);
    }
  }, [page, size, roleFilter, searchTerm]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    setSearchTerm(searchQuery.trim());
  };

  const handleRoleChange = (newRole: string) => {
    setRoleFilter(newRole);
    setPage(1);
  };

  const handleDeleteUser = async (u: AdminUser) => {
    const confirmed = window.confirm(
      `Bạn có chắc chắn muốn vô hiệu hóa / xóa mềm người dùng [${u.user_code}] ${u.full_name}?`
    );
    if (!confirmed) return;

    try {
      await deleteAdminUser(u.id);
      setFeedbackMsg({
        type: "success",
        text: `Đã vô hiệu hóa tài khoản ${u.user_code} thành công`,
      });
      fetchUsers();
    } catch (err: any) {
      setFeedbackMsg({
        type: "error",
        text: err.message || "Không thể xóa người dùng",
      });
    }
  };

  const totalPages = Math.ceil(total / size) || 1;

  const getRoleBadge = (roleName?: string, role?: string) => {
    const r = (roleName || role || "").toUpperCase();
    if (r === "ADMIN") {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-indigo-50 text-indigo-700 border border-indigo-200">
          <Shield size={12} />
          Quản trị viên
        </span>
      );
    }
    if (r === "TEACHER") {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-sky-50 text-sky-700 border border-sky-200">
          <Briefcase size={12} />
          Giảng viên
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
        <GraduationCap size={12} />
        Sinh viên
      </span>
    );
  };

  return (
    <RoleGuard allowedRoles={["ADMIN"]}>
      <div className="space-y-4">
        {/* Page Title & Action */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-200">
          <div>
            <h2 className="text-lg font-semibold text-slate-900 tracking-tight flex items-center gap-2">
              <Users size={20} className="text-slate-700" />
              Quản lý người dùng hệ thống
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Danh sách tài khoản sinh viên, giảng viên và quản trị viên trong toàn trường
            </p>
          </div>

          <button
            onClick={() => {
              setEditingUser(null);
              setIsUserModalOpen(true);
            }}
            className="inline-flex items-center justify-center gap-1.5 px-3.5 py-2 text-xs font-medium text-white bg-slate-900 hover:bg-slate-800 rounded-md transition-colors cursor-pointer shadow-xs"
          >
            <Plus size={15} />
            Thêm người dùng mới
          </button>
        </div>

        {/* Feedback alert */}
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

        {/* Filter and Search Bar */}
        <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 bg-white p-3 rounded-lg border border-slate-200 shadow-xs">
          {/* Role Filter Tabs */}
          <div className="flex items-center gap-1 overflow-x-auto pb-1 md:pb-0">
            {[
              { id: "ALL", label: "Tất cả" },
              { id: "STUDENT", label: "Sinh viên" },
              { id: "TEACHER", label: "Giảng viên" },
              { id: "ADMIN", label: "Quản trị viên" },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => handleRoleChange(tab.id)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium whitespace-nowrap transition-colors cursor-pointer ${
                  roleFilter === tab.id
                    ? "bg-slate-900 text-white"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Search Form */}
          <form onSubmit={handleSearchSubmit} className="flex items-center gap-2 max-w-md w-full">
            <div className="relative flex-1">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Tìm theo mã, họ tên hoặc email..."
                className="w-full pl-8 pr-3 py-1.5 text-xs rounded-md border border-slate-200 bg-slate-50/50 focus:bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900 focus:border-slate-900"
              />
            </div>
            <button
              type="submit"
              className="px-3 py-1.5 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-md transition-colors cursor-pointer"
            >
              Tìm
            </button>
            {(searchTerm || searchQuery) && (
              <button
                type="button"
                onClick={() => {
                  setSearchQuery("");
                  setSearchTerm("");
                  setPage(1);
                }}
                title="Đặt lại tìm kiếm"
                className="p-1.5 text-slate-400 hover:text-slate-600 rounded-md hover:bg-slate-100 transition-colors cursor-pointer"
              >
                <RotateCcw size={14} />
              </button>
            )}
          </form>
        </div>

        {/* Data Table */}
        <div className="bg-white rounded-lg border border-slate-200 shadow-xs overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                  <th className="px-4 py-3 w-12 text-center">STT</th>
                  <th className="px-4 py-3">Mã ND</th>
                  <th className="px-4 py-3">Họ và tên</th>
                  <th className="px-4 py-3">Email</th>
                  <th className="px-4 py-3">Vai trò</th>
                  <th className="px-4 py-3">Hồ sơ chi tiết</th>
                  <th className="px-4 py-3 text-center">Trạng thái</th>
                  <th className="px-4 py-3 text-right">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs text-slate-700">
                {isLoading ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-12 text-center text-slate-400">
                      <div className="flex flex-col items-center justify-center gap-2">
                        <Loader2 size={24} className="animate-spin text-slate-500" />
                        <span>Đang tải danh sách người dùng...</span>
                      </div>
                    </td>
                  </tr>
                ) : users.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-12 text-center text-slate-400">
                      Không tìm thấy người dùng nào phù hợp với bộ lọc
                    </td>
                  </tr>
                ) : (
                  users.map((u, idx) => {
                    const rowNumber = (page - 1) * size + idx + 1;
                    const isStudent = (u.role_name || u.role || "").toUpperCase() === "STUDENT";
                    const isTeacher = (u.role_name || u.role || "").toUpperCase() === "TEACHER";

                    return (
                      <tr key={u.id} className="hover:bg-slate-50/75 transition-colors">
                        <td className="px-4 py-3 text-center font-mono tabular-nums text-slate-400">
                          {rowNumber}
                        </td>
                        <td className="px-4 py-3 font-mono font-medium text-slate-900 tabular-nums">
                          {u.user_code}
                        </td>
                        <td className="px-4 py-3 font-medium text-slate-900">
                          {u.full_name}
                        </td>
                        <td className="px-4 py-3 font-mono text-slate-600 text-[11px]">
                          {u.email}
                        </td>
                        <td className="px-4 py-3">
                          {getRoleBadge(u.role_name, u.role)}
                        </td>
                        <td className="px-4 py-3 text-slate-600">
                          {isStudent && u.student_profile ? (
                            <div>
                              <span className="font-mono text-slate-800 font-medium">
                                {u.student_profile.class_name || "Chưa gán lớp"}
                              </span>
                              {u.student_profile.major && (
                                <span className="text-slate-400 ml-1.5 text-[11px]">
                                  ({u.student_profile.major})
                                </span>
                              )}
                              <div className="text-[11px] text-slate-400 font-mono">
                                ĐRL: {u.student_profile.total_point}đ
                              </div>
                            </div>
                          ) : isTeacher && u.teacher_profile ? (
                            <div>
                              <span className="text-slate-800 font-medium">
                                {u.teacher_profile.department || "Khoa"}
                              </span>
                              {u.teacher_profile.academic_title && (
                                <span className="text-slate-500 ml-1">
                                  - {u.teacher_profile.academic_title}
                                </span>
                              )}
                              {u.teacher_profile.office_room && (
                                <div className="text-[11px] text-slate-400 font-mono">
                                  Phòng: {u.teacher_profile.office_room}
                                </div>
                              )}
                            </div>
                          ) : (
                            <span className="text-slate-400 italic">Quản trị toàn trường</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-center">
                          {u.is_active ? (
                            <span className="inline-flex items-center gap-1 text-[11px] text-emerald-700 font-medium">
                              <CheckCircle2 size={13} className="text-emerald-500" />
                              Hoạt động
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-[11px] text-slate-500 font-medium">
                              <XCircle size={13} className="text-rose-400" />
                              Đã khóa
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex items-center justify-end gap-1">
                            {/* FaceID enroll for student only */}
                            {isStudent && (
                              <button
                                onClick={() => {
                                  setFaceEnrollTarget(u);
                                  setIsFaceModalOpen(true);
                                }}
                                title="Đăng ký FaceID cho sinh viên"
                                className="p-1.5 text-emerald-700 hover:bg-emerald-50 rounded transition-colors cursor-pointer"
                              >
                                <Camera size={15} />
                              </button>
                            )}

                            {/* Edit */}
                            <button
                              onClick={() => {
                                setEditingUser(u);
                                setIsUserModalOpen(true);
                              }}
                              title="Chỉnh sửa thông tin"
                              className="p-1.5 text-slate-600 hover:bg-slate-100 rounded transition-colors cursor-pointer"
                            >
                              <Edit2 size={15} />
                            </button>

                            {/* Soft Delete */}
                            <button
                              onClick={() => handleDeleteUser(u)}
                              title="Khóa / Xóa mềm tài khoản"
                              className="p-1.5 text-rose-600 hover:bg-rose-50 rounded transition-colors cursor-pointer"
                            >
                              <Trash2 size={15} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-200 bg-slate-50/50 text-xs text-slate-500">
            <div>
              Hiển thị{" "}
              <span className="font-mono tabular-nums font-semibold text-slate-700">
                {users.length}
              </span>{" "}
              /{" "}
              <span className="font-mono tabular-nums font-semibold text-slate-700">
                {total}
              </span>{" "}
              người dùng
            </div>

            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1 || isLoading}
                className="p-1.5 border border-slate-200 rounded bg-white hover:bg-slate-50 disabled:opacity-40 transition-colors cursor-pointer"
              >
                <ChevronLeft size={15} />
              </button>
              <span className="px-2 font-mono tabular-nums text-slate-700 font-medium">
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages || isLoading}
                className="p-1.5 border border-slate-200 rounded bg-white hover:bg-slate-50 disabled:opacity-40 transition-colors cursor-pointer"
              >
                <ChevronRight size={15} />
              </button>
            </div>
          </div>
        </div>

        {/* Modals */}
        <UserFormModal
          isOpen={isUserModalOpen}
          onClose={() => {
            setIsUserModalOpen(false);
            setEditingUser(null);
          }}
          onSuccess={() => {
            fetchUsers();
            setFeedbackMsg({
              type: "success",
              text: editingUser ? "Cập nhật người dùng thành công" : "Tạo người dùng mới thành công",
            });
          }}
          user={editingUser}
        />

        <FaceEnrollModal
          isOpen={isFaceModalOpen}
          onClose={() => {
            setIsFaceModalOpen(false);
            setFaceEnrollTarget(null);
          }}
          onSuccess={() => {
            fetchUsers();
            setFeedbackMsg({
              type: "success",
              text: `Đã cập nhật vector FaceID cho sinh viên ${faceEnrollTarget?.user_code}`,
            });
          }}
          user={faceEnrollTarget}
        />
      </div>
    </RoleGuard>
  );
}
