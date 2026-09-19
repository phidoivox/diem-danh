import { z } from "zod";

/**
 * Schema xác thực tập trung (thay các `if (!trim) setErrorMessage(...)` viết
 * tay trong từng modal). Dùng với `@hookform/resolvers/zod` + react-hook-form.
 */

export const loginSchema = z.object({
  identifier: z.string().trim().min(1, "Vui lòng nhập mã người dùng hoặc email."),
  password: z.string().min(1, "Vui lòng nhập mật khẩu."),
});
export type LoginFormValues = z.infer<typeof loginSchema>;

const roleEnum = z.enum(["STUDENT", "TEACHER", "ADMIN"]);

export const userCreateSchema = z.object({
  // Vai trò do nút chọn ngoài form quản lý (state `role`), schema chỉ validate các ô nhập.
  role: roleEnum.optional(),
  user_code: z
    .string()
    .trim()
    .min(1, "Vui lòng nhập mã người dùng")
    .transform((s) => s.toUpperCase()),
  full_name: z.string().trim().min(1, "Vui lòng điền họ tên"),
  email: z
    .string()
    .trim()
    .toLowerCase()
    .email("Email không hợp lệ"),
  password: z.string().min(6, "Mật khẩu phải có ít nhất 6 ký tự"),
  class_name: z.string().trim().optional(),
  major: z.string().trim().optional(),
  department: z.string().trim().optional(),
  academic_title: z.string().trim().optional(),
  office_room: z.string().trim().optional(),
});
export type UserCreateFormValues = z.infer<typeof userCreateSchema>;

export const userUpdateSchema = z.object({
  full_name: z.string().trim().min(1, "Vui lòng điền họ tên"),
  email: z
    .string()
    .trim()
    .toLowerCase()
    .email("Email không hợp lệ"),
  password: z
    .string()
    .refine((s) => s === "" || (s ?? "").length >= 6, "Mật khẩu mới phải có ít nhất 6 ký tự")
    .optional(),
  class_name: z.string().trim().optional(),
  major: z.string().trim().optional(),
  department: z.string().trim().optional(),
  academic_title: z.string().trim().optional(),
  office_room: z.string().trim().optional(),
});
export type UserUpdateFormValues = z.infer<typeof userUpdateSchema>;

export const scheduleSchema = z
  .object({
    room_name: z.string().trim().min(1, "Vui lòng nhập phòng học"),
    study_date: z.string().min(1, "Vui lòng chọn ngày học"),
    start_time: z.string().min(1, "Vui lòng chọn giờ bắt đầu"),
    end_time: z.string().min(1, "Vui lòng chọn giờ kết thúc"),
  })
  .refine((v) => v.start_time < v.end_time, {
    message: "Giờ bắt đầu phải nhỏ hơn giờ kết thúc",
    path: ["end_time"],
  });
export type ScheduleFormValues = z.infer<typeof scheduleSchema>;

export const scheduleFullSchema = scheduleSchema.extend({
  class_id: z.number({ message: "Vui lòng chọn lớp học phần" }).int().positive("Vui lòng chọn lớp học phần"),
  session_order: z.number({ message: "Vui lòng nhập thứ tự buổi" }).int().min(1),
});
export type ScheduleFullFormValues = z.infer<typeof scheduleFullSchema>;

export const ACCEPTED_PROOF_TYPES = ["image/jpeg", "image/png", "application/pdf"] as const;
export const MAX_PROOF_SIZE = 5 * 1024 * 1024; // 5MB (khớp backend storage_service)
export const MAX_AVATAR_SIZE = 10 * 1024 * 1024;

export const leaveRequestSchema = z.object({
  schedule_id: z.number({ message: "Vui lòng chọn buổi học" }).int().positive("Vui lòng chọn buổi học"),
  reason: z.string().trim().min(5, "Lý do nghỉ phải có ít nhất 5 ký tự"),
});
export type LeaveRequestFormValues = z.infer<typeof leaveRequestSchema>;

export function validateUploadFile(
  file: File,
  opts: { maxSize?: number; types?: readonly string[] } = {}
): string | null {
  const maxSize = opts.maxSize ?? MAX_PROOF_SIZE;
  const types = opts.types ?? ACCEPTED_PROOF_TYPES;
  if (!types.includes(file.type as (typeof types)[number])) {
    return `Định dạng ${file.type || "không xác định"} không hợp lệ. Chỉ nhận JPEG/PNG/PDF.`;
  }
  if (file.size > maxSize) {
    return `File vượt quá ${(maxSize / 1024 / 1024).toFixed(0)}MB.`;
  }
  return null;
}
