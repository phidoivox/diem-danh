"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

export default function Home() {
  const router = useRouter();
  const { user, role, isAuthenticated, isLoading } = useAuth();

  useEffect(() => {
    if (!isLoading) {
      if (!isAuthenticated || !role) {
        router.replace("/login");
      } else if (role === "STUDENT") {
        router.replace("/student/schedule");
      } else if (role === "TEACHER") {
        router.replace("/teacher/classes");
      } else if (role === "ADMIN") {
        router.replace("/admin/users");
      } else {
        router.replace("/login");
      }
    }
  }, [isLoading, isAuthenticated, role, router]);

  return (
    <div className="h-full flex-1 flex flex-col items-center justify-center p-8 bg-slate-50 select-none">
      <div className="flex items-center gap-3 text-slate-500 text-sm">
        <span className="w-4 h-4 rounded-full border-2 border-slate-300 border-t-slate-800 animate-spin" />
        <span>Đang chuyển hướng đến phân hệ...</span>
      </div>
    </div>
  );
}
