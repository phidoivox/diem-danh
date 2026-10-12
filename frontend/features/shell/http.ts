export const API = process.env.NEXT_PUBLIC_API || "http://localhost:8000";

export const TOKEN_STORAGE_KEY = "detect_ai_token";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/**
 * Chuẩn hoá URL file do backend trả về.
 *
 * Tất cả ảnh lưu local, đọc qua API có auth:
 * - `/api/v1/files/*`: avatar + file riêng tư (minh chứng/snapshot) — CHỈ dùng để
 *   fetch có Authorization (fetchAuthedFileUrl/openAuthedFileUrl), KHÔNG gắn
 *   trực tiếp vào <img src>/<a href> (sẽ 401).
 */
export function mediaUrl(url?: string | null): string {
  if (!url) return "";
  if (/^(https?:)?\/\//i.test(url) || url.startsWith("data:") || url.startsWith("blob:")) {
    return url;
  }
  return `${API}${url.startsWith("/") ? "" : "/"}${url}`;
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export function removeToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_STORAGE_KEY);
}

export type UserRole = "ADMIN" | "TEACHER" | "STUDENT";

/** Một nơi duy nhất ánh xạ role -> portal mặc định (trước lặp ở login/page,
// role-guard, app/page). */
export function getDefaultPortalPath(role?: string | null): string {
  if (role === "STUDENT") return "/student/schedule";
  if (role === "TEACHER") return "/teacher/classes";
  if (role === "ADMIN") return "/admin/users";
  return "/login";
}

/** Dựng query string, bỏ qua undefined/null/"" và giá trị "ALL". */
export function buildQuery(params: Record<string, string | number | undefined | null>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "" || v === "ALL") continue;
    sp.append(k, String(v));
  }
  const qs = sp.toString();
  return qs ? `?${qs}` : "";
}

/** Tải file blob (Excel/báo cáo): một helper thay 2 bản copy download. */
export async function downloadFile(url: string, fallbackName: string): Promise<void> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(url.startsWith("http") ? url : `${API}${url}`, { headers });
  if (!res.ok) {
    let errMsg = "Không thể tải file";
    try {
      const errJson = await res.json();
      errMsg = errJson.detail || errMsg;
    } catch {
      // ignore
    }
    throw new Error(errMsg);
  }
  const disposition = res.headers.get("Content-Disposition");
  let downloadName = fallbackName;
  if (disposition) {
    const match = disposition.match(/filename="?([^"]+)"?/);
    if (match?.[1]) downloadName = match[1];
  }
  const blob = await res.blob();
  const objectUrl = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = downloadName;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { window.URL.revokeObjectURL(objectUrl); document.body.removeChild(a); }, 1000);
}

/** true khi URL là file qua API auth (avatar/minh chứng/snapshot) — bắt buộc đọc qua
 * fetch có Authorization, KHÔNG gắn trực tiếp vào <img src>/<a href>. */
export function isPrivateFileUrl(url?: string | null): boolean {
  return !!url && (url.startsWith("/api/v1/files/") || url.includes("/api/v1/files/"));
}

/** Fetch file riêng tư (/api/v1/files/*) có kèm token -> blob object URL.
 * <img>/<a> không gửi được Authorization header nên phải fetch tay.
 * Caller tự revoke (URL.revokeObjectURL) khi đóng modal/unmount. */
export async function fetchAuthedFileUrl(path: string): Promise<string> {
  const token = getToken();
  const url = path.startsWith("http") ? path : `${API}${path.startsWith("/") ? "" : "/"}${path}`;
  const res = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    let detail = `HTTP error ${res.status}`;
    try {
      const j = await res.json();
      detail = j.detail || detail;
    } catch {
      // giữ detail mặc định
    }
    throw new Error(detail);
  }
  return window.URL.createObjectURL(await res.blob());
}

/** Mở file riêng tư trong tab mới (fetch blob có auth rồi window.open).
 * Dùng cho link "Xem tài liệu": <a href> trần không kèm token nên sẽ 401. */
export async function openAuthedFileUrl(path: string): Promise<void> {
  const objectUrl = await fetchAuthedFileUrl(path);
  window.open(objectUrl, "_blank", "noopener");
  window.setTimeout(() => window.URL.revokeObjectURL(objectUrl), 60_000);
}

export interface StudentProfile {
  id: number;
  user_id: number;
  total_point: number;
  is_officer?: boolean;
  class_name: string;
  major: string;
}

export interface TeacherProfile {
  id: number;
  user_id: number;
  department: string;
  academic_title: string;
  office_room: string;
}

export interface User {
  id: number;
  user_code: string;
  full_name: string;
  email: string;
  role: UserRole;
  avatar_url?: string | null;
  student_profile?: StudentProfile | null;
  teacher_profile?: TeacherProfile | null;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  role: UserRole;
  user: User;
}

export async function authFetch<T = unknown>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const url = endpoint.startsWith("http")
    ? endpoint
    : `${API}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;

  const headers: Record<string, string> = {
    ...((options.headers as Record<string, string>) || {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  if (options.body && !(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = "";
    try {
      const errJson = await response.json();
      if (Array.isArray(errJson.detail))
        errorDetail = errJson.detail.map((e: { msg?: string; message?: string }) => e?.msg || e?.message || JSON.stringify(e)).join(", ");
      else errorDetail = errJson.detail || JSON.stringify(errJson);
    } catch {
      errorDetail = await response.text();
    }
    if (response.status === 401) {
      removeToken();
      // Tập trung redirect login tại 1 chỗ thay vì mỗi caller tự xử lý.
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
        window.location.href = new URL("/login", window.location.origin).toString();
      }
    }
    throw new ApiError(errorDetail || `HTTP error ${response.status}`, response.status);
  }

  return response.json();
}

export async function login(
  user_code_or_email: string,
  password: string
): Promise<LoginResponse> {
  const res = await fetch(`${API}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_code_or_email, password }),
  });

  if (!res.ok) {
    let errorDetail = "";
    try {
      const errJson = await res.json();
      if (Array.isArray(errJson.detail))
        errorDetail = errJson.detail.map((e: { msg?: string; message?: string }) => e?.msg || e?.message || JSON.stringify(e)).join(", ");
      else errorDetail = errJson.detail || JSON.stringify(errJson);
    } catch {
      errorDetail = await res.text();
    }
    throw new Error(errorDetail || "Đăng nhập thất bại");
  }

  const data: LoginResponse = await res.json();
  setToken(data.access_token);
  return data;
}

export async function getMe(): Promise<User> {
  return authFetch<User>("/api/v1/auth/me");
}

export function logout(): void {
  removeToken();
}

// Student Portal API definitions
export interface StudentSchedule {
  id: number;
  class_id: number;
  class_code: string;
  course_name: string;
  teacher_name: string;
  room_name: string;
  study_date: string;
  start_time: string;
  end_time: string;
  session_order: number;
}

export interface StudentAttendance {
  attendance_id: number;
  schedule_id: number;
  class_code: string;
  course_name: string;
  study_date: string;
  start_time: string;
  end_time: string;
  check_in_time: string | null;
  check_out_time: string | null;
  check_in_snapshot_url?: string | null;
  check_out_snapshot_url?: string | null;
  has_uniform: boolean;
  status: "PRESENT" | "LATE" | "HALF_ABSENT" | "ABSENT" | "EXCUSED" | string;
  note: string | null;
  snapshot_url: string | null;
  /** Tổng biến động điểm rèn luyện của buổi này. null = chưa chấm điểm. */
  point_delta?: number | null;
}

export interface ConductLedgerEntry {
  id: number;
  point_delta: number;
  reason_code: string;
  description: string | null;
  created_at: string;
  schedule_id: number | null;
}

export interface StudentConductLedger {
  total_point: number;
  conduct_rank?: string;
  is_officer?: boolean;
  items: ConductLedgerEntry[];
}

export interface StudentLeaveRequest {
  id: number;
  schedule_id: number;
  student_id: number;
  reason: string;
  proof_image: string | null;
  status: "PENDING" | "APPROVED" | "REJECTED" | string;
  teacher_feedback: string | null;
  reviewed_by: number | null;
  reviewed_at: string | null;
  created_at: string;
  course_name?: string | null;
  class_code?: string | null;
  study_date?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  room_name?: string | null;
  student_code?: string | null;
  student_name?: string | null;
  student_email?: string | null;
  avatar_url?: string | null;
  class_name?: string | null;
}

export async function getStudentSchedule(): Promise<StudentSchedule[]> {
  return authFetch<StudentSchedule[]>("/api/v1/student/schedule");
}

export async function getStudentAttendance(): Promise<StudentAttendance[]> {
  return authFetch<StudentAttendance[]>("/api/v1/student/attendance");
}

export async function getStudentConductLedger(): Promise<StudentConductLedger> {
  return authFetch<StudentConductLedger>("/api/v1/student/conduct-ledger");
}

export async function getStudentLeaveRequests(): Promise<StudentLeaveRequest[]> {
  return authFetch<StudentLeaveRequest[]>("/api/v1/student/leave-requests");
}

export async function submitLeaveRequest(formData: FormData): Promise<StudentLeaveRequest> {
  return authFetch<StudentLeaveRequest>("/api/v1/student/leave-requests", {
    method: "POST",
    body: formData,
  });
}

// =====================================================================
// TEACHER PORTAL API DEFINITIONS
// =====================================================================
export interface ScheduleBrief {
  id: number;
  study_date: string;
  start_time: string;
  end_time: string;
  room_name: string;
  session_order: number;
}

export interface TeacherClass {
  id: number;
  class_code: string;
  course_name: string;
  teacher_id: number;
  semester: string;
  total_sessions: number;
  student_count: number;
  today_schedule?: ScheduleBrief | null;
}

export interface LiveAttendanceStudent {
  attendance_id: number | null;
  student_id: number;
  student_code: string;
  full_name: string;
  class_name: string;
  check_in_time: string | null;
  check_out_time: string | null;
  check_in_snapshot_url?: string | null;
  check_out_snapshot_url?: string | null;
  has_uniform: boolean;
  status: "PRESENT" | "LATE" | "HALF_ABSENT" | "ABSENT" | "EXCUSED" | string;
  is_manual_override: boolean;
  /** Nguồn điểm danh: face | manual | teacher | none (backend >= face-kiosk). */
  source?: string;
}

export interface LiveAttendanceResponse {
  class_id: number;
  class_code: string;
  course_name: string;
  schedule_id: number | null;
  study_date: string | null;
  start_time: string | null;
  end_time: string | null;
  room_name: string | null;
  total_students: number;
  checked_in_count: number;
  absent_count: number;
  uniform_violation_count: number;
  students: LiveAttendanceStudent[];
  // Extended helper fields
  class_info?: {
    id: number;
    class_code: string;
    course_name: string;
  };
  schedule_info?: {
    schedule_id: number | null;
    study_date: string | null;
    start_time: string | null;
    end_time: string | null;
    room_name: string | null;
  };
  stats?: {
    total_students: number;
    checked_in_count: number;
    absent_count: number;
    uniform_violation_count: number;
  };
}

export interface TeacherLeaveRequest {
  id: number;
  schedule_id: number;
  student_id: number;
  reason: string;
  proof_image: string | null;
  status: "PENDING" | "APPROVED" | "REJECTED" | string;
  teacher_feedback: string | null;
  reviewed_by: number | null;
  reviewed_at: string | null;
  created_at: string;
  course_name?: string | null;
  class_code?: string | null;
  study_date?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  room_name?: string | null;
  student_code?: string | null;
  student_name?: string | null;
  student_email?: string | null;
  avatar_url?: string | null;
  class_name?: string | null;
}

export interface TeacherLeaveRequestPage {
  items: TeacherLeaveRequest[];
  total: number;
  page: number;
  size: number;
}

export interface ExamBanStudent {
  student_id: number;
  student_code: string;
  full_name: string;
  class_name?: string;
  course_name?: string;
  class_code?: string;
  absent_count: number;
  half_absent_count: number;
  late_count?: number;
  present_count?: number;
  excused_count?: number;
  converted_absent?: number;
  cumulative_rate?: number;
  rate_cumulative?: number;
  semester_rate?: number;
  rate_semester?: number;
  is_warning: boolean;
  is_banned: boolean;
  status_label: "BỊ CẤM THI" | "CẢNH BÁO" | "ĐỦ ĐIỀU KIỆN" | string;
}

export interface ExamBanReport {
  class_id?: number;
  class_code: string;
  course_name: string;
  semester?: string;
  teacher_name?: string;
  total_sessions: number;
  elapsed_sessions: number;
  /** Ngưỡng cảnh báo/cấm thi (%) backend đang áp dụng (mặc định 15/20). */
  warning_percent?: number;
  ban_percent?: number;
  students: ExamBanStudent[];
}

export async function getTeacherClasses(): Promise<TeacherClass[]> {
  return authFetch<TeacherClass[]>("/api/v1/teacher/classes");
}

export async function getTeacherLiveAttendance(classId: number): Promise<LiveAttendanceResponse> {
  const data = await authFetch<LiveAttendanceResponse>(`/api/v1/teacher/classes/${classId}/live-attendance`);
  data.class_info = {
    id: data.class_id,
    class_code: data.class_code,
    course_name: data.course_name,
  };
  data.schedule_info = {
    schedule_id: data.schedule_id,
    study_date: data.study_date,
    start_time: data.start_time,
    end_time: data.end_time,
    room_name: data.room_name,
  };
  data.stats = {
    total_students: data.total_students,
    checked_in_count: data.checked_in_count,
    absent_count: data.absent_count,
    uniform_violation_count: data.uniform_violation_count,
  };
  return data;
}

export async function manualOverrideAttendance(
  attendanceId: number,
  data: { status: string; note?: string; schedule_id?: number; student_id?: number; has_uniform?: boolean }
): Promise<unknown> {
  return authFetch<unknown>(`/api/v1/teacher/attendance/${attendanceId}/manual-override`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

// =====================================================================
// Lịch sử điểm danh của 1 sinh viên trong 1 lớp học phần (từng môn)
// =====================================================================
export interface StudentHistoryItem {
  schedule_id: number;
  study_date: string;
  start_time: string;
  end_time: string;
  session_order: number;
  room_name: string;
  attendance_id: number | null;
  check_in_time: string | null;
  check_out_time: string | null;
  check_in_snapshot_url?: string | null;
  check_out_snapshot_url?: string | null;
  has_uniform: boolean;
  status: string;
  is_manual_override: boolean;
  source?: string;
  note?: string | null;
  /** Tổng biến động điểm rèn luyện của buổi này. null = chưa chấm điểm. */
  point_delta?: number | null;
}

export interface StudentHistoryResponse {
  class_id: number;
  class_code: string;
  course_name: string;
  student_id: number;
  student_code: string;
  full_name: string;
  summary: {
    total_sessions: number;
    present: number;
    late: number;
    half_absent: number;
    absent: number;
    excused: number;
    total_deducted?: number;
  };
  items: StudentHistoryItem[];
}

export async function getStudentAttendanceHistory(
  classId: number,
  studentId: number
): Promise<StudentHistoryResponse> {
  return authFetch<StudentHistoryResponse>(
    `/api/v1/teacher/classes/${classId}/students/${studentId}/attendance-history`
  );
}

export interface HomeroomClass {
  id: number;
  class_code: string;
  faculty?: string;
}

export interface HomeroomStudent {
  id: number;
  user_code: string;
  full_name: string;
  total_point: number;
  is_officer: boolean;
}

export async function getTeacherHomeroomClasses(): Promise<HomeroomClass[]> {
  return authFetch<HomeroomClass[]>("/api/v1/teacher/homeroom-classes");
}

export async function getTeacherHomeroomStudents(adminClassId: number): Promise<HomeroomStudent[]> {
  return authFetch<HomeroomStudent[]>(
    `/api/v1/teacher/homeroom-classes/${adminClassId}/students`
  );
}

export async function setTeacherHomeroomOfficer(
  adminClassId: number,
  studentId: number,
  isOfficer: boolean
): Promise<{ ok: boolean; student_id: number; is_officer: boolean }> {
  return authFetch<{ ok: boolean; student_id: number; is_officer: boolean }>(
    `/api/v1/teacher/homeroom-classes/${adminClassId}/students/${studentId}/officer`,
    { method: "PUT", body: JSON.stringify({ is_officer: isOfficer }) }
  );
}

export async function getAdminStudentAttendanceHistory(
  classId: number,
  studentId: number
): Promise<StudentHistoryResponse> {
  return authFetch<StudentHistoryResponse>(
    `/api/v1/admin/reports/classes/${classId}/students/${studentId}/attendance-history`
  );
}

// =====================================================================
// Face Kiosk (điểm danh khuôn mặt tại cửa lớp)
// =====================================================================
export interface KioskFaceBox {
  track_id: number;
  bbox: number[];
  student_id: number | null;
  user_code: string | null;
  full_name: string | null;
  score: number;
  liveness: number;
  decision: string;
}

export interface KioskCheckinResponse {
  schedule_id: number;
  checked_in: number[];
  checked_out?: number[];
  already_done?: number[];
  faces: KioskFaceBox[];
  gallery_size: number;
  next_interval_ms?: number;
  next_width?: number;
}

export function kioskWsUrl(scheduleId: number): string {
  // Token KHÔNG đi qua query (lộ logs/proxy/history). Auth qua subprotocol
  // `jwt-<token>` ở kioskWsProtocols(), backend ưu tiên đọc subprotocol.
  const base = API.replace(/^http:/, "ws:").replace(/^https:/, "wss:");
  return `${base}/api/v1/kiosk/ws?schedule_id=${scheduleId}`;
}
export function kioskWsProtocols(): string[] {
  const token = getToken() || "";
  return token ? [`jwt-${token}`] : [];
}

export interface KioskGalleryStatus {
  class_id: number;
  total: number;
  enrolled: number;
  gallery_vectors: number;
  students: {
    student_id: number;
    user_code: string;
    full_name: string;
    embeddings: number;
    enrolled: boolean;
  }[];
}

export async function kioskCheckin(scheduleId: number, frameBlob: Blob): Promise<KioskCheckinResponse> {
  const form = new FormData();
  form.append("schedule_id", String(scheduleId));
  form.append("frame", frameBlob, "frame.jpg");
  return authFetch<KioskCheckinResponse>("/api/v1/kiosk/checkin", {
    method: "POST",
    body: form,
  });
}

export async function getKioskGalleryStatus(classId: number): Promise<KioskGalleryStatus> {
  return authFetch<KioskGalleryStatus>(`/api/v1/kiosk/gallery-status?class_id=${classId}`);
}

export async function kioskResetSession(scheduleId: number): Promise<{ ok: boolean }> {
  const form = new FormData();
  form.append("schedule_id", String(scheduleId));
  return authFetch<{ ok: boolean }>("/api/v1/kiosk/reset-session", { method: "POST", body: form });
}

export async function getTeacherLeaveRequests(params?: {
  status?: string;
  class_id?: number;
  page?: number;
  size?: number;
}): Promise<TeacherLeaveRequestPage> {
  const qs = buildQuery({
    status: params?.status,
    class_id: params?.class_id,
    page: params?.page,
    size: params?.size || 100,
  });
  return authFetch<TeacherLeaveRequestPage>(`/api/v1/teacher/leave-requests${qs}`);
}

export async function reviewLeaveRequest(
  id: number,
  data: { status: "APPROVED" | "REJECTED"; feedback?: string }
): Promise<TeacherLeaveRequest> {
  return authFetch<TeacherLeaveRequest>(`/api/v1/teacher/leave-requests/${id}/review`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getTeacherExamBanReport(classId: number): Promise<ExamBanReport> {
  const res = await authFetch<ExamBanReport>(`/api/v1/teacher/classes/${classId}/exam-ban-report`);
  if (res && Array.isArray(res.students)) {
    res.students = res.students.map((st) => ({
      ...st,
      cumulative_rate: st.cumulative_rate ?? st.rate_cumulative ?? 0,
      semester_rate: st.semester_rate ?? st.rate_semester ?? 0,
    }));
  }
  return res;
}

export async function getAdminExamBanReport(classId: number): Promise<ExamBanReport> {
  const res = await authFetch<ExamBanReport>(`/api/v1/admin/reports/classes/${classId}/exam-ban-report`);
  if (res && Array.isArray(res.students)) {
    res.students = res.students.map((st) => ({
      ...st,
      cumulative_rate: st.cumulative_rate ?? st.rate_cumulative ?? 0,
      semester_rate: st.semester_rate ?? st.rate_semester ?? 0,
    }));
  }
  return res;
}

export async function downloadTeacherExamBanExcel(classId: number, filename?: string): Promise<void> {
  await downloadFile(
    `/api/v1/teacher/classes/${classId}/export-exam-ban-excel`,
    filename || `cam_thi_lop_${classId}.xlsx`
  );
}

// =====================================================================
// Bảng điểm rèn luyện theo lớp (global + delta lớp + rank)
// =====================================================================
export interface ClassConductStudent {
  student_id: number;
  student_code: string;
  full_name: string;
  class_name?: string;
  total_point: number;
  is_officer?: boolean;
  conduct_rank: string;
  class_delta: number;
  class_entries: number;
}

export interface ClassConductReport {
  class_id: number;
  class_code: string;
  course_name: string;
  evaluated_sessions: number;
  total_sessions: number;
  summary: { total: number; by_rank: Record<string, number> };
  students: ClassConductStudent[];
}

export async function getTeacherClassConduct(classId: number, month?: string): Promise<ClassConductReport> {
  const qs = buildQuery({ month });
  return authFetch<ClassConductReport>(`/api/v1/teacher/classes/${classId}/conduct-points${qs}`);
}

export async function getAdminClassConduct(classId: number, month?: string): Promise<ClassConductReport> {
  const qs = buildQuery({ month });
  return authFetch<ClassConductReport>(`/api/v1/admin/reports/classes/${classId}/conduct-points${qs}`);
}

export async function downloadTeacherConductExcel(classId: number, month?: string, filename?: string): Promise<void> {
  const qs = buildQuery({ month });
  await downloadFile(
    `/api/v1/teacher/classes/${classId}/export-conduct-excel${qs}`,
    filename ?? `diem_ren_luyen_${classId}.xlsx`,
  );
}

export async function downloadAdminConductExcel(classId: number, month?: string, filename?: string): Promise<void> {
  const qs = buildQuery({ month });
  await downloadFile(
    `/api/v1/admin/reports/classes/${classId}/export-conduct-excel${qs}`,
    filename ?? `diem_ren_luyen_${classId}.xlsx`,
  );
}

// =====================================================================
// ADMIN PORTAL API DEFINITIONS
// =====================================================================
export interface AdminStudentProfile {
  id: number;
  user_id: number;
  total_point: number;
  is_officer?: boolean;
  admin_class_id?: number | null;
  class_name: string;
  major: string;
}

export interface AdminTeacherProfile {
  id: number;
  user_id: number;
  department: string;
  academic_title: string;
  office_room: string;
}

export interface AdminUser {
  id: number;
  user_code: string;
  full_name: string;
  email: string;
  role: string;
  role_name?: string;
  is_active: boolean;
  avatar_url?: string | null;
  created_at?: string | null;
  student_profile?: AdminStudentProfile | null;
  teacher_profile?: AdminTeacherProfile | null;
}

export interface AdminUserPage {
  items: AdminUser[];
  total: number;
  page: number;
  size: number;
}

export interface AdminCourse {
  id: number;
  course_code: string;
  course_name: string;
  credits: number;
  default_sessions: number;
  description?: string | null;
  created_at?: string | null;
}

export interface AdminCoursePage {
  items: AdminCourse[];
  total: number;
  page: number;
  size: number;
}

export interface AdminAdministrativeClass {
  id: number;
  class_code: string;
  academic_year: string;
  faculty: string;
  homeroom_teacher_id?: number | null;
  homeroom_teacher_name?: string;
  student_count: number;
  created_at?: string | null;
}

export interface AdminAdministrativeClassPage {
  items: AdminAdministrativeClass[];
  total: number;
  page: number;
  size: number;
}

export interface AdminClass {
  id: number;
  class_code: string;
  course_id?: number;
  course_code?: string;
  course_name: string;
  teacher_id: number;
  teacher_name: string;
  semester: string;
  total_sessions: number;
  student_count: number;
}

export interface AdminClassPage {
  items: AdminClass[];
  total: number;
  page: number;
  size: number;
}

export interface StudentInClass {
  id: number;
  user_code: string;
  full_name: string;
  email: string;
  class_name?: string;
  major?: string;
  total_point?: number;
  is_officer?: boolean;
}

export interface AdminSchedule {
  id: number;
  class_id: number;
  class_code?: string | null;
  course_name?: string | null;
  room_name: string;
  study_date: string;
  start_time: string;
  end_time: string;
  session_order: number;
}

export type SystemSettingsMap = { [key: string]: string };

export interface SystemSettingItem {
  id: number;
  key: string;
  value: string;
  description?: string | null;
}

export interface SystemSettingsResponse {
  settings: SystemSettingsMap;
  items: SystemSettingItem[];
  has_smtp_password?: boolean;
}

export interface EvaluationResult {
  target_date: string;
  schedules_evaluated: number;
  students_evaluated: number;
  total_records: number;
}

export async function getAdminUsers(params?: {
  page?: number;
  size?: number;
  role?: string;
  q?: string;
}): Promise<AdminUserPage> {
  const qs = buildQuery({ page: params?.page, size: params?.size, role: params?.role, q: params?.q });
  const res = await authFetch<AdminUserPage>(`/api/v1/admin/users${qs}`);
  if (res && Array.isArray(res.items)) {
    res.items = res.items.map((u) => ({
      ...u,
      role_name: u.role_name || u.role,
    }));
  }
  return res;
}

export async function createAdminUser(data: Record<string, unknown>): Promise<AdminUser> {
  const res = await authFetch<AdminUser>("/api/v1/admin/users", {
    method: "POST",
    body: JSON.stringify(data),
  });
  if (res) {
    res.role_name = res.role_name || res.role;
  }
  return res;
}

export async function updateAdminUser(id: number, data: Record<string, unknown>): Promise<AdminUser> {
  const res = await authFetch<AdminUser>(`/api/v1/admin/users/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
  if (res) {
    res.role_name = res.role_name || res.role;
  }
  return res;
}

export async function deleteAdminUser(id: number): Promise<{ ok: boolean; message: string }> {
  return authFetch<{ ok: boolean; message: string }>(`/api/v1/admin/users/${id}`, {
    method: "DELETE",
  });
}

export async function uploadUserAvatar(
  id: number,
  file: File
): Promise<{ ok: boolean; user_id: number; avatar_url?: string | null; face_status?: string }> {
  const fd = new FormData();
  fd.append("photo", file);
  return authFetch<{ ok: boolean; user_id: number; avatar_url?: string | null; face_status?: string }>(
    `/api/v1/admin/users/${id}/avatar`,
    {
      method: "POST",
      body: fd,
    }
  );
}

export async function getStudentClassNames(): Promise<string[]> {
  return authFetch<string[]>("/api/v1/admin/users/class-names");
}

export interface StudentImportResult {
  created: number;
  skipped: number;
  errors: { row: number; user_code: string; message: string }[];
  default_password: string;
}

/** Nhập sinh viên hàng loạt từ file Excel (.xlsx). Mật khẩu mặc định 123456. */
export async function importStudentsExcel(file: File): Promise<StudentImportResult> {
  const fd = new FormData();
  fd.append("file", file);
  return authFetch<StudentImportResult>("/api/v1/admin/users/import-excel", {
    method: "POST",
    body: fd,
  });
}

/** Tải file mẫu nhập sinh viên. */
export async function downloadStudentImportTemplate(): Promise<void> {
  await downloadFile("/api/v1/admin/users/import-excel/template", "mau_nhap_sinh_vien.xlsx");
}

/** Danh sách lớp sinh hoạt (mã lớp + sĩ số) cho dropdown chọn lớp khi tạo/sửa SV. */
export async function getStudentAdministrativeClassOptions(): Promise<AdminAdministrativeClass[]> {
  const page = await authFetch<AdminAdministrativeClassPage>(
    "/api/v1/admin/academic/administrative-classes?size=500"
  );
  return page.items ?? [];
}

// =====================================================================
// Courses (Học phần / Môn học)
// =====================================================================
export async function getAdminCourses(params?: {
  page?: number;
  size?: number;
  q?: string;
}): Promise<AdminCoursePage> {
  const qs = buildQuery({ page: params?.page, size: params?.size, q: params?.q });
  return authFetch<AdminCoursePage>(`/api/v1/admin/academic/courses${qs}`);
}

export async function createAdminCourse(data: {
  course_code: string;
  course_name: string;
  credits?: number;
  default_sessions?: number;
  description?: string;
}): Promise<AdminCourse> {
  return authFetch<AdminCourse>("/api/v1/admin/academic/courses", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateAdminCourse(
  id: number,
  data: {
    course_code?: string;
    course_name?: string;
    credits?: number;
    default_sessions?: number;
    description?: string;
  }
): Promise<AdminCourse> {
  return authFetch<AdminCourse>(`/api/v1/admin/academic/courses/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteAdminCourse(id: number): Promise<{ ok: boolean; message: string }> {
  return authFetch<{ ok: boolean; message: string }>(`/api/v1/admin/academic/courses/${id}`, {
    method: "DELETE",
  });
}

// =====================================================================
// Administrative Classes (Lớp sinh hoạt / Lớp niên chế)
// =====================================================================
export async function getAdminAdministrativeClasses(params?: {
  page?: number;
  size?: number;
  q?: string;
}): Promise<AdminAdministrativeClassPage> {
  const qs = buildQuery({ page: params?.page, size: params?.size, q: params?.q });
  return authFetch<AdminAdministrativeClassPage>(`/api/v1/admin/academic/administrative-classes${qs}`);
}

export async function createAdminAdministrativeClass(data: {
  class_code: string;
  academic_year?: string;
  faculty?: string;
  homeroom_teacher_id?: number | null;
}): Promise<AdminAdministrativeClass> {
  return authFetch<AdminAdministrativeClass>("/api/v1/admin/academic/administrative-classes", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateAdminAdministrativeClass(
  id: number,
  data: {
    class_code?: string;
    academic_year?: string;
    faculty?: string;
    homeroom_teacher_id?: number | null;
  }
): Promise<AdminAdministrativeClass> {
  return authFetch<AdminAdministrativeClass>(`/api/v1/admin/academic/administrative-classes/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteAdminAdministrativeClass(id: number): Promise<{ ok: boolean; message: string }> {
  return authFetch<{ ok: boolean; message: string }>(`/api/v1/admin/academic/administrative-classes/${id}`, {
    method: "DELETE",
  });
}

export async function getAdminAdministrativeClassStudents(id: number): Promise<StudentInClass[]> {
  return authFetch<StudentInClass[]>(`/api/v1/admin/academic/administrative-classes/${id}/students`);
}

// =====================================================================
// Classes (Lớp học phần)
// =====================================================================
export async function getAdminClasses(params?: {
  page?: number;
  size?: number;
  q?: string;
}): Promise<AdminClassPage> {
  const qs = buildQuery({ page: params?.page, size: params?.size, q: params?.q });
  return authFetch<AdminClassPage>(`/api/v1/admin/academic/classes${qs}`);
}

export async function createAdminClass(data: Record<string, unknown>): Promise<AdminClass> {
  return authFetch<AdminClass>("/api/v1/admin/academic/classes", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateAdminClass(id: number, data: Record<string, unknown>): Promise<AdminClass> {
  return authFetch<AdminClass>(`/api/v1/admin/academic/classes/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteAdminClass(id: number): Promise<{ ok: boolean; message: string }> {
  return authFetch<{ ok: boolean; message: string }>(`/api/v1/admin/academic/classes/${id}`, {
    method: "DELETE",
  });
}

export async function getAdminClassStudents(classId: number): Promise<StudentInClass[]> {
  return authFetch<StudentInClass[]>(`/api/v1/admin/academic/classes/${classId}/students`);
}

export async function addStudentToClass(
  classId: number,
  studentId: number
): Promise<{ ok: boolean; class_id: number; student_id: number }> {
  return authFetch<{ ok: boolean; class_id: number; student_id: number }>(
    `/api/v1/admin/academic/classes/${classId}/students`,
    {
      method: "POST",
      body: JSON.stringify({ student_id: studentId }),
    }
  );
}

export async function removeStudentFromClass(
  classId: number,
  studentId: number
): Promise<{ ok: boolean; message: string }> {
  return authFetch<{ ok: boolean; message: string }>(
    `/api/v1/admin/academic/classes/${classId}/students/${studentId}`,
    {
      method: "DELETE",
    }
  );
}

export async function addStudentsToClassBulk(
  classId: number,
  studentIds: number[],
  classNames?: string[],
  adminClassIds?: number[]
): Promise<{ ok: boolean; enrolled: number[]; skipped: number[] }> {
  return authFetch<{ ok: boolean; enrolled: number[]; skipped: number[] }>(
    `/api/v1/admin/academic/classes/${classId}/students/bulk`,
    {
      method: "POST",
      body: JSON.stringify({
        student_ids: studentIds,
        class_names: classNames ?? [],
        admin_class_ids: adminClassIds ?? [],
      }),
    }
  );
}

export async function getAdminSchedules(params?: {
  class_id?: number;
  study_date?: string;
  room_name?: string;
}): Promise<AdminSchedule[]> {
  const qs = buildQuery({
    class_id: params?.class_id,
    study_date: params?.study_date,
    room_name: params?.room_name,
  });
  return authFetch<AdminSchedule[]>(`/api/v1/admin/academic/schedules${qs}`);
}

export async function createAdminSchedule(data: Record<string, unknown>): Promise<AdminSchedule> {
  return authFetch<AdminSchedule>("/api/v1/admin/academic/schedules", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export interface AdminScheduleBulkRequest {
  class_id: number;
  room_name: string;
  start_date: string;
  start_time: string;
  end_time: string;
  weekdays: number[];
  total_sessions: number;
  start_session_order?: number;
}

export interface AdminScheduleBulkResponse {
  created: AdminSchedule[];
  skipped: { study_date: string; reason: string }[];
}

export async function createAdminSchedulesBulk(data: AdminScheduleBulkRequest): Promise<AdminScheduleBulkResponse> {
  return authFetch<AdminScheduleBulkResponse>("/api/v1/admin/academic/schedules/bulk", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateAdminSchedule(id: number, data: Record<string, unknown>): Promise<AdminSchedule> {
  return authFetch<AdminSchedule>(`/api/v1/admin/academic/schedules/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteAdminSchedule(id: number): Promise<{ ok: boolean; message: string }> {
  return authFetch<{ ok: boolean; message: string }>(`/api/v1/admin/academic/schedules/${id}`, {
    method: "DELETE",
  });
}

export async function getAdminSettings(): Promise<SystemSettingsResponse> {
  return authFetch<SystemSettingsResponse>("/api/v1/admin/settings");
}

export async function updateAdminSettings(
  settings: Record<string, string>
): Promise<SystemSettingsResponse> {
  return authFetch<SystemSettingsResponse>("/api/v1/admin/settings", {
    method: "PUT",
    body: JSON.stringify(settings),
  });
}

export async function triggerNightlyEvaluation(targetDate?: string): Promise<EvaluationResult> {
  const qs = buildQuery({ target_date: targetDate });
  return authFetch<EvaluationResult>(`/api/v1/admin/evaluation/run-now${qs}`, {
    method: "POST",
  });
}

export async function downloadAllSchoolExamBanExcel(
  filename = "danh_sach_cam_thi_toan_truong.xlsx"
): Promise<void> {
  await downloadFile("/api/v1/admin/reports/export-exam-ban-all-excel", filename);
}

// Notifications: test mail + gửi bù cảnh báo/cấm thi + nhắc lịch.
export interface NotifyResult {
  sent: number;
  skipped: number;
  failed: number;
  disabled?: boolean;
  [k: string]: unknown;
}

export async function sendTestEmail(to: string): Promise<{ ok: boolean } & Record<string, unknown>> {
  return authFetch(`/api/v1/admin/reports/notifications/test`, {
    method: "POST",
    body: JSON.stringify({ to }),
  });
}

export async function sendAdminExamWarnings(
  classId: number,
  data?: { only?: string; dry_run?: boolean }
): Promise<NotifyResult> {
  return authFetch<NotifyResult>(`/api/v1/admin/reports/classes/${classId}/send-exam-warnings`, {
    method: "POST",
    body: JSON.stringify({ only: data?.only ?? "all", dry_run: data?.dry_run ?? false }),
  });
}

export async function sendTeacherExamWarnings(
  classId: number,
  data?: { only?: string; dry_run?: boolean }
): Promise<NotifyResult> {
  return authFetch<NotifyResult>(`/api/v1/teacher/classes/${classId}/send-exam-warnings`, {
    method: "POST",
    body: JSON.stringify({ only: data?.only ?? "all", dry_run: data?.dry_run ?? false }),
  });
}

export async function sendScheduleReminder(
  scheduleId: number,
  dryRun = false
): Promise<NotifyResult> {
  return authFetch<NotifyResult>(`/api/v1/admin/academic/schedules/${scheduleId}/send-reminder`, {
    method: "POST",
    body: JSON.stringify({ dry_run: dryRun }),
  });
}

