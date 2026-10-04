import type { KioskFaceBox } from "./api";

/**
 * Logic ổn định quyết định kiosk (tách từ kiosk/page.tsx để test được).
 * MediaPipe face-detector.ts giữ nguyên, không đụng vào.
 */

export type StableEntry = {
  shown: string;
  pending: string | null;
  pendingCount: number;
  lastChange: number;
};

export function stabilizeDecisions(
  faces: KioskFaceBox[],
  stable: Map<string, StableEntry>,
  nowMs: number
): KioskFaceBox[] {
  const seen = new Set<string>();
  const out = faces.map((f) => {
    const key = String(f.user_code || f.student_id || f.track_id);
    seen.add(key);
    const st = stable.get(key) || {
      shown: f.decision,
      pending: null as string | null,
      pendingCount: 0,
      lastChange: nowMs,
    };
    if (f.decision === st.shown) {
      st.pending = null;
      st.pendingCount = 0;
    } else if (f.decision === st.pending) {
      st.pendingCount += 1;
      const timeout = f.decision === "SPOOF" ? 1200 : 800;
      if (st.pendingCount >= 2 || nowMs - st.lastChange > timeout) {
        st.shown = f.decision;
        st.pending = null;
        st.pendingCount = 0;
        st.lastChange = nowMs;
      }
    } else {
      st.pending = f.decision;
      st.pendingCount = 1;
    }
    stable.set(key, st);
    return st.shown === f.decision ? f : { ...f, decision: st.shown };
  });
  for (const k of [...stable.keys()]) {
    if (!seen.has(k)) stable.delete(k);
  }
  return out;
}

/** Lọc lượt CHECKED_IN mới (cooldown 12s/người) để lịch sử không spam. */
export function filterFreshChecked(
  faces: KioskFaceBox[],
  seenAt: Map<string, number>,
  nowMs: number,
  cooldownMs = 12000
): KioskFaceBox[] {
  return faces
    .filter((f) => f.decision === "CHECKED_IN" && f.user_code)
    .filter((f) => nowMs - (seenAt.get(f.user_code || "") || 0) > cooldownMs);
}

export function boxColor(decision: string): string {
  switch (decision) {
    case "CHECKED_IN":
      return "#059669";
    case "VERIFYING":
      return "#d97706";
    case "SPOOF":
      return "#e11d48";
    default:
      return "#64748b";
  }
}

/** Nhãn hiển thị trên box. */
export function boxLabel(b: {
  decision?: string;
  fullName?: string | null;
  full_name?: string | null;
  userCode?: string | null;
  user_code?: string | null;
}): string {
  const dec = b.decision || "UNKNOWN";
  const name = b.fullName || b.full_name || b.userCode || b.user_code || "";
  switch (dec) {
    case "CHECKED_IN":
      return `✓ ${name}`;
    case "VERIFYING":
      return name || "Đang xác nhận...";
    case "SPOOF":
      return "Giả mạo!";
    default:
      return "Đang quét...";
  }
}
