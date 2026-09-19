"use client";

import React, { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ColumnDef } from "@tanstack/react-table";
import { RoleGuard } from "@/components/layout/role-guard";
import {
  AdminUser,
  deleteAdminUser,
  getAdminUsers,
} from "@/lib/api";
import { DataTable } from "@/components/ui/data-table";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { UserFormModal } from "@/components/admin/user-form-modal";
import {
  Users,
  Search,
  Plus,
  Edit2,
  Trash2,
  Shield,
  GraduationCap,
  Briefcase,
  CheckCircle2,
  XCircle,
  RotateCcw,
} from "lucide-react";

const PAGE_SIZE = 15;

function RoleBadge({ user }: { user: AdminUser }) {
  const r = (user.role_name || user.role || "").toUpperCase();
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
}

export default function AdminUsersPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1); // 1-based cho API
  const [roleFilter, setRoleFilter] = useState<string>("ALL");
  const [searchInput, setSearchInput] = useState("");
  const [searchTerm, setSearchTerm] = useState("");

  // Modal states
  const [isUserModalOpen, setIsUserModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<AdminUser | null>(null);
  const [deletingUser, setDeletingUser] = useState<AdminUser | null>(null);

  const [feedbackMsg, setFeedbackMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // react-query thay useState+useEffect+fetchUsers tay: cache theo filter, tự
  // refetch khi invalidate sau create/update/delete/enroll.
  const usersQuery = useQuery({
    queryKey: ["admin-users", page, roleFilter, searchTerm],
    queryFn: () =>
      getAdminUsers({ page, size: PAGE_SIZE, role: roleFilter, q: searchTerm }),
    placeholderData: (prev) => prev,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteAdminUser(id),
    onSuccess: (_, id) => {
      const target = usersQuery.data?.items?.find((u) => u.id === id);
      setFeedbackMsg({
        type: "success",
        text: `Đã vô hiệu hóa tài khoản ${target?.user_code ?? id} thành công`,
      });
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: (err: unknown) => {
      setFeedbackMsg({
        type: "error",
        text: err instanceof Error ? err.message : "Không thể xóa người dùng",
      });
    },
  });

  const users = usersQuery.data?.items ?? [];
  const total = usersQuery.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    setSearchTerm(searchInput.trim());
  };

  const handleRoleChange = (newRole: string) => {
    setRoleFilter(newRole);
    setPage(1);
  };

  const handleDeleteUser = (u: AdminUser) => {
    setDeletingUser(u);
  };

  const handleConfirmDelete = () => {
    if (!deletingUser) return;
    deleteMutation.mutate(deletingUser.id, {
      onSuccess: () => setDeletingUser(null),
    });
  };

  const refresh = (text: string) => {
    queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    setFeedbackMsg({ type: "success", text });
  };

  const columns = useMemo<ColumnDef<AdminUser>[]>(
    () => [
      {
        header: "STT",
        cell: ({ row }) => (
          <span className="font-mono tabular-nums text-slate-400">
            {(page - 1) * PAGE_SIZE + row.index + 1}
          </span>
        ),
      },
      {
        accessorKey: "user_code",
        header: "Mã ND",
        cell: ({ row }) => (
          <span className="font-mono font-medium text-slate-900 tabular-nums">
            {row.original.user_code}
          </span>
        ),
      },
      {
        accessorKey: "full_name",
        header: "Họ và tên",
        cell: ({ row }) => <span className="font-medium text-slate-900">{row.original.full_name}</span>,
      },
      {
        accessorKey: "email",
        header: "Email",
        cell: ({ row }) => (
          <span className="font-mono text-slate-600 text-[11px]">{row.original.email}</span>
        ),
      },
      {
        id: "role",
        header: "Vai trò",
        cell: ({ row }) => <RoleBadge user={row.original} />,
      },
      {
        id: "profile",
        header: "Hồ sơ chi tiết",
        enableSorting: false,
        cell: ({ row }) => {
          const u = row.original;
          const isStudent = (u.role_name || u.role || "").toUpperCase() === "STUDENT";
          const isTeacher = (u.role_name || u.role || "").toUpperCase() === "TEACHER";
          if (isStudent && u.student_profile) {
            return (
              <div>
                <span className="font-mono text-slate-800 font-medium">
                  {u.student_profile.class_name || "Chưa gán lớp"}
                </span>
                {u.student_profile.major && (
                  <span className="text-slate-400 ml-1.5 text-[11px]">({u.student_profile.major})</span>
                )}
                <div className="text-[11px] text-slate-400 font-mono">
                  ĐRL: {u.student_profile.total_point}đ
                </div>
              </div>
            );
          }
          if (isTeacher && u.teacher_profile) {
            return (
              <div>
                <span className="text-slate-800 font-medium">
                  {u.teacher_profile.department || "Khoa"}
                </span>
                {u.teacher_profile.academic_title && (
                  <span className="text-slate-500 ml-1">- {u.teacher_profile.academic_title}</span>
                )}
                {u.teacher_profile.office_room && (
                  <div className="text-[11px] text-slate-400 font-mono">
                    Phòng: {u.teacher_profile.office_room}
                  </div>
                )}
              </div>
            );
          }
          return <span className="text-slate-400 italic">Quản trị toàn trường</span>;
        },
      },
      {
        id: "status",
        header: "Trạng thái",
        cell: ({ row }) =>
          row.original.is_active ? (
            <span className="inline-flex items-center gap-1 text-[11px] text-emerald-700 font-medium">
              <CheckCircle2 size={13} className="text-emerald-500" />
              Hoạt động
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 text-[11px] text-slate-500 font-medium">
              <XCircle size={13} className="text-rose-400" />
              Đã khóa
            </span>
          ),
      },
      {
        id: "actions",
        header: "Thao tác",
        enableSorting: false,
        cell: ({ row }) => {
          const u = row.original;
          return (
            <div className="flex items-center justify-end gap-1">
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
              <button
                onClick={() => handleDeleteUser(u)}
                title="Khóa / Xóa mềm tài khoản"
                className="p-1.5 text-rose-600 hover:bg-rose-50 rounded transition-colors cursor-pointer"
              >
                <Trash2 size={15} />
              </button>
            </div>
          );
        },
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [page]
  );

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
        {usersQuery.isError && (
          <div className="p-3 text-xs rounded-md border bg-rose-50 text-rose-800 border-rose-200">
            {usersQuery.error instanceof Error
              ? usersQuery.error.message
              : "Không thể tải danh sách người dùng"}
          </div>
        )}

        {/* Filter and Search Bar */}
        <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 bg-white p-3 rounded-lg border border-slate-200 shadow-xs">
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

          <form onSubmit={handleSearchSubmit} className="flex items-center gap-2 max-w-md w-full">
            <div className="relative flex-1">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
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
            {(searchTerm || searchInput) && (
              <button
                type="button"
                onClick={() => {
                  setSearchInput("");
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

        {/* Data Table (TanStack Table, server pagination) */}
        <div className="bg-white rounded-lg border border-slate-200 shadow-xs p-3">
          <DataTable<AdminUser>
            columns={columns}
            data={users}
            pageSize={PAGE_SIZE}
            isLoading={usersQuery.isFetching}
            emptyMessage="Không tìm thấy người dùng nào phù hợp với bộ lọc"
            manualPagination={{
              pageCount: totalPages,
              pageIndex: page - 1,
              onPageChange: (idx) => setPage(idx + 1),
              totalRows: total,
            }}
          />
        </div>

        {/* Modals */}
        <ConfirmDialog
          open={deletingUser !== null}
          onOpenChange={(open) => {
            if (!open) setDeletingUser(null);
          }}
          title="Vô hiệu hóa người dùng"
          description={
            deletingUser
              ? `Bạn có chắc chắn muốn vô hiệu hóa / xóa mềm người dùng [${deletingUser.user_code}] ${deletingUser.full_name}?`
              : ""
          }
          confirmLabel="Vô hiệu hóa"
          onConfirm={handleConfirmDelete}
          isPending={deleteMutation.isPending}
        />
        <UserFormModal
          isOpen={isUserModalOpen}
          onClose={() => {
            setIsUserModalOpen(false);
            setEditingUser(null);
          }}
          onSuccess={() => {
            refresh(editingUser ? "Cập nhật người dùng thành công" : "Tạo người dùng mới thành công");
          }}
          user={editingUser}
        />
      </div>
    </RoleGuard>
  );
}
