export const API = process.env.NEXT_PUBLIC_API || "http://localhost:8000";
export const WS = API.replace(/^http/, "ws") + "/ws/attendance/webcam";

export const TOKEN_STORAGE_KEY = "detect_ai_token";

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

export interface StudentProfile {
  id: number;
  user_id: number;
  total_point: number;
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

export async function authFetch<T = any>(
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
      errorDetail = errJson.detail || JSON.stringify(errJson);
    } catch {
      errorDetail = await response.text();
    }
    if (response.status === 401) {
      removeToken();
    }
    throw new Error(errorDetail || `HTTP error ${response.status}`);
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
      errorDetail = errJson.detail || JSON.stringify(errJson);
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

// Legacy & Utility API definitions
export type Att = { id: number; code: string; uniform: string; violations: string; snapshot: string; at: string };
export type Student = { id: number; code: string; name: string; class_name: string; photo?: string };
export type Page<T> = { items: T[]; total: number; page: number; size: number };

async function j<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, { cache: "no-store", ...init });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export const getAtt = (limit = 50, status = "", q = ""): Promise<Att[]> =>
  j(`${API}/api/attendance?limit=${limit}&status=${status}&q=${encodeURIComponent(q)}`);
export const getStudents = (page = 1, size = 50, q = ""): Promise<Page<Student>> =>
  j(`${API}/api/students?page=${page}&size=${size}&q=${encodeURIComponent(q)}`);
export const addStudent = (fd: FormData) =>
  j(`${API}/api/students`, { method: "POST", body: fd });
export const updateStudent = (id: number, fd: FormData) =>
  j(`${API}/api/students/${id}`, { method: "PUT", body: fd });
export const deleteStudent = (id: number) =>
  j(`${API}/api/students/${id}`, { method: "DELETE" });
export const studentPhoto = (name?: string) => (name ? `${API}/api/students/photo/${name}` : "");
export const toCsv = (rows: Att[]) =>
  "id,code,uniform,violations,at\n" +
  rows.map((r) => [r.id, r.code, r.uniform, `"${r.violations}"`, r.at].join(",")).join("\n");
