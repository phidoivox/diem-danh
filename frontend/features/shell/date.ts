/**
 * Một cổng duy nhất cho định dạng ngày giờ (thay ~10 bản copy `padStart` /
 * `toLocaleString` rải rác các page). Dùng Intl API có sẵn của browser nên
 * không cần thêm `date-fns`/`dayjs` + tz-data vào bundle.
 *
 * Quy ước: server lưu wall-clock VN; hiển thị luôn ở Asia/Ho_Chi_Minh (UTC+7,
 * không DST). KHÔNG dùng `new Date().toISOString().split("T")[0]` để lấy ngày
 * VN vì toISOString trả ngày UTC (lệch 1 ngày sau 17h).
 */
export const VN_TIME_ZONE = "Asia/Ho_Chi_Minh";

function toDate(input: string | number | Date): Date {
  return input instanceof Date ? input : new Date(input);
}

export function formatTime(input: string | number | Date): string {
  return new Intl.DateTimeFormat("vi-VN", {
    timeZone: VN_TIME_ZONE,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(toDate(input));
}

export function formatDate(input: string | number | Date): string {
  return new Intl.DateTimeFormat("vi-VN", {
    timeZone: VN_TIME_ZONE,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(toDate(input));
}

export function formatDateTime(input: string | number | Date): string {
  return new Intl.DateTimeFormat("vi-VN", {
    timeZone: VN_TIME_ZONE,
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour12: false,
  }).format(toDate(input));
}

/** Thứ + ngày VN: "Thứ 2, 01/09/2026" (dùng Intl weekday, đúng TZ). */
export function formatWeekdayDate(input: string | number | Date): string {
  const d = toDate(input);
  const weekday = new Intl.DateTimeFormat("vi-VN", {
    timeZone: VN_TIME_ZONE,
    weekday: "long",
  }).format(d);
  const capped = weekday.charAt(0).toUpperCase() + weekday.slice(1);
  return `${capped}, ${formatDate(d)}`;
}

/** Ngày VN hiện tại dạng YYYY-MM-DD (cho input[type=date], query). */
export function todayVN(): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: VN_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
  return parts; // en-CA cho YYYY-MM-DD
}

/** Giờ local dạng YYYY-MM-DDTHH:mm:ss (không Z) để gửi backend wall-clock. */
export function localDateTimeString(d: Date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  );
}
