"use client";

// Chân lý hiển thị khớp backend conduct_rank.py:
// Xuất sắc: chỉ ban cán sự + điểm >= 90. SV thường trần Tốt kể cả 100.
// Tốt 80-100, Khá 65-<80, Trung bình 50-<65, Yếu 35-<50, Kém <35.

export type ConductRankLabel =
  | "Xuất sắc"
  | "Tốt"
  | "Khá"
  | "Trung bình"
  | "Yếu"
  | "Kém";

export interface ConductRank {
  label: ConductRankLabel;
  color: string;
  bar: string;
  description: string;
}

const RANK_META: Record<ConductRankLabel, Omit<ConductRank, "label">> = {
  "Xuất sắc": {
    color: "text-emerald-700 bg-emerald-50 border-emerald-200",
    bar: "bg-emerald-600",
    description: "Duy trì tác phong chuẩn mực và đi học đầy đủ.",
  },
  Tốt: {
    color: "text-sky-700 bg-sky-50 border-sky-200",
    bar: "bg-sky-600",
    description: "Mặc định tối đa cho sinh viên (100 điểm vẫn loại Tốt).",
  },
  Khá: {
    color: "text-amber-700 bg-amber-50 border-amber-200",
    bar: "bg-amber-500",
    description: "Cần lưu ý tuân thủ giờ giấc và quy định đồng phục.",
  },
  "Trung bình": {
    color: "text-yellow-700 bg-yellow-50 border-yellow-200",
    bar: "bg-yellow-500",
    description: "Điểm rèn luyện ở mức trung bình, cần cải thiện chuyên cần.",
  },
  Yếu: {
    color: "text-orange-700 bg-orange-50 border-orange-200",
    bar: "bg-orange-500",
    description: "Điểm rèn luyện yếu, nguy cơ cảnh báo học vụ.",
  },
  Kém: {
    color: "text-rose-700 bg-rose-50 border-rose-200",
    bar: "bg-rose-500",
    description: "Điểm rèn luyện kém! Nguy cơ bị cấm thi nếu tiếp tục vắng.",
  },
};

export function defaultPoint(isOfficer: boolean = false): number {
  return isOfficer ? 100 : 95;
}

export function classifyConductRankLabel(
  totalPoint: number | null | undefined,
  isOfficer: boolean = false,
): ConductRankLabel {
  const fallback = defaultPoint(isOfficer);
  const p = totalPoint == null || Number.isNaN(Number(totalPoint)) ? fallback : Number(totalPoint);
  const clamped = Math.min(100, Math.max(0, p));
  if (isOfficer && clamped >= 90) return "Xuất sắc";
  if (clamped >= 80) return "Tốt";
  if (clamped >= 65) return "Khá";
  if (clamped >= 50) return "Trung bình";
  if (clamped >= 35) return "Yếu";
  return "Kém";
}

export function getConductRank(
  totalPoint: number | null | undefined,
  serverRank?: string | null,
  isOfficer: boolean = false,
): ConductRank {
  const label =
    serverRank && serverRank in RANK_META
      ? (serverRank as ConductRankLabel)
      : classifyConductRankLabel(totalPoint, isOfficer);
  return { label, ...RANK_META[label] };
}
