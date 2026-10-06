"use client";

import { cn } from "./modal";

export type AttendanceStatus =
  | "PRESENT"
  | "LATE"
  | "ABSENT"
  | "HALF_ABSENT"
  | "EXCUSED"
  | (string & {});

const STATUS_META: Record<string, { label: string; classes: string; dot: string }> = {
  PRESENT: {
    label: "Có mặt",
    classes: "bg-emerald-50 text-emerald-700 border-emerald-200",
    dot: "bg-emerald-500",
  },
  LATE: {
    label: "Đi muộn",
    classes: "bg-amber-50 text-amber-700 border-amber-200",
    dot: "bg-amber-500",
  },
  ABSENT: {
    label: "Vắng",
    classes: "bg-rose-50 text-rose-700 border-rose-200",
    dot: "bg-rose-500",
  },
  HALF_ABSENT: {
    label: "Nửa buổi",
    classes: "bg-sky-50 text-sky-700 border-sky-200",
    dot: "bg-sky-500",
  },
  EXCUSED: {
    label: "Có phép",
    classes: "bg-blue-50 text-blue-700 border-blue-200",
    dot: "bg-blue-500",
  },
};

interface StatusBadgeProps {
  status: AttendanceStatus;
  className?: string;
}

/**
 * Badge trạng thái điểm danh dùng chung (thay các `renderStatusBadge`
 * copy-paste ở teacher/live + student/attendance).
 */
export function StatusBadge({ status, className }: StatusBadgeProps) {
  const key = (status || "").toUpperCase();
  const meta = STATUS_META[key] ?? {
    label: status || "—",
    classes: "bg-slate-100 text-slate-600 border-slate-200",
    dot: "bg-slate-400",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-[11px] font-medium",
        meta.classes,
        className
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", meta.dot)} />
      {meta.label}
    </span>
  );
}
