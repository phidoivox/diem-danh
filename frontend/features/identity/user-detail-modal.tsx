"use client";

import type { AdminUser } from "@/features/shell";
import { Modal } from "@/features/shell";
import { UserAvatar } from "@/features/shell";

interface UserDetailModalProps {
  user: AdminUser | null;
  onClose: () => void;
}

function roleLabel(role?: string | null) {
  const r = (role || "").toUpperCase();
  if (r === "ADMIN") return "Quản trị viên";
  if (r === "TEACHER") return "Giảng viên";
  return "Sinh viên";
}

function InfoItem({ label, value, mono }: { label: string; value?: string | null; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <p className="text-[11px] text-slate-400">{label}</p>
      <p
        className={`mt-0.5 truncate text-xs font-medium text-slate-800 ${mono ? "font-mono" : ""}`}
        title={value ?? undefined}
      >
        {value || "—"}
      </p>
    </div>
  );
}

export function UserDetailModal({ user, onClose }: UserDetailModalProps) {
  const role = (user?.role_name || user?.role || "").toUpperCase();
  const created = user?.created_at ? new Date(user.created_at).toLocaleDateString("vi-VN") : null;

  return (
    <Modal
      open={user !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title="Chi tiết hồ sơ"
      description={user ? `[${user.user_code}] ${user.full_name}` : undefined}
      footer={
        <button
          type="button"
          onClick={onClose}
          className="inline-flex min-h-[36px] items-center justify-center px-4 py-2 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-md hover:bg-slate-50 transition-colors cursor-pointer"
        >
          Đóng
        </button>
      }
    >
      {user && (
        <div className="space-y-4 p-4 sm:p-6">
          <div className="flex items-center gap-3">
            <UserAvatar user={user} size="lg" showStatusDot={false} />
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-slate-900">{user.full_name}</p>
              <p className="mt-0.5 truncate font-mono text-[11px] text-slate-500">
                {user.user_code} • {user.email}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <InfoItem label="Vai trò" value={roleLabel(user.role_name || user.role)} />
            <InfoItem label="Trạng thái" value={user.is_active ? "Hoạt động" : "Đã khóa"} />
            <InfoItem label="Email" value={user.email} mono />
            <InfoItem label="Ngày tạo" value={created} />
          </div>

          {role === "STUDENT" && (
            <div className="space-y-3 border-t border-slate-200 pt-3">
              <p className="text-xs font-semibold text-slate-800">Hồ sơ sinh viên</p>
              <div className="grid grid-cols-2 gap-3">
                <InfoItem label="Lớp" value={user.student_profile?.class_name} mono />
                <InfoItem label="Chuyên ngành" value={user.student_profile?.major} />
                <InfoItem
                  label="Điểm rèn luyện"
                  value={
                    user.student_profile != null ? `${user.student_profile.total_point}đ` : null
                  }
                />
              </div>
            </div>
          )}

          {role === "TEACHER" && (
            <div className="space-y-3 border-t border-slate-200 pt-3">
              <p className="text-xs font-semibold text-slate-800">Hồ sơ giảng viên</p>
              <div className="grid grid-cols-2 gap-3">
                <InfoItem label="Khoa / Bộ môn" value={user.teacher_profile?.department} />
                <InfoItem label="Học vị / Chức danh" value={user.teacher_profile?.academic_title} />
                <InfoItem label="Văn phòng" value={user.teacher_profile?.office_room} mono />
              </div>
            </div>
          )}

          {role === "ADMIN" && (
            <p className="border-t border-slate-200 pt-3 text-xs italic text-slate-400">
              Quản trị toàn trường
            </p>
          )}
        </div>
      )}
    </Modal>
  );
}
