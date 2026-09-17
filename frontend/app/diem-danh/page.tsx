"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  School,
  Clock,
  MapPin,
  Volume2,
  VolumeX,
  History,
  ShieldCheck,
  ShieldAlert,
  CheckCircle2,
  XCircle,
  HelpCircle,
  UserCheck,
} from "lucide-react";
import { CameraFeed } from "@/components/kiosk/camera-feed";
import {
  AttendanceResultCard,
  playKioskAudioFeedback,
} from "@/components/kiosk/attendance-result-card";
import type { KioskRecordResponse } from "@/lib/api";

const PRESET_ROOMS = ["A1-301", "A1-302", "A101", "Lab 302", "B204", "B201", "C105"];

interface HistoryScanItem {
  id: string;
  type: "CHECK_IN" | "CHECK_OUT" | "ERROR";
  student_code: string;
  student_name: string;
  class_code: string;
  room_name: string;
  has_uniform: boolean;
  violations?: string[];
  status?: string;
  time: string;
  error?: string;
}

export default function DiemDanhKioskPage() {
  const [currentRoom, setCurrentRoom] = useState("A1-301");
  const [isCustomRoom, setIsCustomRoom] = useState(false);
  const [customRoomInput, setCustomRoomInput] = useState("");
  const [currentTime, setCurrentTime] = useState("");
  const [currentDate, setCurrentDate] = useState("");
  const [soundEnabled, setSoundEnabled] = useState(true);

  // Active scan result displayed in result card
  const [activeResult, setActiveResult] = useState<
    (KioskRecordResponse & { violations?: string[]; error?: string }) | null
  >(null);

  // Recent scans list (up to 8 items)
  const [recentScans, setRecentScans] = useState<HistoryScanItem[]>([]);

  // Load saved room from localStorage on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem("kiosk_room");
      if (saved) {
        setCurrentRoom(saved);
        if (!PRESET_ROOMS.includes(saved)) {
          setIsCustomRoom(true);
          setCustomRoomInput(saved);
        }
      }
    } catch {
      // ignore
    }
  }, []);

  // Update room selection & persist
  const handleRoomChange = (room: string) => {
    setCurrentRoom(room);
    try {
      localStorage.setItem("kiosk_room", room);
    } catch {
      // ignore
    }
  };

  // Real-time Clock tick
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      const timeStr = now.toLocaleTimeString("vi-VN", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      });
      const dateStr = now.toLocaleDateString("vi-VN", {
        weekday: "long",
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      });
      setCurrentTime(timeStr);
      setCurrentDate(dateStr);
    };

    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  // Handle successful check-in / check-out
  const handleScanSuccess = useCallback(
    (data: KioskRecordResponse) => {
      setActiveResult(data);

      const newScan: HistoryScanItem = {
        id: `${data.student_code}_${Date.now()}`,
        type: data.type,
        student_code: data.student_code,
        student_name: data.student_name,
        class_code: data.class_code || "--",
        room_name: data.room_name,
        has_uniform: data.has_uniform,
        status: data.status,
        time: data.time || data.check_out_time || data.check_in_time || new Date().toISOString(),
      };

      setRecentScans((prev) => [newScan, ...prev.slice(0, 9)]);
    },
    []
  );

  // Handle scan error (e.g. not enrolled or no schedule)
  const handleScanError = useCallback(
    (err: { student_code: string; error_message: string; room_name: string }) => {
      const errResult = {
        type: "CHECK_IN" as const,
        student_code: err.student_code,
        student_name: "Không thể điểm danh",
        room_name: err.room_name,
        class_code: "--",
        has_uniform: false,
        error: err.error_message,
        time: new Date().toISOString(),
      };

      setActiveResult(errResult);

      const errScan: HistoryScanItem = {
        id: `err_${err.student_code}_${Date.now()}`,
        type: "ERROR",
        student_code: err.student_code,
        student_name: "Chưa thể ghi nhận",
        class_code: "--",
        room_name: err.room_name,
        has_uniform: false,
        error: err.error_message,
        time: new Date().toISOString(),
      };

      setRecentScans((prev) => [errScan, ...prev.slice(0, 9)]);
    },
    []
  );

  // Test sound / user gesture unlock
  const handleToggleSound = () => {
    const next = !soundEnabled;
    setSoundEnabled(next);
    if (next) {
      playKioskAudioFeedback("success");
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans select-none antialiased">
      {/* =====================================================================
          KIOSK HEADER BAR
      ====================================================================== */}
      <header className="h-16 shrink-0 border-b border-slate-800 bg-slate-950/95 px-6 flex items-center justify-between z-20 backdrop-blur">
        {/* Left: School Logo & System Title */}
        <div className="flex items-center gap-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-950/80 border border-emerald-700/80 text-emerald-400">
            <School className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-base font-semibold text-white tracking-tight flex items-center gap-2">
              Kiosk Điểm danh Tự động AI
              <span className="rounded bg-slate-800 border border-slate-700 px-1.5 py-0.5 text-[10px] font-mono text-emerald-400 uppercase">
                FaceID + Uniform
              </span>
            </h1>
            <p className="text-xs text-slate-400 capitalize">
              {currentDate || "Đang tải ngày..."}
            </p>
          </div>
        </div>

        {/* Center: Realtime Digital Clock */}
        <div className="hidden md:flex items-center gap-2.5 rounded-lg bg-slate-900 border border-slate-800 px-4 py-1.5 shadow-inner">
          <Clock className="h-4 w-4 text-emerald-400 animate-pulse" />
          <span className="font-mono text-xl font-bold tabular-nums tracking-widest text-slate-100">
            {currentTime || "--:--:--"}
          </span>
        </div>

        {/* Right: Room Selector & Sound & Exit Controls */}
        <div className="flex items-center gap-3">
          {/* Room Selector Dropdown */}
          <div className="flex items-center gap-1.5 rounded-lg bg-slate-900 border border-slate-800 px-2.5 py-1">
            <MapPin className="h-3.5 w-3.5 text-slate-400" />
            <span className="text-xs text-slate-400 font-medium">Phòng:</span>
            {!isCustomRoom ? (
              <select
                value={currentRoom}
                onChange={(e) => {
                  if (e.target.value === "CUSTOM") {
                    setIsCustomRoom(true);
                  } else {
                    handleRoomChange(e.target.value);
                  }
                }}
                className="bg-transparent text-xs font-mono font-semibold text-emerald-400 focus:outline-none cursor-pointer"
              >
                {PRESET_ROOMS.map((r) => (
                  <option key={r} value={r} className="bg-slate-900 text-slate-200">
                    {r}
                  </option>
                ))}
                <option value="CUSTOM" className="bg-slate-900 text-slate-400">
                  + Phòng khác...
                </option>
              </select>
            ) : (
              <div className="flex items-center gap-1">
                <input
                  type="text"
                  value={customRoomInput}
                  onChange={(e) => setCustomRoomInput(e.target.value)}
                  placeholder="Nhập tên phòng"
                  className="w-20 bg-slate-800 px-1.5 py-0.5 text-xs text-white rounded focus:outline-none"
                />
                <button
                  type="button"
                  onClick={() => {
                    if (customRoomInput.trim()) {
                      handleRoomChange(customRoomInput.trim());
                    }
                    setIsCustomRoom(false);
                  }}
                  className="px-1.5 py-0.5 text-[10px] rounded bg-emerald-600 text-white font-medium"
                >
                  OK
                </button>
              </div>
            )}
          </div>

          {/* Sound Toggle Button */}
          <button
            onClick={handleToggleSound}
            title={soundEnabled ? "Tắt âm thanh thông báo" : "Bật âm thanh thông báo"}
            className={`flex h-8 w-8 items-center justify-center rounded-lg border transition-colors ${
              soundEnabled
                ? "border-emerald-800 bg-emerald-950/60 text-emerald-400 hover:bg-emerald-900/60"
                : "border-slate-800 bg-slate-900 text-slate-500 hover:bg-slate-800"
            }`}
          >
            {soundEnabled ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
          </button>

          {/* Admin Exit Button */}
          <Link
            href="/"
            title="Thoát màn hình Kiosk về Trang chủ"
            className="flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Về Hệ thống</span>
          </Link>
        </div>
      </header>

      {/* =====================================================================
          MAIN KIOSK WORKSPACE (SPLIT LAYOUT)
      ====================================================================== */}
      <main className="flex-1 p-4 md:p-6 grid grid-cols-1 lg:grid-cols-12 gap-6 overflow-hidden">
        {/* Left/Center Column: High-Priority Live Camera Feed (7 cols) */}
        <div className="lg:col-span-7 xl:col-span-8 flex flex-col gap-3">
          <div className="flex-1 flex flex-col justify-center">
            <CameraFeed
              currentRoom={currentRoom}
              onScanSuccess={handleScanSuccess}
              onScanError={handleScanError}
              cooldownSeconds={12}
            />
          </div>

          {/* Kiosk Instruction Notice Banner */}
          <div className="flex items-center justify-between rounded-lg border border-slate-800/80 bg-slate-900/70 px-4 py-2 text-xs text-slate-400">
            <div className="flex items-center gap-2">
              <HelpCircle className="h-4 w-4 text-emerald-400 shrink-0" />
              <span>
                Đứng thẳng trước ống kính camera (khoảng cách 0.5m - 1.5m), giữ khuôn mặt rõ nét và mặc đồng phục trường quy định.
              </span>
            </div>
            <span className="font-mono tabular-nums text-[11px] text-slate-500 shrink-0 ml-2">
              Tự động Check-in / Check-out
            </span>
          </div>
        </div>

        {/* Right Column: Active Result Card + Recent Scans History (5 cols) */}
        <div className="lg:col-span-5 xl:col-span-4 flex flex-col gap-4 overflow-hidden">
          {/* Active Result Card or Waiting Placeholder */}
          <div className="shrink-0">
            {activeResult ? (
              <AttendanceResultCard
                result={activeResult}
                onDismiss={() => setActiveResult(null)}
                autoDismissMs={4000}
              />
            ) : (
              <div className="rounded-xl border border-dashed border-slate-800 bg-slate-900/40 p-6 text-center text-slate-400 flex flex-col items-center justify-center min-h-[160px]">
                <UserCheck className="h-10 w-10 text-slate-600 mb-2 animate-pulse" />
                <h4 className="text-sm font-semibold text-slate-300">
                  Sẵn sàng quét điểm danh
                </h4>
                <p className="mt-1 text-xs text-slate-500 max-w-xs">
                  Sinh viên bước vào vị trí quét trước camera để hệ thống nhận diện FaceID và kiểm tra tác phong.
                </p>
              </div>
            )}
          </div>

          {/* Recent Attendance Scans History Panel */}
          <div className="flex-1 flex flex-col min-h-0 rounded-xl border border-slate-800 bg-slate-900/70 p-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <History className="h-4 w-4 text-slate-400" />
                <h3 className="text-sm font-semibold text-slate-200">
                  Lượt quét gần nhất tại phòng {currentRoom}
                </h3>
              </div>
              <span className="font-mono text-xs text-slate-400 tabular-nums">
                {recentScans.length} lượt
              </span>
            </div>

            {/* Scrollable Scans List */}
            <div className="mt-3 flex-1 overflow-y-auto space-y-2 pr-1 custom-scrollbar">
              {recentScans.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-slate-500 text-xs py-8">
                  <span>Chưa có lượt quét nào trong phiên làm việc này</span>
                </div>
              ) : (
                recentScans.map((item) => {
                  const isCheckIn = item.type === "CHECK_IN";
                  const isCheckOut = item.type === "CHECK_OUT";
                  const isError = item.type === "ERROR";

                  let scanTime = "--:--:--";
                  try {
                    scanTime = new Date(item.time).toLocaleTimeString("vi-VN", {
                      hour: "2-digit",
                      minute: "2-digit",
                      second: "2-digit",
                      hour12: false,
                    });
                  } catch {
                    scanTime = new Date().toLocaleTimeString();
                  }

                  return (
                    <div
                      key={item.id}
                      className="flex items-center justify-between rounded-lg border border-slate-800/80 bg-slate-950/60 p-2.5 text-xs hover:border-slate-700 transition-colors"
                    >
                      <div className="min-w-0 flex items-center gap-2.5">
                        {/* Status Icon */}
                        <div
                          className={`flex h-7 w-7 shrink-0 items-center justify-center rounded ${
                            isError
                              ? "bg-rose-950/80 text-rose-400 border border-rose-800/60"
                              : isCheckIn
                              ? "bg-emerald-950/80 text-emerald-400 border border-emerald-800/60"
                              : "bg-blue-950/80 text-blue-400 border border-blue-800/60"
                          }`}
                        >
                          {isError ? (
                            <XCircle className="h-4 w-4" />
                          ) : (
                            <CheckCircle2 className="h-4 w-4" />
                          )}
                        </div>

                        {/* Name & Code */}
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5 truncate">
                            <span className="font-medium text-slate-200 truncate">
                              {item.student_name}
                            </span>
                            <span className="font-mono text-[11px] text-slate-400 shrink-0">
                              ({item.student_code})
                            </span>
                          </div>
                          <div className="flex items-center gap-2 text-[11px] text-slate-500">
                            <span>{item.class_code}</span>
                            <span>•</span>
                            <span className={item.has_uniform ? "text-emerald-400" : "text-rose-400"}>
                              {item.has_uniform ? "Đúng đồng phục" : "Sai đồng phục"}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Right: Badge & Time */}
                      <div className="flex flex-col items-end shrink-0 pl-2">
                        <span
                          className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider font-mono ${
                            isError
                              ? "bg-rose-950 text-rose-300 border border-rose-800"
                              : isCheckIn
                              ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                              : "bg-blue-950 text-blue-300 border border-blue-800"
                          }`}
                        >
                          {isError ? "Lỗi" : isCheckIn ? "In" : "Out"}
                        </span>
                        <span className="font-mono tabular-nums text-[10px] text-slate-400 mt-0.5">
                          {scanTime}
                        </span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
