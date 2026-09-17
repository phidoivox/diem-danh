"use client";

import React from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import Attendance from "../attendance/page";

export default function DiemDanhKioskPage() {
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col">
      {/* Top Kiosk Bar */}
      <header className="h-12 border-b border-slate-800 bg-slate-950 px-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 transition-colors"
          >
            <ArrowLeft size={14} />
            Quay lại Hệ thống
          </Link>
          <span className="text-xs font-semibold text-slate-200 tracking-wide">
            Kiosk Điểm danh AI FaceID & Đồng phục
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-[11px] font-mono text-slate-400">KIOSK MODE</span>
        </div>
      </header>

      {/* Main Kiosk View */}
      <div className="flex-1 bg-white text-slate-900">
        <Attendance />
      </div>
    </div>
  );
}
