"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Lock, User, AlertCircle, ArrowRight, Loader2 } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const { login, user, isAuthenticated, isLoading: isAuthLoading } = useAuth();

  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // If already logged in, redirect to appropriate portal
  useEffect(() => {
    if (!isAuthLoading && isAuthenticated && user) {
      if (user.role === "STUDENT") router.replace("/student/schedule");
      else if (user.role === "TEACHER") router.replace("/teacher/classes");
      else if (user.role === "ADMIN") router.replace("/admin/users");
    }
  }, [isAuthLoading, isAuthenticated, user, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!identifier.trim() || !password) {
      setErrorMsg("Vui lòng nhập đầy đủ mã người dùng/email và mật khẩu.");
      return;
    }

    setErrorMsg(null);
    setIsSubmitting(true);

    try {
      const loggedUser = await login({
        user_code_or_email: identifier.trim(),
        password,
      });

      if (loggedUser.role === "STUDENT") {
        router.push("/student/schedule");
      } else if (loggedUser.role === "TEACHER") {
        router.push("/teacher/classes");
      } else if (loggedUser.role === "ADMIN") {
        router.push("/admin/users");
      } else {
        router.push("/student/schedule");
      }
    } catch (err: any) {
      setErrorMsg(err.message || "Tài khoản hoặc mật khẩu không chính xác.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const fillQuickAccount = (acc: string, pass: string) => {
    setIdentifier(acc);
    setPassword(pass);
    setErrorMsg(null);
  };

  return (
    <div className="min-h-screen w-full flex flex-col justify-center items-center p-4 bg-slate-50 text-slate-900 selection:bg-slate-200">
      <div className="w-full max-w-sm">
        {/* Brand Header */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-10 h-10 rounded-lg bg-slate-900 text-white font-bold text-sm tracking-tight mb-3">
            SC
          </div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900">
            Hệ thống Quản lý Học vụ & Điểm danh
          </h1>
          <p className="mt-1 text-xs text-slate-500">
            Đăng nhập để truy cập Cổng Sinh viên, Giảng viên hoặc Quản trị
          </p>
        </div>

        {/* Login Card */}
        <div className="bg-white border border-slate-200 rounded-lg p-6 shadow-xs">
          {errorMsg && (
            <div className="mb-4 flex items-start gap-2.5 p-3 rounded-md bg-rose-50 border border-rose-200 text-rose-700 text-xs">
              <AlertCircle size={16} className="shrink-0 mt-0.5" />
              <div className="leading-snug">{errorMsg}</div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label
                htmlFor="identifier"
                className="block text-xs font-medium text-slate-700 mb-1.5"
              >
                Mã sinh viên / Mã giảng viên / Email
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <User size={15} />
                </div>
                <input
                  id="identifier"
                  type="text"
                  autoComplete="username"
                  required
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  placeholder="Ví dụ: SV2026001, GV01, ADMIN01"
                  className="w-full pl-9 pr-3 py-2 text-sm bg-white border border-slate-300 rounded-md focus:outline-none focus:ring-1 focus:ring-slate-900 focus:border-slate-900 font-mono"
                />
              </div>
            </div>

            <div>
              <label
                htmlFor="password"
                className="block text-xs font-medium text-slate-700 mb-1.5"
              >
                Mật khẩu
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <Lock size={15} />
                </div>
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full pl-9 pr-3 py-2 text-sm bg-white border border-slate-300 rounded-md focus:outline-none focus:ring-1 focus:ring-slate-900 focus:border-slate-900"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full mt-2 flex items-center justify-center gap-2 py-2.5 px-4 rounded-md text-xs font-medium text-white bg-slate-900 hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isSubmitting ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  <span>Đang đăng nhập...</span>
                </>
              ) : (
                <>
                  <span>Đăng nhập hệ thống</span>
                  <ArrowRight size={14} />
                </>
              )}
            </button>
          </form>

          {/* Quick Fill Test Accounts */}
          <div className="mt-6 pt-5 border-t border-slate-100">
            <p className="text-[11px] font-medium text-slate-400 uppercase tracking-wider mb-2">
              Tài khoản mẫu thử nghiệm
            </p>
            <div className="grid grid-cols-3 gap-1.5 text-xs">
              <button
                type="button"
                onClick={() => fillQuickAccount("SV2026001", "123456")}
                className="px-2 py-1.5 rounded border border-slate-200 bg-slate-50 hover:bg-slate-100 text-slate-700 text-left transition-colors"
              >
                <div className="font-medium text-[11px]">Sinh viên</div>
                <div className="font-mono text-[10px] text-slate-500 tabular-nums">SV2026001</div>
              </button>

              <button
                type="button"
                onClick={() => fillQuickAccount("GV01", "123456")}
                className="px-2 py-1.5 rounded border border-slate-200 bg-slate-50 hover:bg-slate-100 text-slate-700 text-left transition-colors"
              >
                <div className="font-medium text-[11px]">Giảng viên</div>
                <div className="font-mono text-[10px] text-slate-500 tabular-nums">GV01</div>
              </button>

              <button
                type="button"
                onClick={() => fillQuickAccount("ADMIN01", "123456")}
                className="px-2 py-1.5 rounded border border-slate-200 bg-slate-50 hover:bg-slate-100 text-slate-700 text-left transition-colors"
              >
                <div className="font-medium text-[11px]">Admin</div>
                <div className="font-mono text-[10px] text-slate-500 tabular-nums">ADMIN01</div>
              </button>
            </div>
            <p className="text-[10px] text-slate-400 mt-2 text-center">
              Mật khẩu mặc định: <span className="font-mono text-slate-600">123456</span>
            </p>
          </div>
        </div>

        {/* Footer info */}
        <div className="mt-6 text-center text-xs text-slate-400">
          Hệ thống Quản lý Lớp học Thông minh &copy; 2026
        </div>
      </div>
    </div>
  );
}
