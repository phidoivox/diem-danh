"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ColumnDef } from "@tanstack/react-table";
import { toast } from "sonner";
import { RoleGuard } from "@/features/shell";
import { AdminUser, deleteAdminUser, getAdminUsers } from "@/features/shell";
import { UserAvatar } from "@/features/shell";
import { DataTable } from "@/features/shell";
import { ConfirmDialog } from "@/features/shell";
import { UserFormModal } from "./user-form-modal";
import { UserDetailModal } from "./user-detail-modal";
import { SearchInput } from "@/features/shell";
import { useDebouncedValue } from "@/features/shell";
import {
  Users,
  Plus,
  Edit2,
  Trash2,
  Shield,
  GraduationCap,
  Briefcase,
  CheckCircle2,
  XCircle,
  Eye,
} from "lucide-react";

const PAGE_SIZE = 15;

function RoleBadge({ user }: { user: AdminUser }) {
  const r = (user.role_name || user.role || "").toUpperCase();
  if (r === "ADMIN") {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-indigo-50 text-indigo-700 border border-indigo-200">
        <Shield size={12} />
        Quản trị viên
      </span>
    );
  }
  if (r === "TEACHER") {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-sky-50 text-sky-700 border border-sky-200">
        <Briefcase size={12} />
        Giảng viên
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
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
  // Kiểu tìm kiếm thống nhất: gõ là lọc live, không nút Tìm.
  // Server-side: queryKey chỉ đổi khi dừng gõ 300ms (tránh spam API mỗi phím).
  const searchTerm = useDebouncedValue(searchInput.trim(), 300);

  // Debounce đổi term -> về trang 1 (giữ queryKey [page,...] không nhảy lung tung).
  // roleFilter đổi đã reset trong handleRoleChange, không gộp vào effect này
  // (tránh reset page 2 lần / loop khi tab click).
  useEffect(() => {
    setPage(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchTerm]);

  // Modal states
  const [isUserModalOpen, setIsUserModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<AdminUser | null>(null);
  const [deletingUser, setDeletingUser] = useState<AdminUser | null>(null);
  const [viewingUser, setViewingUser] = useState<AdminUser | null>(null);

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
      toast.success(`Đã vô hiệu hóa tài khoản ${target?.user_code ?? id} thành công`);
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Không thể xóa người dùng");
    },
  });

  const users = usersQuery.data?.items ?? [];
  const total = usersQuery.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

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
    toast.success(text);
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
        id: "user",
        header: "Người dùng",
        cell: ({ row }) => {
          const u = row.original;
          return (
            <div className="flex items-center gap-3 min-w-0">
              <UserAvatar user={u} size="md" />
              <div className="min-w-0">
                <p className="font-medium text-slate-900 truncate leading-tight" title={u.full_name}>
                  {u.full_name}
                </p>
                <p
                  className="text-[11px] text-slate-500 truncate font-mono mt-0.5"
                  title={`${u.user_code} • ${u.email}`}
                >
                  {u.user_code} • {u.email}
                </p>
              </div>
            </div>
          );
        },
      },
      {
        id: "role",
        header: "Vai trò",
        cell: ({ row }) => <RoleBadge user={row.original} />,
      },
      {
        id: "status",
        header: "Trạng thái",
        cell: ({ row }) =>
          row.original.is_active ? (
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
              <CheckCircle2 size={12} className="text-emerald-500" />
              Hoạt động
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-slate-100 text-slate-500 border border-slate-200">
              <XCircle size={12} className="text-rose-400" />
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
                onClick={() => setViewingUser(u)}
                title="Xem chi tiết hồ sơ"
                className="p-1.5 text-slate-600 hover:bg-slate-100 rounded transition-colors cursor-pointer"
              >
                <Eye size={15} />
              </button>
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

        {usersQuery.isError && (
          <div className="p-3 text-xs rounded-md border bg-rose-50 text-rose-800 border-rose-200">
            {usersQuery.error instanceof Error
              ? usersQuery.error.message
              : "Không thể tải danh sách người dùng"}
          </div>
        )}

        {/* Filter and Search Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between flex-wrap gap-2 sm:gap-3 bg-white p-3 rounded-lg border border-slate-200 shadow-xs">
          <div className="flex flex-wrap items-center gap-1">
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

          <SearchInput
            value={searchInput}
            onChange={setSearchInput}
            placeholder="Tìm theo mã, họ tên hoặc email..."
            ariaLabel="Tìm kiếm người dùng"
            className="w-full sm:max-w-xs"
          />
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
        <UserDetailModal user={viewingUser} onClose={() => setViewingUser(null)} />
      </div>
    </RoleGuard>
  );
}
